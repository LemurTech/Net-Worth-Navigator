# Social Security — Live Benefit Derivation & Validation

**Status:** Proposed
**Date:** 2026-08-08
**Depends on:** [2026-08-07 v2 Event-Driven Timeline](2026-08-07-v2-event-driven-timeline.md) (shipped on `dev`)
**Related:** [2026-08-06 Event Management in the Setup Panel](2026-08-06-event-management-setup-panel.md)
**Source:** Design proposal + full codebase audit of `ss_start_age` / `social_security_benefits` / `SocialSecurity.monthly_benefit` call sites, 2026-08-08

---

## Motivation

The v2 event-driven timeline (2026-08-07) moved Social Security start timing into `[[events]] type = "SocialSecurity"` blocks with an age-entry UI: the user types a claiming age, the backend computes `year = birth_year + age` and stores it in TOML. That part works and should not be revisited.

But the *benefit amount* half of that same event was only half-migrated:

- `admin_app.py`'s add/update-event handlers look up `person.social_security_benefits[age]` and write the result into the event as `monthly_benefit` **once, at save time** — a snapshot, not a live value.
- The runtime income calculation (`model.py:4380`) and the survivor step-up calculation (`model.py:2119`) both read that stored `monthly_benefit` **verbatim**, with no re-derivation and no fallback to the benefit table.
- If the user later edits `social_security_benefits` (updated SSA estimate) or the event's age, the stored `monthly_benefit` goes stale silently — nothing recomputes it, nothing warns about the mismatch.
- If a `SocialSecurity` event exists for a person whose benefit table is missing or incomplete, today's behavior ranges from "narrow 400 error" (add-event, table exists but lacks the age key) to "silently do nothing" (add-event, table missing entirely) to "no check at all" (update-event) to "silently treat as $0" (`_planned_social_security_monthly_benefit`'s `float(x or 0.0)` coercion).

The fix: make the benefit amount a fully derived value, resolved fresh every time it's needed, never persisted in TOML. Fail loudly and specifically when it can't be resolved, instead of drifting or going quiet.

---

## Current State (verified against `dev` HEAD, 2026-08-08)

| Area | Status |
|---|---|
| Age-entry UI (`templates/setup_panel.html` `SocialSecurity` form) | **Shipped.** Only exposes `age`; help text already says benefit is "auto-looked up." No change needed here. |
| `year = birth_year + age` computed at save time | **Shipped**, in `admin_app.py` add/update-event handlers. No change needed. |
| `monthly_benefit` computed **and stored** at save time | **Shipped but wrong per target design** — should be looked up live at read time, not persisted. |
| Runtime income calc trusts stored `monthly_benefit` | **Live, needs to change.** `model.py:4380`, `model.py:2119`. |
| Reverse derivation (event `year` → age) | **Exists only in frontend JS** (`setup_panel.html:2728-2736`). No backend equivalent is wired in. `_person_event_age` (`model.py:2530`) exists but is dead code and has a bug: it returns raw `year` instead of `year - birth_year` when no explicit `age` field is stored on the event (which is always the case for real `SocialSecurity` events today — they store `year`, not `age`). |
| Validation of missing/incomplete benefit table | **Partial and inconsistent.** Only fires on add-event, only when the table exists but lacks the specific age key (`admin_app.py:2211-2215`). Missing table entirely → silent no-op. Update-event → no check at all. `validate_scenario()` (`model.py:542`) has zero SS-related checks. |
| Legacy synthesis functions (`_synthesize_social_security_event`, `_resolve_social_security_events`, `_resolve_social_security_monthly_benefit`) | **Dead code** — not called from `resolve_runtime_config()`. Reusable as a starting point for the new resolver (see below), but currently unreachable. |
| Display surfaces reading `person.ss_start_age` directly | `tables.py:274-298` (Scenario Parameters table), `demo_setup_page.py:163`. Both v1-only; go blank on any scenario where `ss_start_age` has been migrated off the person. |
| Docs | Stale: `docs/systemPatterns.md:82`, `src/references/survivor-phase-modeling.md:143-149`, `docs/guide/.../social-security.mdx` all describe the pre-refactor synthesis-based design. |
| Tests | `tests/test_recurring_events.py`'s SS synthesis tests pre-populate the exact `year`/`monthly_benefit` the pass-through path already produces — they pass today without exercising synthesis/derivation logic at all, and would not catch a regression here. |

---

## Target Design (the contract)

1. SS start is always an `[[events]] type = "SocialSecurity"` block carrying `year` — never a person-entered `ss_start_age` as the source of truth.
2. Age-entry UI computes and stores `year`. It *may* also cache the entered age onto `person.ss_start_age` as a convenience for other code, but that cache is never authoritative.
3. Displaying/editing an event may derive age from `year - birth_year` or read the cached `ss_start_age` — the two must always agree, since one is derivable from the other.
4. `monthly_benefit` is **never** written into `[[events]]` TOML. It is resolved at read time, every time, from `person.social_security_benefits[age]`.
5. If a `SocialSecurity` event exists and the person's benefit table is missing, or has no entry for the resolved age, resolution raises a clear, specific error — no silent skip, no silent zero, no stale stand-in value.

---

## Detailed Changes

### 1. New canonical resolver (the load-bearing piece)

Add one function that every other call site funnels through — repurposing the existing (currently dead, currently buggy) helpers rather than writing from scratch:

```python
def resolve_social_security_monthly_benefit(config: dict, person_key: str, event: dict) -> float:
    """Resolve the monthly SS benefit for a SocialSecurity event, live, from the
    person's benefit table. Raises ValueError if the age or benefit can't be
    resolved — callers must not swallow this into a silent 0.0."""
```

Behavior:
- Resolve age: prefer `person.ss_start_age` if present and consistent with the event's `year`; otherwise derive `age = event["year"] - birth_year(person["dob"])`. This is the fixed version of `_person_event_age` (`model.py:2530`) — its current fallback (`return int(event["year"])` when no explicit `age` field exists) is wrong and must be corrected to `year - birth_year`.
- Look up `person["social_security_benefits"][str(age)]`. Fall back to legacy scalar `person["ss_monthly_benefit"]` only if the table is entirely absent (documented as deprecated, not removed — see Open Questions).
- If neither resolves: `raise ValueError(f"No Social Security benefit found for {person_key} at age {age}. Add an entry to [{person_key}.social_security_benefits] or set ss_monthly_benefit.")`.

This replaces `_resolve_social_security_monthly_benefit` (`model.py:1034-1053`), which currently returns `None` silently on failure — same lookup logic, different failure behavior.

### 2. Runtime call sites — stop trusting stored `monthly_benefit`

| File:Line | Current | Change |
|---|---|---|
| `model.py:4380` (`_person_income_components`) | `annual_ss = event.get("monthly_benefit", 0) * 12` | `annual_ss = resolve_social_security_monthly_benefit(config, person_key, event) * 12` |
| `model.py:2119` (`_planned_social_security_monthly_benefit`) | `return max(0.0, float(event.get("monthly_benefit", 0.0)))` | Call the resolver instead of reading the stored field; let `ValueError` propagate rather than coercing to `0.0` |

### 3. `admin_app.py` — stop writing `monthly_benefit`, extend validation

| Endpoint | Current | Change |
|---|---|---|
| `POST /api/add-event` (`admin_app.py:2190-2221`) | Computes `monthly_benefit` from age + table, writes it into the event body; errors only if table exists but lacks the age key | Drop the write entirely. Still compute it **for display purposes only** (the response can include a `resolved_monthly_benefit` field so the UI can show it), but do not persist it. Error if the table is missing OR lacks the age key — close the current gap where a missing table silently no-ops. |
| `POST /api/update-event` (`admin_app.py:2288-2305`) | No benefit-related check at all | Same validation as add-event: resolve and surface the benefit for display; error clearly if unresolvable. Do not persist `monthly_benefit`. |
| `GET /api/events` (`admin_app.py:1994`) | Flattens stored `monthly_benefit` onto the event for card display | Call the resolver live instead, so the displayed amount always reflects the current benefit table rather than whatever was last saved. |
| `_FLOAT_FIELDS` (`admin_app.py:2109`) | Includes `"monthly_benefit"` | Remove — it's no longer a persisted field. |

### 4. `validate_scenario()` — close the "silent" gap for hand-edited TOML

`admin_app.py`'s checks only run through the Setup Panel UI. Anyone hand-editing TOML (as we've been doing all session) bypasses them entirely. Add to `model.py:542` `validate_scenario()`:

- For each enabled `SocialSecurity` event in `config["events"]`, resolve its age and confirm `person.social_security_benefits` (or legacy `ss_monthly_benefit`) has a usable value. Append a descriptive error string to the existing `(bool, list[str])` return — matching the function's current convention (it collects errors, it doesn't raise) — rather than raising `ValueError` directly, so this is consistent with how every other check in that function already reports problems.

### 5. Display-only surfaces reading `ss_start_age` directly

These don't touch benefit resolution but will silently go blank on any scenario that's been migrated (where `ss_start_age` no longer exists on the person):

| File:Line | Change |
|---|---|
| `tables.py:274-298` (Scenario Parameters "SS start age" column) | Read from the person's `SocialSecurity` event instead: derive age via the same resolver's age-derivation step (`year - birth_year`), not `person.get("ss_start_age")`. |
| `demo_setup_page.py:163` | Same change. |

### 6. Dead code cleanup

`_synthesize_social_security_event`, `_resolve_social_security_events` (`model.py:911-1032`) are unreachable from `resolve_runtime_config()` and superseded by the new resolver. Remove them, or fold their still-useful pieces (the age→year math, for any code that still needs to construct a SocialSecurity event from a bare person record — e.g. `scripts/migrate_v2.py`) into a shared helper. Out of scope for this plan but flagged since they sit right next to the code being touched: `_resolve_retirement_events` / `_synthesize_retire_event` (`model.py:802-883`) are the same kind of dead code for `Retire` events and should probably be cleaned up in the same pass for hygiene, even though this plan doesn't otherwise touch Retire/EndOfPlan.

### 7. Docs

| File | Change |
|---|---|
| `docs/systemPatterns.md:82` | Rewrite to describe live resolution, not synthesis-at-runtime. |
| `src/references/survivor-phase-modeling.md:143-149` | Update the code excerpt/line numbers and description to match the new resolver call in `_planned_social_security_monthly_benefit`. |
| `docs/guide/.../social-security.mdx` | Rewrite the user-facing workflow: age is entered on the event, benefit is looked up automatically and never hand-edited on the event itself. |
| `src/definitions_page.py:262-267` | Update the `ss_start_age` / `social_security_benefits` field descriptions to match. |

### 8. Tests

| File | Change |
|---|---|
| `tests/test_recurring_events.py` (SS synthesis tests, lines 607-731) | Rewrite fixtures so they do **not** pre-supply `monthly_benefit` in the `events` list — instead supply `social_security_benefits` and an event with only `year`, and assert the resolver produces the right value. As written today these tests would keep passing through any regression in derivation logic. |
| `tests/test_tax_model.py:121-143, 209-239` | Currently hand-write `monthly_benefit` directly into event dicts. Update to instead populate `social_security_benefits` and let resolution happen, so the tests exercise the real path. |
| New: `tests/test_social_security_resolution.py` | Cover: exact-age match, missing table (raises), table present but missing age key (raises), legacy `ss_monthly_benefit` scalar fallback, age derived correctly from `year - birth_year` for an event with no cached `ss_start_age`. |
| `tests/test_assumptions_summary.py`, `tests/test_simulation_modes.py` | Check whether their `ss_start_age` fixtures still make sense once `tables.py`/`demo_setup_page.py` stop reading that field directly; update if they assert on that display path. |

### 9. Scenario TOML files — remove now-redundant stored values

Once the resolver ships, existing `monthly_benefit` values in `[[events]]` blocks become redundant (harmless if left, since nothing reads them anymore, but they'll drift from the table over time and confuse anyone hand-editing the file). Options:

- **Leave them** — they're inert once the runtime stops reading them, and removing them is a larger diff across every scenario file for no functional gain.
- **Strip them** — as part of a follow-up pass (could reuse `scripts/migrate_v2.py`'s pattern), for cleanliness, so the TOML doesn't lie about what's authoritative.

Recommend: leave them for now, strip opportunistically when a file is next touched for another reason (matches how `migrate_v2.py --strip-comments` was scoped as separate from the v2 schema migration itself).

---

## Implementation Order

### Step 1 — Resolver + runtime call sites (the hard dependency)
Write `resolve_social_security_monthly_benefit()`, fix the age-derivation bug, repoint `model.py:4380` and `model.py:2119` to use it. This is the only step that changes actual simulation output, so it needs the new/updated tests (Step 4) passing before merging.

### Step 2 — `admin_app.py`
Stop persisting `monthly_benefit` on add/update; extend validation to cover the missing-table case; switch `GET /api/events` to resolve live for display.

### Step 3 — `validate_scenario()`
Add the SS benefit-resolution check so hand-edited TOML gets the same guardrail as the UI path.

### Step 4 — Tests
Rewrite the fixtures identified above so they genuinely exercise derivation and validation, not just pass-through.

### Step 5 — Display-surface fixes
`tables.py` and `demo_setup_page.py` stop reading `ss_start_age` directly.

### Step 6 — Docs + dead-code cleanup
Rewrite the stale docs; remove or repurpose the dead synthesis functions.

---

## Risks

### Runtime behavior change for existing scenarios
Any scenario whose stored `monthly_benefit` currently *disagrees* with what the benefit table would produce (e.g., edited by hand after the event was created, or the table was updated but the event wasn't re-saved) will see its projected SS income change once this ships — that's the intended fix, but it means projections can shift for reasons that aren't a scenario edit. Worth a changelog note.

### Legacy `ss_monthly_benefit` scalar fallback
The target design (item 5) doesn't explicitly address this pre-existing legacy field. Recommend keeping it as a secondary fallback (documented as deprecated) rather than deleting it outright in this pass — deleting it is a separable, smaller breaking change if desired later.

### `_person_event_age` fix touches shared code
If `_person_event_age` is also used (or will be used) by the parallel Retire/EndOfPlan dead-code cleanup mentioned in item 6, fixing its bug here should be coordinated with that cleanup rather than duplicated.

### Multiple people, same age table shape
No new risk beyond what already exists — each person has their own `social_security_benefits` table and is resolved independently.

---

## Open Questions

1. Should the legacy `ss_monthly_benefit` scalar fallback be kept indefinitely, deprecated with a warning, or removed in this same pass? (Recommend: keep, deprecate in docs only, revisit later.)
2. Should existing scenario TOML files have their now-redundant `monthly_benefit` values stripped as part of this work, or left for a later pass? (Recommend: leave, per item 9 above.)
3. Should the Retire/EndOfPlan dead-code cleanup (item 6, out of scope here) be its own follow-up plan doc, given it's the same shape of problem but not part of the SS benefit contract?

---

## Versioning

No TOML schema change (unlike the v2 event-driven timeline plan) — existing scenario files keep working as-is; stored `monthly_benefit` values simply stop being read. This is a MINOR version bump: behavior/validation change, not a required migration.
