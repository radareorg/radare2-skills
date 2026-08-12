#!/usr/bin/env python3
"""Install/uninstall this category's skills into every configured SKILLDIRS target.

Cross-platform equivalent of the sibling categories' `make install`/`make
uninstall` (dev/Makefile, r2mcp/Makefile, radius2/Makefile) -- same target
resolution (every skill-name subdirectory here, into every SKILLDIRS entry),
but COPIES instead of symlinking. `ln -fs`/`os.symlink` needs Developer-Mode-
or-admin rights on Windows; copying needs no special privilege at all, on any
platform. Trade-off: a copy does not live-update when the source here
changes -- re-run `install` to refresh an already-installed copy.

Usage:
    python install.py install
    python install.py uninstall
    python install.py install --skilldirs "~/.agents/skills" "~/.claude/skills"
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_MK = HERE.parent / "config.mk"


def read_skilldirs(config_path: Path) -> list[str]:
    """Parse SKILLDIRS=... out of config.mk (shell-style KEY=value, '#' comments)."""
    if not config_path.is_file():
        raise FileNotFoundError(f"config.mk not found at {config_path}")
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("SKILLDIRS="):
            value = stripped[len("SKILLDIRS="):].strip()
            return value.split()
    raise ValueError(f"No uncommented SKILLDIRS= line found in {config_path}")


def skill_dirs_here() -> list[Path]:
    """Every skill-name subdirectory in this category (mirrors `find * -maxdepth 0 -type d`)."""
    return sorted(p for p in HERE.iterdir() if p.is_dir())


def do_install(targets: list[Path]) -> None:
    skills = skill_dirs_here()
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            dest = target / skill.name
            shutil.copytree(skill, dest, dirs_exist_ok=True)
            print(f"installed {skill.name} -> {dest}")


def do_uninstall(targets: list[Path]) -> None:
    skills = skill_dirs_here()
    for target in targets:
        for skill in skills:
            dest = target / skill.name
            if dest.exists():
                shutil.rmtree(dest)
                print(f"removed {dest}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument(
        "--skilldirs",
        nargs="+",
        metavar="DIR",
        help="Override the SKILLDIRS list from config.mk (space-separated paths).",
    )
    args = parser.parse_args()

    raw_dirs = args.skilldirs if args.skilldirs else read_skilldirs(CONFIG_MK)
    targets = [Path(d).expanduser() for d in raw_dirs]

    if args.action == "install":
        do_install(targets)
    else:
        do_uninstall(targets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
