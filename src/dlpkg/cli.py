"""
CLI entry point for dlpkg.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
import logging

from dlpkg import __version__
from dlpkg.versioning import SemVer
from dlpkg.package import PythonPackage
from dlpkg.tomlutil import ConfigToml
from dlpkg.util import ensure_empty_dir, run, make_read_only_recursively

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CMD_FORMAT:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'  # Reset code
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class _HelpWithVersionAction(argparse.Action):
    """Like the default -h/--help action, but also prints the dlpkg version and install location."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        location = Path(__file__).resolve().parent
        print(f"dlpkg {__version__}")
        print(f"Location: {location}")
        print()
        parser.print_help()
        parser.exit()


def cmd_version(args: argparse.Namespace) -> int:
    logger.debug(f"cmd_version() args: {args}")

    pkg_info = PythonPackage(args.root_dir)

    # -- Read current version
    # TODO: Need more validation here to ensure we querying the package version.
    #   If we add more flags in the future this logic might break, so we should consider
    #   refactoring how we read/write package info in general.

    if args.bump is None:
        print(pkg_info.version)
        return 0

    # -- bump version
    current = SemVer.parse(pkg_info.version)
    new_version = str(current.bump(args.bump))  # bump version based on args.bump (major/minor/patch)

    # -- tries to update version in package anywhere it is defined (e.g. pyproject.toml, __init__.py, etc.)
    pkg_info.version = new_version

    print(f"{current} -> {new_version}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    src_dir = Path(args.root_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    ensure_empty_dir(out_dir)

    run(["python", "-m", "pip", "install", "--upgrade", "pip"])
    run(["python", "-m", "pip", "install", "--upgrade", "build"])
    run(["python", "-m", "build", "--outdir", str(out_dir)], cwd=src_dir)

    print(f"Built dist into: {out_dir}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    override = False
    root_dir = Path(args.source_path).resolve()
    name: str
    version: str
    src_path: Path | None = None

    if root_dir.is_dir():
        pkg_info = PythonPackage(root_dir)
        if not pkg_info.has_config:
            raise RuntimeError(f"Cannot find package config in {root_dir}. "
                               f"Please make sure pyproject.toml exists and is properly configured.")
        name = pkg_info.name
        version = pkg_info.version
        src_path = pkg_info.root_dir
    elif '.whl' in root_dir.suffixes:
        # If source_path is not a directory, we assume it's a wheel file and try to parse package info from the file name.
        # This is a bit hacky but allows us to support publishing directly from a wheel file without needing to specify the package name and version separately.
        wheel_path = Path(args.source_path).resolve()
        wheel_pattern = re.compile(
            r'^(?P<name>[^-]+)-'
            r'(?P<version>[^-]+)-'
            r'(?P<python>py[^-]+)-'
            r'[^-]+-'
            r'[^-]+$'
        )
        m = wheel_pattern.match(wheel_path.stem)
        if not m:
            raise RuntimeError(f"Cannot parse package info from wheel file name: {wheel_path.stem}")
        name = m.group("name")
        version = m.group("version")
        src_path = wheel_path
    else:
        raise RuntimeError(f"Invalid source path: {args.source_path}. Must be a package root directory or a wheel file.")

    dst_path = (Path(args.out_dir) / name / f"{args.channel}-{version}").resolve()

    msg = [
        # "="*40,
        f"{CMD_FORMAT.BOLD}* Publishing package:{CMD_FORMAT.END}",
        f"package: {name}",
        f"version: {version}",
        f"channel: {args.channel}",
        f"source: {src_path.as_posix() if src_path else f'{CMD_FORMAT.RED}No wheel found in dist dir!{CMD_FORMAT.END}'}",
        f"target dir: {dst_path.as_posix()}",
        # "="*40
    ]
    print('\n'.join(msg))

    if args.dry_run:
        return 0

    # -- resolve target folder
    if override:
        try:
            ensure_empty_dir(dst_path)
        except PermissionError as e:
            e.args = (f"Cannot override published packages. Access is denied: {dst_path!r}",)
            raise e
    elif dst_path.exists():
        raise FileExistsError(f"Target folder already exists: {dst_path!r}")

    # Use pip to install the package from source to the target folder.
    # This will ensure that we only copy necessary files based on
    # pyproject.toml configuration (e.g. using src layout, excluding tests, etc.)
    run(["python", "-m", "pip", "install", src_path.as_posix(),
         "--target", dst_path.as_posix()])

    if args.read_only:
        make_read_only_recursively(dst_path)

    # if args.write_mod:
    #     _write_mod_file(dst, args.name, args.version)

    print(f"{CMD_FORMAT.GREEN}Successfully published {name} package to: {dst_path}{CMD_FORMAT.END}")
    return 0


def _scan_published_versions(folder: Path | str, package_name: str, limit: int = 10) -> tuple[list[SemVer], list[SemVer]]:
    """Scans <folder>/<package_name>/* for `rel-<version>` and `dev-<version>` subdirectories.

    Entries that don't match this shape, or whose version part fails to parse as SemVer, are
    silently skipped.

    Returns (rel_versions, dev_versions), each sorted newest-first and truncated to `limit`
    entries. Returns ([], []) if <folder>/<package_name> doesn't exist.
    """
    pkg_dir = Path(folder) / package_name
    rel_versions: list[SemVer] = []
    dev_versions: list[SemVer] = []
    if not pkg_dir.is_dir():
        return rel_versions, dev_versions

    for entry in pkg_dir.iterdir():
        if not entry.is_dir():
            continue
        channel, _, version_str = entry.name.partition("-")
        if channel not in ("rel", "dev"):
            continue
        try:
            ver = SemVer.parse(version_str)
        except ValueError:
            continue
        (rel_versions if channel == "rel" else dev_versions).append(ver)

    rel_versions.sort(reverse=True)
    dev_versions.sort(reverse=True)
    return rel_versions[:limit], dev_versions[:limit]


def _resolve_list_dir(dir_arg: str | None) -> Path:
    """Resolves the folder to scan for published versions using precedence:
    --dir CLI flag > DLPKG_PUBLISH_DIR environment variable > config.toml [defaults].install_dir.

    Raises:
        RuntimeError: if none of the three sources provide a folder.
    """
    if dir_arg:
        return Path(dir_arg).resolve()

    env_dir = os.environ.get("DLPKG_PUBLISH_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    config = ConfigToml.open_default()
    if config.install_dir is not None:
        return config.install_dir

    raise RuntimeError(
        "No folder to scan for published versions. Pass --dir PATH, set the "
        "DLPKG_PUBLISH_DIR environment variable, or run `dlpkg list --set-default-dir PATH` first."
    )


def cmd_list(args: argparse.Namespace) -> int:
    logger.debug(f"cmd_list() args: {args}")

    if args.set_default_dir:
        config = ConfigToml.open_default()
        config.install_dir = args.set_default_dir
        config.save()
        print(f"{CMD_FORMAT.GREEN}Default list folder set to: {config.install_dir}{CMD_FORMAT.END}")
        return 0

    if not args.package_name:
        raise RuntimeError("package_name is required unless --set-default-dir is given.")

    folder = _resolve_list_dir(args.dir)
    rel_versions, dev_versions = _scan_published_versions(folder, args.package_name)

    lines = [f"{CMD_FORMAT.BOLD}Published versions (latest 10):{CMD_FORMAT.END}"]
    lines.extend(f"    rel-{v}" for v in rel_versions)
    lines.append("")
    lines.append(f"{CMD_FORMAT.BOLD}Development versions (latest 10):{CMD_FORMAT.END}")
    lines.extend(f"    dev-{v}" for v in dev_versions)

    print("\n".join(lines))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="dlpkg", add_help=False)
    p.add_argument("-h", "--help", action=_HelpWithVersionAction, help="show this help message and exit")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common parent parser for subcommands
    # base_parser = argparse.ArgumentParser(add_help=False)
    # base_parser.add_argument("--name", default=None, help="Package name (default: read from pyproject)")
    # base_parser.add_argument("--root-dir", default=".", help="Package root (default: current directory)")
    # base_parser.add_argument("--source-dir", help="Relative source directory path (default: read from pyproject)")

    # -- version
    p_bump = sub.add_parser("version", help="Get/Set version of the package.")
    p_bump.add_argument("root_dir", nargs="?", default='.', help="Source folder to build (default: current directory)")
    p_bump.add_argument("--bump", nargs="?", const="patch", choices=["major", "minor", "patch", "prerelease"])
    # p_bump.add_argument("--dev-tag", default=None, help="Optional prerelease tag to append after version E.g. 'dev' would result in a version like 1.2.3-dev")
    p_bump.set_defaults(func=cmd_version)

    # -- build
    p_build = sub.add_parser("build", help="Build wheel+sdist")
    p_build.add_argument("root_dir", nargs="?", default='.', help="Source folder to build (default: current directory)")
    p_build.add_argument("--out-dir", default="./build", help="Output dir (default: ./build)")
    p_build.set_defaults(func=cmd_build)

    # -- publish
    p_pub = sub.add_parser("publish", help="Publish package files into a target root")
    p_pub.add_argument("source_path", nargs="?", default='.', help=f"Source wheel file or dist folder (default: first .whl in dist folder)")
    p_pub.add_argument("--out-dir", default="./publish", help=f"Target root folder. E.g. This is where the package will be published.")
    # p_pub.add_argument("--name", help="Package name (default: read from pyproject)")
    # p_pub.add_argument("--version", help="Override version (default: read from pyproject)")
    p_pub.add_argument("--channel", choices=["rel", "dev"], default="rel")
    p_pub.add_argument("--read-only", action="store_true", help="Set read-only permissions on the published files")
    # p_pub.add_argument("--write-mod", action="store_true", help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_pub.add_argument("--dist-dir", default='./dist', help=f"Publish from wheel file or dist folder (default: ./dist). If a dist folder is given, the first .whl file inside will be used.")
    p_pub.add_argument("--dry-run", action="store_true", help=f"Print publish plan without copying files")
    p_pub.set_defaults(func=cmd_publish)

    # -- list
    p_list = sub.add_parser("list", help="List published versions of a package.")
    p_list.add_argument("package_name", nargs="?", default=None,
                         help="Name of the package to list published versions for (required unless --set-default-dir is given).")
    p_list.add_argument("--dir", default=None,
                         help="Folder to scan for published packages (same folder passed to `publish --out-dir`). "
                              "Overrides DLPKG_PUBLISH_DIR and the config.toml default.")
    p_list.add_argument("--set-default-dir", default=None, metavar="PATH",
                         help="Save PATH as the default folder to scan (written to config.toml) and exit.")
    p_list.set_defaults(func=cmd_list)

    # -- write-mod file
    # p_mod = sub.add_parser("writemod", parents=[base_parser], help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_mod.add_argument("--version", default=None, help="Override version (default: read from pyproject)")
    # p_mod.set_defaults(func=cmd_write_mod)

    # Use sys.argv (user input) by default, but can be overridden for testing
    args = p.parse_args()

    # print(f"main() args: {args}")
    # logger.debug(f"main() args: {args}")

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
