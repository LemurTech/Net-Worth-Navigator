#!/usr/bin/env python3
"""Migrate NWN scenario TOML files from v1 (person-field timeline) to v2 (event-driven timeline).

v1 fields migrated:
  person.retirement_year   → [[events]] type="Retire"
  person.ss_start_age      → [[events]] type="SocialSecurity"
  person.life_expectancy   → [[events]] type="EndOfPlan" (with age field)

Run: .venv/bin/python scripts/migrate_v2.py [--dry-run] [scenario_slug ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import tomlkit

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def _person_initial(person: dict, person_key: str) -> str:
    name = str(person.get("name", "")).strip()
    if name and name[0].isalpha():
        return name[0].upper()
    return person_key[:1].upper()


def migrate_scenario(path: Path, dry_run: bool = False) -> list[str]:
    """Migrate one scenario file. Returns list of actions taken."""
    actions: list[str] = []
    slug = path.stem

    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    events = doc.get("events")
    if not isinstance(events, list):
        # tomlkit AoT may need creation
        doc["events"] = tomlkit.aot()
        events = doc["events"]

    for person_key in ("person1", "person2"):
        person = doc.get(person_key)
        if not isinstance(person, dict):
            continue
        initial = _person_initial(person, person_key)
        dob = person.get("dob")
        birth_year = None
        if isinstance(dob, str) and "-" in dob:
            try:
                birth_year = int(dob.split("-", 1)[0])
            except (TypeError, ValueError):
                pass

        # Check for existing events of these types
        existing_types = {str(e.get("type", "")): str(e.get("person", ""))
                         for e in events if isinstance(e, dict)}

        # ── Retire ────────────────────────────────────────────────────
        retire_year = person.get("retirement_year")
        has_retire = any(
            str(e.get("type", "")) == "Retire" and str(e.get("person", "")) == person_key
            for e in events
        )
        if retire_year is not None and not has_retire:
            try:
                yr = int(retire_year)
                tbl = tomlkit.table()
                tbl["enabled"] = True
                tbl["type"] = "Retire"
                tbl["label"] = f"Retirement ({initial})"
                tbl["person"] = person_key
                tbl["year"] = yr
                events.append(tbl)
                del person["retirement_year"]
                actions.append(f"  {slug}: {person_key} Retire → event year={yr}")
            except (TypeError, ValueError):
                actions.append(f"  {slug}: {person_key} Retire SKIPPED (invalid year)")

        # ── SocialSecurity ────────────────────────────────────────────
        ss_age = person.get("ss_claim_age") or person.get("ss_start_age")
        has_ss = any(
            str(e.get("type", "")) == "SocialSecurity" and str(e.get("person", "")) == person_key
            for e in events
        )
        if ss_age is not None and birth_year is not None and not has_ss:
            try:
                start_year = birth_year + int(ss_age)
                benefits = person.get("social_security_benefits")
                monthly = None
                if isinstance(benefits, dict):
                    monthly = benefits.get(str(int(ss_age)))
                    if monthly is None:
                        monthly = benefits.get(str(ss_age))
                if monthly is not None:
                    tbl = tomlkit.table()
                    tbl["enabled"] = True
                    tbl["type"] = "SocialSecurity"
                    tbl["label"] = f"SS Begins ({initial})"
                    tbl["person"] = person_key
                    tbl["year"] = start_year
                    tbl["monthly_benefit"] = float(monthly)
                    events.append(tbl)
                    if "ss_start_age" in person:
                        del person["ss_start_age"]
                    if "ss_claim_age" in person:
                        del person["ss_claim_age"]
                    actions.append(
                        f"  {slug}: {person_key} SocialSecurity → event year={start_year} "
                        f"age={ss_age} benefit={monthly}"
                    )
                else:
                    actions.append(
                        f"  {slug}: {person_key} SocialSecurity SKIPPED "
                        f"(no benefit at age {ss_age})"
                    )
            except (TypeError, ValueError):
                actions.append(f"  {slug}: {person_key} SocialSecurity SKIPPED (invalid age)")

        # ── EndOfPlan ─────────────────────────────────────────────────
        life_exp = person.get("life_expectancy")
        has_eop = any(
            str(e.get("type", "")) == "EndOfPlan" and str(e.get("person", "")) == person_key
            for e in events
        )
        if life_exp is not None and not has_eop:
            try:
                le = int(life_exp)
                tbl = tomlkit.table()
                tbl["enabled"] = True
                tbl["type"] = "EndOfPlan"
                tbl["label"] = f"End of Plan ({initial})"
                tbl["person"] = person_key
                tbl["age"] = le       # v2: store age, not year
                tbl["year"] = birth_year + le if birth_year else 0  # computed year
                events.append(tbl)
                del person["life_expectancy"]
                yr_str = f"year={birth_year + le}" if birth_year else "year=0 (no dob)"
                actions.append(
                    f"  {slug}: {person_key} EndOfPlan → event age={le} {yr_str}"
                )
            except (TypeError, ValueError):
                actions.append(f"  {slug}: {person_key} EndOfPlan SKIPPED (invalid value)")

    if actions and not dry_run:
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    return actions


def main():
    dry_run = "--dry-run" in sys.argv
    slugs = [a for a in sys.argv[1:] if not a.startswith("--") and a != "--dry-run"]

    if slugs:
        paths = [SCENARIOS_DIR / f"{slug}.toml" for slug in slugs]
    else:
        paths = sorted(SCENARIOS_DIR.glob("*.toml"))

    total = 0
    for path in paths:
        if not path.exists():
            print(f"  SKIP: {path} not found")
            continue
        actions = migrate_scenario(path, dry_run=dry_run)
        for a in actions:
            print(a)
        total += len(actions)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}{total} action(s) across {len(paths)} file(s)")
    if dry_run:
        print("Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
