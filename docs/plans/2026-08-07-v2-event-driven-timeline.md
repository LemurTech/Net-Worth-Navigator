# Event-Driven Timeline — v2.0 Architecture Shift

**Status:** Proposed
**Date:** 2026-08-07
**Precedes:** Phase 3c (edit/delete/reorder events)
**Follows:** Phase 3b (Add Event form + synthesized events)
**Source:** Architectural assessment of event-vs-metadata date management

---

## Motivation

Currently, three key timeline dates are split across two locations:

| Concept | Where | UX |
|---------|-------|-----|
| When do wages stop? | Metadata tab: "Retires (year)" + age slider | Can't see alongside other events |
| When does SS begin? | `person.ss_start_age` in TOML, no UI | Invisible to user |
| How long do I live? | `person.life_expectancy` in TOML, no UI | Invisible to user |

Users think in terms of ages ("I'll retire at 67", "I'll claim SS at 70", "I'll live to 90") but the system stores years. More importantly, these dates are scattered across the Metadata tab and hidden TOML fields — nowhere near the Events tab where all other timeline events live.

The proposal: move all three into `[[events]]` blocks with **age-based entry**. The Events tab becomes the single place for all timeline decisions. A user modeling "retire at 62 instead of 67" changes one card in one tab.

---

## What Changes

### Person config — 3 fields removed

| Field | Becomes |
|-------|---------|
| `person.retirement_year` | `[[events]] type="Retire"` with `age` field → `year = birth_year + age` |
| `person.ss_start_age` / `ss_claim_age` | `[[events]] type="SocialSecurity"` with `age` field → `year = birth_year + age` |
| `person.life_expectancy` | `[[events]] type="EndOfPlan"` with `age` field → `year = birth_year + age` |

### Person config — what stays

`dob`, `name`, income fields (`annual_take_home`, `gross_income`, etc.), contribution fields, `social_security_benefits` table, `survivor_ss_start_age`, `annual_401k_contribution_split`, `rmd_trad_ira_share`.

### Setup Panel — Metadata tab

**Removed from People section:** Retires (year), or-age slider.

**Added to People section:** Nothing. The section simplifies to Name, Birth Year, and income/contribution fields.

### Setup Panel — Events tab

**Unhidden in Add Event selector:** Retire, SocialSecurity, EndOfPlan.

**New event forms** for these three types accept an **Age** field instead of Year. On save, the backend computes `year = birth_year + age` from the person's `dob` in the same TOML.

**No longer synthesized:** These become normal editable events with enable/disable toggles. The `SYSTEM` badge and `synthesized` flag are removed. The event list shows them inline with all other events.

---

## Model Changes (~40 lines in model.py)

### Sites that currently read `person.retirement_year`

| Line | Current behavior | New behavior |
|------|-----------------|-------------|
| 4322 | `if year >= person["retirement_year"]: earned_income = 0.0` | Scan events for this person's Retire event, read its `year` |
| 4343 | `if year < person["retirement_year"]` (NewJob guard) | Same — scan events |
| 869-883 | `_synthesize_retire_event()` — creates event from person field | **Remove** — event exists in TOML now |

### Sites that currently read `person.ss_start_age`

| Line | Current behavior | New behavior |
|------|-----------------|-------------|
| 970-1008 | `_synthesize_social_security_event()` — creates event from person fields | **Remove** — event exists in TOML now |
| 2116 | Benefit fallback: `person.get("ss_start_age")` | Read from SocialSecurity event's year, compute age as `year - birth_year` |

### Sites that currently read `person.life_expectancy`

| Line | Current behavior | New behavior |
|------|-----------------|-------------|
| 739-750 | `_sync_end_of_plan_years()` — syncs year from `dob + life_expectancy` | Read age from EndOfPlan event, compute year as `birth_year + age` |
| 649-665 | Validation: bounds-checks `life_expectancy` | Validate EndOfPlan event's age instead |

### Validation

`validate_scenario()` currently checks:
- `retirement_year` is within life_expectancy and not before simulation start
- `life_expectancy` is reasonable

New checks:
- Each person has exactly one enabled `Retire` event with a valid `year`
- Each person has exactly one enabled `EndOfPlan` event with a valid `year`
- `Retire.year < EndOfPlan.year` (can't retire after death)
- `SocialSecurity.year >= 62` (earliest claiming age)

### Gantt chart

`charts.py:2145` reads `person.retirement_year`. Change to scan events for Retire, same pattern as `_first_retirement_year()` already does.

### Tables (Scenario Parameters)

`tables.py:262-296` displays `life_expectancy` per person. Change to read from EndOfPlan events and compute age as `year - birth_year`.

---

## Event Form Updates

### Three forms get an Age field

**Retire:**
```
Label:  Retirement (M)
Person: [person1 ▼]
Age:    [67]           ← NEW — replaces Year
→ Year computed as birth_year + 67 = 2037
```

**SocialSecurity:**
```
Label:  SS Begins (M)
Person: [person1 ▼]
Age:    [70]           ← NEW — replaces Year
→ Year computed as birth_year + 70 = 2040
Monthly Benefit: [2500]  ← from social_security_benefits lookup
```

**EndOfPlan:**
```
Label:  End of Plan (M)
Person: [person1 ▼]
Age:    [90]           ← NEW — replaces Year
→ Year computed as birth_year + 90 = 2057
```

### Age field behavior

The frontend sends `age` instead of `year`. The `POST /api/add-event` endpoint:
1. Receives `age` and `person`
2. Reads the person's `dob` from the TOML
3. Computes `year = birth_year + age`
4. Stores `year` in the event (not `age` — the model reads `year`)

For edit (Phase 3c), the reverse: read `year` from the event, compute `age = year - birth_year`, populate the form with the age.

---

## TOML Migration

### Migration script behavior

For each scenario TOML file:

1. **Retire:** If `[person1].retirement_year` is present, create:
```toml
[[events]]
enabled = true
type    = "Retire"
label   = "Retirement (M)"
person  = "person1"
year    = <retirement_year>
```
Then remove `retirement_year` from `[person1]`.

2. **SocialSecurity:** If `[person1].ss_start_age` (or `ss_claim_age`) and `dob` and `social_security_benefits` are present, create:
```toml
[[events]]
enabled = true
type    = "SocialSecurity"
label   = "SS Begins (M)"
person  = "person1"
year    = <birth_year + ss_start_age>
monthly_benefit = <benefit at that age>
```
Then remove `ss_start_age`/`ss_claim_age` from `[person1]`.

3. **EndOfPlan:** If `[person1].life_expectancy` and `dob` are present, create:
```toml
[[events]]
enabled = true
type    = "EndOfPlan"
label   = "End of Plan (M)"
person  = "person1"
year    = <birth_year + life_expectancy>
```
Then remove `life_expectancy` from `[person1]`.

4. Repeat for `[person2]` if present.

### Files to migrate

Tracked sample scenarios:
- `scenarios/sample.toml`
- `scenarios/sample-a.toml`
- `scenarios/sample-b.toml`
- `scenarios/sample-couples.toml`
- `scenarios/starter.toml`
- `scenarios/starter-couple.toml`

Gitignored personal scenarios (manual migration):
- `scenarios/default.toml`
- `scenarios/comfortable.toml`
- `scenarios/optimistic.toml`
- `scenarios/restrictive.toml`
- `scenarios/early-death-person1.toml`
- `scenarios/early-death-person2.toml`

---

## Implementation Order

### Step 1 — Model changes (the hard dependency)

All code sites that read `person.retirement_year`, `person.ss_start_age`, and `person.life_expectancy` are updated to scan events instead. The synthesis functions are removed. Validation is re-pointed. Tests pass.

### Step 2 — Migration script + TOML files

A `scripts/migrate_v2.py` script performs the mechanical migration on all scenario files. Run once. Verify all scenarios render correctly.

### Step 3 — Setup Panel: Metadata tab

Remove Retires (year), or-age slider, and Life Expectancy inputs from the People section. Remove `person1_retirement_year`, `person2_retirement_year`, and the life_expectancy entries from `_QUICK_CONTROL_MAP`, `initQuickEdit()`, and `collectQuickControls()`.

### Step 4 — Setup Panel: Events tab

Update the event field catalog so Retire, SocialSecurity, and EndOfPlan forms use an Age field. The `POST /api/add-event` endpoint computes `year` from `age` + `dob`. Remove the `synthesized` logic from `GET /api/events` — these events now come from TOML directly.

### Step 5 — Phase 3c (edit/delete/reorder)

Now that all events are normal editable cards, Phase 3c proceeds as originally planned. Edit forms for Retire/SS/EndOfPlan compute `age` from stored `year` and `dob` for display.

---

## Risks

### Backward compatibility

Existing scenario files produced before v2.0 won't have the required Retire/SS/EndOfPlan `[[events]]` blocks. Options:

1. **Reject old files** — `validate_scenario()` fails with a clear message about missing events
2. **Auto-migrate on load** — `_toml_open` or `get_scenario` detects old format and synthesizes events in memory (not writing back)
3. **Migration script** — user runs `python scripts/migrate_v2.py` once

Recommended: Option 1 (fail with clear message) + Option 3 (one-time script). Auto-migration on load adds complexity and hides the schema change from the user.

### Monthly benefit lookup at form time

The SocialSecurity event form needs to read the monthly benefit from `social_security_benefits[age]`. This requires `GET /api/events` or a new lightweight endpoint to return the benefit amount for a given person + age. Alternatively, the form can leave it blank and the migration script fills it.

### Couple households

Each person gets their own Retire, SS, and EndOfPlan events. Two people → six events. The Events tab needs to handle this gracefully — the label shows the person initial to disambiguate.

### Event ordering

Retire and EndOfPlan events sit among the existing events. Order matters (events are processed sequentially), but these events are primarily read by the income computation loop, which scans all events regardless of order.

---

## Versioning

This is a MAJOR version bump: v1.x → **v2.0**. Reason: TOML schema migration (`person.retirement_year`, `person.ss_start_age`, `person.life_expectancy` removed). MAJOR is for "your TOML files need updating."
