"""
CLI entry point for dlpkg.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import logging

from dlpkg.versioning import SemVer
from dlpkg.package import PythonPackage
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
    src_dir = Path(args.source).resolve()
    out_dir = Path(args.out_dir).resolve()
    ensure_empty_dir(out_dir)

    run(["python", "-m", "pip", "install", "--upgrade", "pip"])
    run(["python", "-m", "pip", "install", "--upgrade", "build"])
    run(["python", "-m", "build", "--outdir", str(out_dir)], cwd=src_dir)

    print(f"Built dist into: {out_dir}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    override = False

    root_dir = Path(args.src_path).resolve()
    if not root_dir.is_dir():
        pass

    pkg_info = PythonPackage(root_dir)
    src_path = Path(args.src_path).resolve()
    dst_path = (Path(args.out_dir) / pkg_info.name / f"{args.channel}-{pkg_info.version}").resolve()

    # collect source wheel path
    # wheel_paths = list(dist_dir.glob("**/*.whl"))

    msg = [
        # "="*40,
        f"{CMD_FORMAT.BOLD}* Installing package:{CMD_FORMAT.END}",
        f"package: {pkg_info.name}",
        f"version: {pkg_info.version}",
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
            e.args = (f"Cannot override installed packages. Access is denied: {dst_path!r}",)
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

    print(f"{CMD_FORMAT.GREEN}Successfully installed {pkg_info.name} package to: {dst_path}{CMD_FORMAT.END}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="dlpkg")
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

    # -- install
    p_inst = sub.add_parser("install", help="Copy files into a target root")
    p_inst.add_argument("source_path", nargs="?", default='.', help=f"Source wheel file or dist folder (default: first .whl in dist folder)")
    p_inst.add_argument("--out-dir", default="./install", help=f"Target root folder. E.g. This is where the package will be installed.")
    # p_inst.add_argument("--name", help="Package name (default: read from pyproject)")
    # p_inst.add_argument("--version", help="Override version (default: read from pyproject)")
    p_inst.add_argument("--channel", choices=["rel", "dev"], default="rel")
    p_inst.add_argument("--read-only", action="store_true", help="Set read-only permissions on the installed files")
    # p_inst.add_argument("--write-mod", action="store_true", help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_inst.add_argument("--dist-dir", default='./dist', help=f"Install from wheel file or dist folder (default: ./dist). If a dist folder is given, the first .whl file inside will be used.")
    p_inst.add_argument("--dry-run", action="store_true", help=f"Print publish plan without copying files")
    p_inst.set_defaults(func=cmd_install)

    # -- write-mod file
    # p_mod = sub.add_parser("writemod", parents=[base_parser], help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_mod.add_argument("--version", default=None, help="Override version (default: read from pyproject)")
    # p_mod.set_defaults(func=cmd_write_mod)

    # Use sys.argv (user input) by default, but can be overridden for testing
    args = p.parse_args()

    print(f"main() args: {args}")
    logger.debug(f"main() args: {args}")

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
