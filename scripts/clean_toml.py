#!/usr/bin/env python3
"""Clean scenario TOML files: strip decorative section headers and normalize blank lines
between [[events]] blocks.

Run: .venv/bin/python scripts/clean_toml.py [--dry-run] [scenario_slug ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

# Match decorative section headers: lines starting with "# " followed by
# dash/box-drawing run of 3+ chars (──, ══, etc.)
_SECTION_HEADER = re.compile(r'^#\s+[─═━▬▔▀▄█▌▐░▒▓]{3,}')


def clean_file(path: Path, dry_run: bool = False) -> list[str]:
    """Clean one scenario file. Returns list of actions taken."""
    actions = []
    slug = path.stem
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")

    # Strip section header lines
    cleaned = [line for line in lines if not _SECTION_HEADER.match(line)]
    removed = len(lines) - len(cleaned)
    if removed:
        actions.append(f"  {slug}: removed {removed} section header(s)")

    # Rejoin, then normalize blank lines between [[events]] blocks
    text = "\n".join(cleaned)
    # Add blank line between consecutive ]] and [[events]]
    text = re.sub(r'(\]\])(\n)\[\[events\]\]', r'\1\n\n[[events]]', text)
    # Remove triple+ blank lines, keep at most 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    if not dry_run and text != original:
        path.write_text(text, encoding="utf-8")

    return actions


def main():
    dry_run = "--dry-run" in sys.argv
    slugs = [a for a in sys.argv[1:] if not a.startswith("--")]

    if slugs:
        paths = [SCENARIOS_DIR / f"{slug}.toml" for slug in slugs]
    else:
        paths = sorted(SCENARIOS_DIR.glob("*.toml"))

    total_headers = 0
    for path in paths:
        if not path.exists():
            print(f"  SKIP: {path} not found")
            continue
        actions = clean_file(path, dry_run=dry_run)
        for a in actions:
            print(a)
        total_headers += len(actions)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}{total_headers} file(s) modified")


if __name__ == "__main__":
    main()
