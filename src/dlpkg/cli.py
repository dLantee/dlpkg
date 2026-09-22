"""
CLI entry point for dlpkg.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from dlpkg import __version__
from dlpkg.package import PythonPackage
from dlpkg.tomlutil import ConfigToml
from dlpkg.util import ensure_empty_dir, make_read_only_recursively, run
from dlpkg.versioning import SemVer

logger = logging.getLogger(__name__)

PUBLISH_DIR_ENV = "DLPKG_PUBLISH_DIR"
DEFAULT_PUBLISH_DIR = "./publish"
DEFAULT_BUILD_DIR = "./build"
DEFAULT_LIST_LIMIT = 10
LIST_LIMIT_KEY = "list_limit"

# Publish channel -> heading printed by `dlpkg list`. Published folders are named <channel>-<version>.
CHANNELS = {"rel": "Published versions", "dev": "Development versions"}
LIST_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
LIST_LABEL_WIDTH = 22

_WHEEL_NAME_RE = re.compile(r'^(?P<name>[^-]+)-(?P<version>[^-]+)-(?P<python>py[^-]+)-[^-]+-[^-]+$')


class CMD_FORMAT:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class _HelpWithVersionAction(argparse.Action):
    """Like the default -h/--help action, but also prints the dlpkg version and install location."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"dlpkg {__version__}")
        print(f"Location: {Path(__file__).resolve().parent}")
        print()
        parser.print_help()
        parser.exit()


def cmd_version(args: argparse.Namespace) -> int:
    logger.debug("cmd_version() args: %s", args)
    pkg_info = PythonPackage(args.root_dir)

    if args.bump is None:
        print(pkg_info.version)
        return 0

    current = SemVer.parse(pkg_info.version)
    new_version = str(current.bump(args.bump))
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


def _configured_publish_dir(dir_arg: str | None) -> Path | None:
    """Shared precedence for the published-packages root:
    CLI flag > PUBLISH_DIR_ENV environment variable > config.toml [defaults].publish_dir.
    Returns None when none of them is set."""
    if dir_arg:
        return Path(dir_arg).resolve()
    env_dir = os.environ.get(PUBLISH_DIR_ENV)
    if env_dir:
        return Path(env_dir).resolve()
    return ConfigToml.open_default().publish_dir


def _resolve_publish_out_dir(out_dir_arg: str | None) -> Path:
    """Target root for `dlpkg publish`; falls back to DEFAULT_PUBLISH_DIR."""
    return _configured_publish_dir(out_dir_arg) or Path(DEFAULT_PUBLISH_DIR).resolve()


def _resolve_list_dir(dir_arg: str | None) -> Path:
    """Folder `dlpkg list` scans.

    Raises:
        RuntimeError: if neither the flag, the environment variable nor config.toml provide one.
    """
    folder = _configured_publish_dir(dir_arg)
    if folder is None:
        raise RuntimeError(
            f"No folder to scan for published versions. Pass --dir PATH, set the {PUBLISH_DIR_ENV} "
            "environment variable, or run `dlpkg config set publish_dir PATH` first."
        )
    return folder


def _package_source(source_path: str) -> tuple[str, str, Path]:
    """Returns (name, version, path) for a package root dir or a .whl file.

    Given a wheel, name and version are parsed from the file name rather than the metadata."""
    path = Path(source_path).resolve()
    if path.is_dir():
        pkg_info = PythonPackage(path)
        if not pkg_info.has_config:
            raise RuntimeError(f"Cannot find package config in {path}. "
                               "Please make sure pyproject.toml exists and is properly configured.")
        return pkg_info.name, pkg_info.version, pkg_info.root_dir
    if path.suffix == ".whl":
        m = _WHEEL_NAME_RE.match(path.stem)
        if not m:
            raise RuntimeError(f"Cannot parse package info from wheel file name: {path.stem}")
        return m.group("name"), m.group("version"), path
    raise RuntimeError(f"Invalid source path: {source_path}. Must be a package root directory or a wheel file.")


def cmd_publish(args: argparse.Namespace) -> int:
    name, version, src_path = _package_source(args.source_path)
    out_dir = _resolve_publish_out_dir(args.out_dir)
    dst_path = (out_dir / name / f"{args.channel}-{version}").resolve()

    print('\n'.join([
        f"{CMD_FORMAT.BOLD}* Publishing package:{CMD_FORMAT.END}",
        f"package: {name}",
        f"version: {version}",
        f"channel: {args.channel}",
        f"source: {src_path.as_posix()}",
        f"target dir: {dst_path.as_posix()}",
    ]))

    if args.dry_run:
        return 0

    if dst_path.exists():
        raise FileExistsError(f"Target folder already exists: {dst_path!r}")

    # pip copies only what pyproject.toml declares (src layout, excludes, etc.).
    run(["python", "-m", "pip", "install", src_path.as_posix(), "--target", dst_path.as_posix()])

    if args.read_only:
        make_read_only_recursively(dst_path)

    # if args.write_mod:
    #     _write_mod_file(dst, args.name, args.version)

    print(f"{CMD_FORMAT.GREEN}Successfully published {name} package to: {dst_path}{CMD_FORMAT.END}")
    return 0


def _scan_published_versions(folder: Path | str, package_name: str,
                             limit: int = DEFAULT_LIST_LIMIT) -> dict[str, list[tuple[SemVer, datetime]]]:
    """Scans <folder>/<package_name>/<channel>-<version> folders for every channel in CHANNELS.

    Entries with an unknown channel or an unparsable version are skipped. Returns, per channel,
    (version, published_at) pairs sorted newest-first and truncated to `limit`. `published_at`
    is the folder's filesystem creation time. Every channel is present, possibly empty.
    """
    pkg_dir = Path(folder) / package_name
    found: dict[str, list[tuple[SemVer, datetime]]] = {channel: [] for channel in CHANNELS}
    if not pkg_dir.is_dir():
        return found

    for entry in pkg_dir.iterdir():
        if not entry.is_dir():
            continue
        channel, _, version_str = entry.name.partition("-")
        if channel not in found:
            continue
        try:
            ver = SemVer.parse(version_str)
        except ValueError:
            continue
        found[channel].append((ver, datetime.fromtimestamp(entry.stat().st_ctime)))

    for versions in found.values():
        versions.sort(key=lambda pair: pair[0], reverse=True)
        del versions[limit:]
    return found


def _format_list_line(channel: str, version: SemVer, published_at: datetime) -> str:
    label = f"{channel}-{version}"
    return f"    {label:<{LIST_LABEL_WIDTH}}[{published_at.strftime(LIST_TIMESTAMP_FORMAT)}]"


def _resolve_list_limit(limit_arg: int | None) -> int:
    """Version-count cutoff for `dlpkg list`:
    --limit flag > config.toml [defaults].list_limit > DEFAULT_LIST_LIMIT."""
    if limit_arg is not None:
        return limit_arg

    configured = ConfigToml.open_default().get_value(LIST_LIMIT_KEY)
    if configured is not None:
        try:
            return int(configured)
        except (TypeError, ValueError):
            logger.warning("Ignoring non-integer %s in config.toml: %r", LIST_LIMIT_KEY, configured)
    return DEFAULT_LIST_LIMIT


def cmd_list(args: argparse.Namespace) -> int:
    logger.debug("cmd_list() args: %s", args)
    if not args.package_name:
        raise RuntimeError("package_name is required.")

    folder = _resolve_list_dir(args.dir)
    limit = _resolve_list_limit(args.limit)
    found = _scan_published_versions(folder, args.package_name, limit=limit)

    sections = []
    for channel, heading in CHANNELS.items():
        lines = [f"{CMD_FORMAT.BOLD}{heading} (latest {limit}):{CMD_FORMAT.END}"]
        lines.extend(_format_list_line(channel, ver, ts) for ver, ts in found[channel])
        sections.append("\n".join(lines))
    print("\n\n".join(sections))
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Implements `dlpkg config get|set|list` (git-config style) against config.toml."""
    logger.debug("cmd_config() args: %s", args)
    config = ConfigToml.open_default()

    if args.action == "list":
        values = config.all_values()
        if not values:
            print("(no settings configured)")
        for key, value in values.items():
            print(f"{key} = {value}")
        return 0

    if args.action == "get":
        value = config.get_value(args.key)
        if value is None:
            print(f"{CMD_FORMAT.YELLOW}{args.key} is not set{CMD_FORMAT.END}")
            return 1
        print(value)
        return 0

    if args.action == "set":
        config.set_value(args.key, args.value)
        config.save()
        print(f"{CMD_FORMAT.GREEN}{args.key} = {config.get_value(args.key)}{CMD_FORMAT.END}")
        return 0

    raise RuntimeError(f"Unknown config action: {args.action!r}")


def main() -> int:
    p = argparse.ArgumentParser(prog="dlpkg", add_help=False)
    p.add_argument("-h", "--help", action=_HelpWithVersionAction, help="show this help message and exit")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common parent parser for subcommands
    # base_parser = argparse.ArgumentParser(add_help=False)
    # base_parser.add_argument("--name", default=None, help="Package name (default: read from pyproject)")
    # base_parser.add_argument("--root-dir", default=".", help="Package root (default: current directory)")
    # base_parser.add_argument("--source-dir", help="Relative source directory path (default: read from pyproject)")

    p_version = sub.add_parser("version", help="Get/Set version of the package.")
    p_version.add_argument("root_dir", nargs="?", default='.', help="Package root (default: current directory)")
    p_version.add_argument("--bump", nargs="?", const="patch", choices=["major", "minor", "patch", "prerelease"])
    p_version.set_defaults(func=cmd_version)

    p_build = sub.add_parser("build", help="Build wheel+sdist")
    p_build.add_argument("root_dir", nargs="?", default='.', help="Source folder to build (default: current directory)")
    p_build.add_argument("--out-dir", default=DEFAULT_BUILD_DIR, help=f"Output dir (default: {DEFAULT_BUILD_DIR})")
    p_build.set_defaults(func=cmd_build)

    p_pub = sub.add_parser("publish", help="Publish package files into a target root")
    p_pub.add_argument("source_path", nargs="?", default='.',
                       help="Package root directory or .whl file (default: current directory)")
    p_pub.add_argument("--out-dir", default=None,
                       help="Target root folder the package is published into. "
                            f"Overrides {PUBLISH_DIR_ENV} and the config.toml default. "
                            f"Falls back to {DEFAULT_PUBLISH_DIR} if none of those are set.")
    p_pub.add_argument("--channel", choices=list(CHANNELS), default="rel")
    p_pub.add_argument("--read-only", action="store_true", help="Set read-only permissions on the published files")
    # p_pub.add_argument("--write-mod", action="store_true", help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    p_pub.add_argument("--dry-run", action="store_true", help="Print publish plan without copying files")
    p_pub.set_defaults(func=cmd_publish)

    p_list = sub.add_parser("list", help="List published versions of a package.")
    p_list.add_argument("package_name", help="Name of the package to list published versions for.")
    p_list.add_argument("--dir", default=None,
                        help="Folder to scan for published packages (same folder passed to `publish --out-dir`). "
                             f"Overrides {PUBLISH_DIR_ENV} and the config.toml default.")
    p_list.add_argument("--limit", type=int, default=None,
                        help="Max number of rel/dev versions to show. "
                             f"Overrides config.toml {LIST_LIMIT_KEY} (default: {DEFAULT_LIST_LIMIT}).")
    p_list.set_defaults(func=cmd_list)

    p_config = sub.add_parser("config", help="Get/set/list dlpkg settings stored in config.toml.")
    config_sub = p_config.add_subparsers(dest="action", required=True)
    p_config_get = config_sub.add_parser("get", help="Print the value of a setting.")
    p_config_get.add_argument("key", help=f"Setting name, e.g. publish_dir or {LIST_LIMIT_KEY}")
    p_config_set = config_sub.add_parser("set", help="Set and save a setting.")
    p_config_set.add_argument("key", help=f"Setting name, e.g. publish_dir or {LIST_LIMIT_KEY}")
    p_config_set.add_argument("value", help="Value to store")
    config_sub.add_parser("list", help="Print all configured settings.")
    p_config.set_defaults(func=cmd_config)

    # -- write-mod file
    # p_mod = sub.add_parser("writemod", parents=[base_parser], help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_mod.add_argument("--version", default=None, help="Override version (default: read from pyproject)")
    # p_mod.set_defaults(func=cmd_write_mod)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
