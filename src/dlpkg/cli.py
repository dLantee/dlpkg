from __future__ import annotations

import argparse
import os
from pathlib import Path
from dataclasses import dataclass
from tomlkit import TOMLDocument

from dlpkg.builder import build_dist
from dlpkg.installer import InstallSpec, install_wheel
from dlpkg.versioning import update_init_version
from dlpkg.util import SemVer
from dlpkg.tomlutil import PyProjectToml, ConfigToml


BOLD = '\033[1m'
END = '\033[0m'

def _update_args_from_files(args: argparse.Namespace):
    """Update args with values from pyproject.toml and config.toml if they are not already set."""

    # TODO: we could optimize this by only parsing the files once per command,
    #  but for simplicity we parse them in each command for now. We can refactor later if needed.

    # TODO: Only update args that are relevant for the current command.
    #  For example, we only need publish_dir for install command,
    #  so we can skip parsing config.toml for other commands.
    #  This would require some mapping of which args are needed for which commands.

    # If we have pyproject.toml, parse it and add to args for easy access in subcommands
    pyproject_path = (Path(args.root_dir) / "pyproject.toml").resolve()
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")
    pyproject = PyProjectToml.open(pyproject_path)
    args.pyproject = pyproject

    if getattr(args, "name", None) is None:
        args.name = pyproject.project_name

    if getattr(args, "source_dir", None) is None:
        # If we have a src/ or python/ folder, use that as source_dir.
        # Otherwise default to root_dir.
        root_dir = Path(args.root_dir).resolve()
        for candidate in PyProjectToml.DEFAULT_SRC_DIRS:
            src_path = root_dir / candidate
            if src_path.is_dir():
                args.source_dir = str(src_path)
                break
        else:
            args.source_dir = str(root_dir)

    if getattr(args, "version", None) is None:
        args.version = pyproject.project_version

    if args.cmd in ["install"] and getattr(args, "out_dir", None) is None:
        # If we have config.toml, use publish_dir as default out_dir for install command
        config_path = (Path(args.root_dir) / "config.toml").resolve()
        if config_path.exists():
            config = ConfigToml.open(config_path)
            args.out_dir = str(config.publish_dir)
        elif "MAYA_MODULE_PATH" in os.environ:
            # Fallback to MAYA_MODULE_PATH or current directory
            args.out_dir = os.environ.get("MAYA_MODULE_PATH").split()[0]
        else:
            raise RuntimeError("No config.toml found and MAYA_MODULE_PATH is not set, \
            cannot determine default out_dir for install command. Use --out-dir to specify target root folder.")
    return args


def cmd_version(args: argparse.Namespace) -> int:
    root_dir = Path(args.root_dir).resolve()
    pyproject = args.pyproject  # type: PyProjectToml

    # -- Read current version from pyproject.toml
    if args.bump is None:
        print(args.version)
        return 0

    # -- bump version
    current = args.version
    cur = SemVer.parse(current)
    new_version = str(cur.bump(args.bump))  # bump version based on args.bump (major/minor/patch)

    # -- update pyproject.toml
    try:
        pyproject.project_version = new_version
        pyproject.save()
    except ValueError:
        print(f"Invalid version format: {new_version!r}, skipping pyproject.toml update")
    except RuntimeError:
        print("Could not update pyproject.toml version, skipping")
    print("Updated pyproject.toml version")

    # -- update __init__.py version
    for src_root in pyproject.source_roots(root_dir):
        # src_pkg_root = src_root / src_dir
        print('Root source:', src_root)
        if update_init_version(src_root, new_version):
            print(f"Updated {src_root / '__init__.py'} __version__")
        else:
            print("Skipped __init__.py version update (not found or no __version__)")

    # Add more version updates here as needed
    pass

    print(f"{current} -> {new_version}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    root_dir = Path(args.root_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    build_dist(root_dir, out_dir)
    print(f"Built dist into: {out_dir}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    dist_dir = (Path(args.root_dir) / "dist").resolve()
    target_root = Path(args.out_dir).resolve()

    dst = target_root / args.name / f"{args.channel}-{args.version}"

    if args.dry_run:
        msg = [
            # "="*40,
            f"* {BOLD}Installing package:{END}",
            f"package: {args.name}",
            f"version: {args.version}",
            f"channel: {args.channel}",
            f"target dir: {dst}",
            # "="*40
        ]
        print('\n'.join(msg))
        return 0
    else:
        for wheel_path in dist_dir.glob("**/*.whl"):
            install_wheel(wheel_path, dst, override=False, write_mod_file=False)
            print(f"Installed folder to: {dst}")
            break
        return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="dlpkg")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common parent parser for subcommands
    base_parser = argparse.ArgumentParser(add_help=False)
    # base_parser.add_argument("--name", default=None, help="Package name (default: read from pyproject)")
    base_parser.add_argument("--root-dir", default=".", help="Repo root (default: . )")
    base_parser.add_argument("--source-dir", default=None, help="Source directory (default: read from pyproject)")

    # -- version
    p_bump = sub.add_parser("version", parents=[base_parser], help="Get/Set version of the package.")
    p_bump.add_argument("--bump", nargs="?", choices=["major", "minor", "patch", "prerelease"], const="patch")
    p_bump.set_defaults(func=cmd_version)

    # -- build
    p_build = sub.add_parser("build", parents=[base_parser], help="Build wheel+sdist")
    p_build.add_argument("--out-dir", default="./dist", help="Output dir (default: ./dist)")
    p_build.set_defaults(func=cmd_build)

    # -- publish
    p_inst = sub.add_parser("install", parents=[base_parser], help="Copy files into a target root")
    p_inst.add_argument("--name", default=None, help="Package name (default: read from pyproject)")
    p_inst.add_argument("--version", default=None, help="Override version (default: read from pyproject)")
    p_inst.add_argument("--channel", choices=["rel", "dev"], default="rel")
    p_inst.add_argument("--out-dir", default=None, help=f"Target root folder. E.g. a folder on MAYA_MODULE_PATH or a shared network location. This is where the package will be installed.")
    # p_inst.add_argument("--write-mod", action="store_true", help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    p_inst.add_argument("--dry-run", action="store_true", help=f"Print publish plan without copying files")
    p_inst.set_defaults(func=cmd_install)

    # -- write-mod file
    # p_mod = sub.add_parser("writemod", parents=[base_parser], help="Write a .mod file into the first MAYA_MODULE_PATH dir")
    # p_mod.add_argument("--version", default=None, help="Override version (default: read from pyproject)")
    # p_mod.set_defaults(func=cmd_write_mod)

    # Use sys.argv (user input) by default, but can be overridden for testing
    args = p.parse_args()

    # Update args with values from pyproject.toml and
    # config.toml if not already set
    args = _update_args_from_files(args)

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
