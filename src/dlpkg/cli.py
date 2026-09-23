"""
CLI entry point for dlpkg.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import date
from pathlib import Path

from dlpkg import __version__
from dlpkg.changelog import CHANGELOG_FILE, release_changelog
from dlpkg.modfile import (MAYA_MODULE_PATH_ENV, first_maya_module_dir, mod_file_path, read_mod_target,
                           write_mod_file)
from dlpkg.package import PythonPackage
from dlpkg.published import (CHANNELS, DEV_CHANNEL, METADATA_FILE, REL_CHANNEL, PublishedVersion, find_published,
                             remove_published, scan_published, with_build_tag, write_metadata)
from dlpkg.tomlutil import ConfigToml
from dlpkg.util import ensure_empty_dir, git, git_is_clean, git_short_hash, make_read_only_recursively, run
from dlpkg.versioning import SemVer

logger = logging.getLogger(__name__)

PUBLISH_DIR_ENV = "DLPKG_PUBLISH_DIR"
DEFAULT_PUBLISH_DIR = "./publish"
DEFAULT_BUILD_DIR = "./build"
DEFAULT_LIST_LIMIT = 10
LIST_LIMIT_KEY = "list_limit"
DEFAULT_PRUNE_KEEP = 3
RELEASE_COMMIT_FORMAT = "Release {tag}"
RELEASE_BUMP_PARTS = ["major", "minor", "patch"]

LIST_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
LIST_LABEL_WIDTH = 22
ACTIVE_MARKER = "(active)"

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


def cmd_release(args: argparse.Namespace) -> int:
    """Bumps the version, dates the changelog's Unreleased section, commits `Release vX.Y.Z` and
    tags it. Never pushes."""
    logger.debug("cmd_release() args: %s", args)
    pkg_info = PythonPackage(args.root_dir)
    root = pkg_info.root_dir
    changelog_path = root / CHANGELOG_FILE
    if not changelog_path.is_file():
        raise RuntimeError(f"No {CHANGELOG_FILE} in {root}")
    if not git_is_clean(root):
        raise RuntimeError(f"{root} has uncommitted changes; commit them before releasing.")

    current = SemVer.parse(pkg_info.version)
    new_version = str(current.bump(args.bump))
    tag = f"v{new_version}"
    new_changelog = release_changelog(changelog_path.read_text(encoding="utf-8"), new_version, date.today())

    print('\n'.join([
        f"{CMD_FORMAT.BOLD}* Releasing {pkg_info.name}:{CMD_FORMAT.END}",
        f"version: {current} -> {new_version}",
        f"changelog: {changelog_path.as_posix()}",
        f"commit: {RELEASE_COMMIT_FORMAT.format(tag=tag)}",
        f"tag: {tag}",
    ]))
    if args.dry_run:
        return 0

    pkg_info.version = new_version
    changelog_path.write_text(new_changelog, encoding="utf-8")
    git(["add", "--update", "."], root)
    git(["commit", "-m", RELEASE_COMMIT_FORMAT.format(tag=tag)], root)
    git(["tag", "-a", tag, "-m", new_version], root)
    print(f"{CMD_FORMAT.GREEN}Released {tag}. Nothing was pushed: push the commit and the tag when ready.{CMD_FORMAT.END}")
    return 0


def _resolve_build_dir(out_dir_arg: str | None) -> Path:
    """Output folder for `dlpkg build`: --out-dir flag > config.toml [defaults].build_dir > DEFAULT_BUILD_DIR."""
    if out_dir_arg:
        return Path(out_dir_arg).resolve()
    return ConfigToml.open_default().build_dir or Path(DEFAULT_BUILD_DIR).resolve()


def cmd_build(args: argparse.Namespace) -> int:
    src_dir = Path(args.root_dir).resolve()
    out_dir = _resolve_build_dir(args.out_dir)
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


def _resolve_mod_dir() -> Path:
    """Folder Maya .mod files are written into:
    config.toml [defaults].mod_dir > first existing dir on MAYA_MODULE_PATH.

    Raises:
        RuntimeError: if neither provides one.
    """
    mod_dir = ConfigToml.open_default().mod_dir or first_maya_module_dir()
    if mod_dir is None:
        raise RuntimeError(
            f"No folder to write the .mod file into. Set the {MAYA_MODULE_PATH_ENV} environment "
            "variable to an existing folder, or run `dlpkg config set mod_dir PATH` first."
        )
    return mod_dir


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
    commit = git_short_hash(src_path)
    if args.channel == DEV_CHANNEL and src_path.is_dir():
        version = with_build_tag(version, commit)
    out_dir = _resolve_publish_out_dir(args.out_dir)
    dst_path = (out_dir / name / f"{args.channel}-{version}").resolve()
    mod_dir = _resolve_mod_dir() if args.write_mod else None

    print('\n'.join([
        f"{CMD_FORMAT.BOLD}* Publishing package:{CMD_FORMAT.END}",
        f"package: {name}",
        f"version: {version}",
        f"channel: {args.channel}",
        f"source: {src_path.as_posix()}",
        f"target dir: {dst_path.as_posix()}",
    ] + ([f"mod file: {mod_file_path(mod_dir, name).as_posix()}"] if mod_dir else [])))

    if args.dry_run:
        return 0

    if dst_path.exists():
        raise FileExistsError(f"Target folder already exists: {dst_path!r}")

    # pip copies only what pyproject.toml declares (src layout, excludes, etc.).
    run(["python", "-m", "pip", "install", src_path.as_posix(), "--target", dst_path.as_posix()])
    write_metadata(dst_path, name, args.channel, version, commit)

    if args.read_only:
        make_read_only_recursively(dst_path)

    print(f"{CMD_FORMAT.GREEN}Successfully published {name} package to: {dst_path}{CMD_FORMAT.END}")
    if mod_dir:
        mod_path = write_mod_file(mod_dir, name, version, dst_path)
        print(f"{CMD_FORMAT.GREEN}Wrote mod file: {mod_path}{CMD_FORMAT.END}")
    return 0


def _active_mod_target(package_name: str) -> Path | None:
    """The folder <name>.mod currently points at, or None when there is no mod dir or mod file."""
    mod_dir = ConfigToml.open_default().mod_dir or first_maya_module_dir()
    if mod_dir is None:
        return None
    return read_mod_target(mod_file_path(mod_dir, package_name))


def _format_list_line(published: PublishedVersion, active: bool = False) -> str:
    line = f"    {published.label:<{LIST_LABEL_WIDTH}}[{published.published_at.strftime(LIST_TIMESTAMP_FORMAT)}]"
    if active:
        line += f"  {CMD_FORMAT.GREEN}{ACTIVE_MARKER}{CMD_FORMAT.END}"
    return line


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
    found = scan_published(folder, args.package_name, limit=limit)
    active = _active_mod_target(args.package_name)

    sections = []
    for channel, heading in CHANNELS.items():
        lines = [f"{CMD_FORMAT.BOLD}{heading} (latest {limit}):{CMD_FORMAT.END}"]
        lines.extend(_format_list_line(published, published.path.resolve() == active)
                     for published in found[channel])
        sections.append("\n".join(lines))
    print("\n\n".join(sections))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Deletes all but the newest --keep versions of one channel, never the active one."""
    logger.debug("cmd_prune() args: %s", args)
    if args.keep < 0:
        raise ValueError("--keep must be 0 or more")
    folder = _resolve_list_dir(args.dir)
    versions = scan_published(folder, args.package_name)[args.channel]
    active = _active_mod_target(args.package_name)
    stale = [p for p in versions[args.keep:] if p.path.resolve() != active]

    if not stale:
        print(f"Nothing to prune: {len(versions)} {args.channel} version(s) of {args.package_name}, keeping {args.keep}.")
        return 0

    print(f"{CMD_FORMAT.BOLD}* Pruning {args.package_name} {args.channel} versions "
          f"(keeping newest {args.keep}):{CMD_FORMAT.END}")
    for published in stale:
        print(f"    {published.label:<{LIST_LABEL_WIDTH}}{published.path.as_posix()}")
    if args.dry_run:
        return 0

    for published in stale:
        remove_published(published)
    print(f"{CMD_FORMAT.GREEN}Removed {len(stale)} version(s).{CMD_FORMAT.END}")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    """Points the Maya <name>.mod file at an already published <channel>-<version> folder."""
    logger.debug("cmd_use() args: %s", args)
    folder = _resolve_list_dir(args.dir)
    published = find_published(folder, args.package_name, args.version)
    mod_dir = _resolve_mod_dir()

    mod_path = write_mod_file(mod_dir, args.package_name, str(published.version), published.path)
    print(f"{CMD_FORMAT.GREEN}{args.package_name} now uses {published.label}: {published.path}{CMD_FORMAT.END}")
    print(f"mod file: {mod_path}")
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

    p_version = sub.add_parser("version", help="Get/Set version of the package.")
    p_version.add_argument("root_dir", nargs="?", default='.', help="Package root (default: current directory)")
    p_version.add_argument("--bump", nargs="?", const="patch", choices=["major", "minor", "patch", "prerelease"])
    p_version.set_defaults(func=cmd_version)

    p_release = sub.add_parser("release", help="Bump the version, date the changelog, commit and tag. Never pushes.")
    p_release.add_argument("root_dir", nargs="?", default='.', help="Package root (default: current directory)")
    p_release.add_argument("--bump", required=True, choices=RELEASE_BUMP_PARTS, help="Version part to bump")
    p_release.add_argument("--dry-run", action="store_true", help="Print the release plan without changing anything")
    p_release.set_defaults(func=cmd_release)

    p_build = sub.add_parser("build", help="Build wheel+sdist")
    p_build.add_argument("root_dir", nargs="?", default='.', help="Source folder to build (default: current directory)")
    p_build.add_argument("--out-dir", default=None,
                         help="Output dir. Overrides the config.toml build_dir default "
                              f"(falls back to {DEFAULT_BUILD_DIR}).")
    p_build.set_defaults(func=cmd_build)

    p_pub = sub.add_parser("publish", help="Publish package files into a target root")
    p_pub.add_argument("source_path", nargs="?", default='.',
                       help="Package root directory or .whl file (default: current directory)")
    p_pub.add_argument("--out-dir", default=None,
                       help="Target root folder the package is published into. "
                            f"Overrides {PUBLISH_DIR_ENV} and the config.toml default. "
                            f"Falls back to {DEFAULT_PUBLISH_DIR} if none of those are set.")
    p_pub.add_argument("--channel", choices=list(CHANNELS), default=REL_CHANNEL,
                       help=f"Publish channel (default: {REL_CHANNEL}). {DEV_CHANNEL} publishes from a git "
                            "checkout get the short commit hash appended as build metadata.")
    p_pub.add_argument("--read-only", action="store_true", help="Set read-only permissions on the published files")
    p_pub.add_argument("--write-mod", action="store_true",
                       help="Write a Maya <name>.mod pointing at the published folder into the config.toml "
                            f"mod_dir, or the first existing dir on {MAYA_MODULE_PATH_ENV}")
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

    p_prune = sub.add_parser("prune", help="Delete old published versions of a package, keeping the newest ones.")
    p_prune.add_argument("package_name", help="Name of the published package.")
    p_prune.add_argument("--channel", choices=list(CHANNELS), default=DEV_CHANNEL,
                         help=f"Channel to prune (default: {DEV_CHANNEL})")
    p_prune.add_argument("--keep", type=int, default=DEFAULT_PRUNE_KEEP,
                         help=f"Newest versions to keep (default: {DEFAULT_PRUNE_KEEP}). "
                              "The version the Maya .mod file points at is always kept.")
    p_prune.add_argument("--dir", default=None,
                         help="Folder holding the published packages (same folder passed to `publish --out-dir`). "
                              f"Overrides {PUBLISH_DIR_ENV} and the config.toml default.")
    p_prune.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting")
    p_prune.set_defaults(func=cmd_prune)

    p_use = sub.add_parser("use", help="Point a package's Maya .mod file at a published version.")
    p_use.add_argument("package_name", help="Name of the published package.")
    p_use.add_argument("version", help="Published folder to use, as <channel>-<version>, e.g. rel-1.2.0")
    p_use.add_argument("--dir", default=None,
                       help="Folder holding the published packages (same folder passed to `publish --out-dir`). "
                            f"Overrides {PUBLISH_DIR_ENV} and the config.toml default.")
    p_use.set_defaults(func=cmd_use)

    p_config = sub.add_parser("config", help="Get/set/list dlpkg settings stored in config.toml.")
    config_sub = p_config.add_subparsers(dest="action", required=True)
    p_config_get = config_sub.add_parser("get", help="Print the value of a setting.")
    p_config_get.add_argument("key", help=f"Setting name, e.g. publish_dir or {LIST_LIMIT_KEY}")
    p_config_set = config_sub.add_parser("set", help="Set and save a setting.")
    p_config_set.add_argument("key", help=f"Setting name, e.g. publish_dir or {LIST_LIMIT_KEY}")
    p_config_set.add_argument("value", help="Value to store")
    config_sub.add_parser("list", help="Print all configured settings.")
    p_config.set_defaults(func=cmd_config)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
