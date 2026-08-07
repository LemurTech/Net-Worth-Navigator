#!/usr/bin/env python3
"""Fix [data_source] position in all scenario TOML files: ensure it's after [scenario]."""

import re
from pathlib import Path

SCENARIOS_DIR = Path("/home/lemurtech/Net-Worth-Navigator/scenarios")


def fix_data_source(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    
    # Find all [data_source] blocks
    matches = list(re.finditer(r'^\n?\[data_source\].*?(?=\n\[|\Z)', text, re.DOTALL | re.MULTILINE))
    if not matches:
        return False
    
    # If [data_source] is already right after [scenario], skip
    scenario_end = re.search(r'^\[scenario\].*?(?=\n\[)', text, re.DOTALL | re.MULTILINE)
    if not scenario_end:
        return False
    
    insert_pos = scenario_end.end()
    
    # Remove ALL [data_source] blocks from the text
    cleaned = text
    for m in reversed(matches):
        cleaned = cleaned[:m.start()] + cleaned[m.end():]
    
    # Keep the first data_source block and reinsert it after [scenario]
    ds_block = matches[0].group(0).lstrip('\n')
    
    # Insert after scenario with blank line separation
    result = cleaned[:insert_pos] + "\n\n" + ds_block + cleaned[insert_pos:]
    
    path.write_text(result, encoding="utf-8")
    return True


if __name__ == "__main__":
    for path in sorted(SCENARIOS_DIR.glob("*.toml")):
        if fix_data_source(path):
            print(f"  {path.stem}: fixed")
    print("Done")
