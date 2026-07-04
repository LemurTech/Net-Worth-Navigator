# Single-Person Household Support — Design Plan

> **Status:** Proposed. Not started.
> **See also:** `src/model.py`, `src/tax_model.py`, `templates/setup_panel.html`, `scenarios/starter.toml`, session finding 2026-07-04 (troubleshooting session that discovered this gap)

**Goal:** Let a single person model their own household in Net Worth Navigator without a
second `[person2]` entry, without crashing, and without nonsensical survivor-phase output.
A single user should be able to start from `starter.toml`, delete or skip Person 2, and get
a correct projection — matching what the starter template's own (currently incorrect)
comment already promises.

**Non-goal:** This plan does not add support for households of 3+ people, blended families,
or dependents. It also does not change the two-person model's behavior in any way — every
change here is additive/conditional on a `person2`-absent case.

**Why this matters:** This was flagged as one of two gaps (the other being state tax
coverage — see `docs/plans/2026-07-04-state-tax-schedule-support.md`) blocking NWN from
being usable by a wider audience beyond Person 1's own two-person household. Single adults,
widowed/divorced users, and anyone not modeling a couple currently cannot use this tool at
all — the engine hard-crashes.

---

## Background: How the Gap Was Found

`scenarios/starter.toml` contained (until this session's docs-only patch) a comment reading:
*"Person 2 (optional — delete or comment out this section if single)."* Reproduced by
copying the template, deleting `[person2]`, and running `run.py --scenario <slug>`:

```
File "src/model.py", line 3022, in _run_projection_yearly
    person2 = config["person2"]
KeyError: 'person2'
```

`validate_scenario()` in `model.py` does NOT require `[person2]` — it only requires
`[person1]` (it iterates `person_keys` dynamically). The crash is entirely in the
simulation engine (`_run_projection_yearly()`), which does `config["person2"]`
unconditionally. `starter.toml` was patched to stop promising a capability that doesn't
exist (pending this plan).

---

## Scope of `person2` Coupling (evidence, not guesswork)

`person2` is referenced ~80+ times in `src/model.py` alone. Grouped by concern:

### 1. Hard crash point
- `src/model.py:3022` — `person2 = config["person2"]` — unconditional, no `.get()` fallback.

### 2. RMD (Required Minimum Distribution) share splitting
- `_normalized_household_rmd_shares()` (`model.py` ~L200-230) computes each person's share
  of the household traditional IRA balance from `rmd_trad_ira_share`, defaulting to a 50/50
  split (`{"person1": 0.5, "person2": 0.5}`) when neither is set. Assumes two claimants.

### 3. Retirement bucket ownership
- `_initial_retirement_owner_state()`, `_normalize_two_person_shares()` — every
  `trad_ira`/`roth` owner-balance split assumes exactly two owner keys
  (`RETIREMENT_OWNER_KEYS = ("person1", "person2")`, `model.py:78`).
- Withdrawal/contribution routing (`owner_bucket["person1"]`, `owner_bucket["person2"]`)
  is hardcoded to these two keys throughout the yearly loop.

### 4. Income aggregation
- Take-home pay, gross income, 401(k)/IRA contributions, and employer match are computed
  per-person and summed for exactly `person1 + person2`. No loop over a variable-length
  person list exists anywhere in the engine.

### 5. Survivor-phase machinery (the deepest coupling)
- `_tax_phase()` in `src/tax_model.py` returns `"survivor"` when `one_deceased=True` —
  meaning "the household used to have two people, and now has one." This has no meaning
  for a household that only ever had one person.
- `[spending].survivor_percent_of_retirement` / `survivor_annual`, and the entire
  `survivor_cash_target` / `survivor_withdrawal_order` / `survivor_surplus_order` triad in
  `[withdrawal_policy]`, exist only to model "spending drops when one spouse dies."
- `EndOfPlan` event synthesis (`_sync_end_of_plan_years()`) reads `config[str(event["person"])]`
  — if the model tried to naively default a stubbed `person2`, EndOfPlan/Retirement/SS
  event synthesis for a placeholder person would inject spurious events into the timeline.

### 6. UI (Setup Panel)
- `templates/setup_panel.html` unconditionally renders `person2_name` / `person2_birth_year`
  / `person2_retirement_year` (hardcoded field id, a preexisting naming leak from Person 1's own
  household — see "Renaming debt" below) with no way to omit Person 2. `updatePersonLabels()`
  always operates on both names.

**Conclusion:** this is not a one-line guard. Any credible fix must (a) let the engine skip
person2-shaped state entirely when absent, and (b) collapse the survivor-phase concept to a
no-op for single-person households, not just avoid the crash.

---

## Design Options Considered

### Option A — Stub a "zero" person2 (rejected)
Auto-inject a `person2` dict with zero income/balances/contributions when absent.

**Rejected because:** the survivor-phase logic would still fire once `person2`'s synthetic
`life_expectancy` is reached — the model would silently switch tax phase and reduce
spending targets based on a fictional person's fictional death. This produces plausible-
looking but *wrong* output — worse than a crash, because a crash is visible and wrong
numbers are not. This violates the project's "fixes that destroy correctness are the wrong
fix" principle (AGENTS.md contribution rubric).

### Option B — `household_size` mode switch, single-person is a first-class path (recommended)
Add an explicit `[scenario].household_type = "single" | "couple"` (default `"couple"` for
backward compatibility with every existing scenario TOML). When `"single"`:
- `person2` is optional and, if absent, the engine takes a `single`-branch code path that
  never invokes `person2`-shaped logic at all — not a stub, an actual skip.
- Tax phase collapses to two phases only: `pre_retirement` → `retirement`. No `survivor`
  phase is ever entered.
- `[spending].survivor_*` fields become inert/ignored (with a validation warning if set,
  not an error — TOML authors may have stale fields from a household template).
- `[withdrawal_policy].survivor_*` fields become inert/ignored the same way.
- RMD share is always 100% to `person1` — no share-splitting logic runs.
- Retirement bucket ownership is always 100% `person1` — no owner-split logic runs.

**Recommended** because it makes single-person status an explicit, validated, documented
scenario property rather than an inferred one (inferring from "is person2 absent" is
fragile — a scenario author might leave `[person2]` present-but-zeroed by habit, and
inference would misclassify it).

### Option C — Generalize to N persons (rejected for this plan)
Refactor the engine to a list-of-persons model instead of `person1`/`person2` fields.

**Rejected as out of scope:** this is a much larger refactor (every `RETIREMENT_OWNER_KEYS`,
every owner-bucket dict, every tax-phase transition, every UI field) for a capability
(3+ person households) nobody has asked for. The Footprint Ladder principle applies:
solve the actual requirement (1 or 2 people) with the smallest correct change, not a
speculative generalization. Two-person is likely to remain the dominant case; this can be
revisited if a real 3+ person use case appears.

---

## Recommended Design (Option B) — Detail

### 1. Scenario config additions

```toml
[scenario]
household_type = "single"   # "single" | "couple" (default: "couple")
```

- `validate_scenario()` gains a check: if `household_type == "single"`, `[person2]` must
  be ABSENT (not just present-with-zeros — presence is now a validation error, to avoid the
  silent-misclassification trap from Option C's rejection reasoning). If `household_type ==
  "couple"` (or unset, for backward compat), `[person2]` remains required, exactly as today.
- Existing scenarios need zero changes — omitting `household_type` defaults to `"couple"`,
  identical to current behavior. This satisfies the "existing Monarch-using / couple-using
  functionality is not broken" invariant used successfully in the Monarch-optional plan.

### 2. Engine changes (`src/model.py`)

- `_run_projection_yearly()`: replace the unconditional `person2 = config["person2"]` with
  a branch:
  ```python
  household_type = config.get("scenario", {}).get("household_type", "couple")
  person2 = config.get("person2") if household_type == "couple" else None
  ```
- Every downstream function that currently takes `person1, person2` as required positional
  args needs an explicit single-person branch — NOT a "treat None as zeros" fallback
  (that reintroduces Option A's correctness problem). Concretely:
  - `_initial_retirement_owner_state()` — when `person2 is None`, retirement owner balances
    and shares collapse to `{"person1": 1.0}` — no `person2` key exists in the owner dicts
    at all (not `0.0` — literally absent, so downstream `.get("person2", 0.0)` calls degrade
    gracefully and no `person2` withdrawal/contribution paths ever execute).
  - `_normalized_household_rmd_shares()` — early-return `{"person1": 1.0}` when
    `household_type == "single"`, skip the two-person share math entirely.
  - RMD, contribution, and surplus routing loops that iterate `RETIREMENT_OWNER_KEYS` need
    to iterate a resolved `owner_keys = ("person1",) if single else ("person1", "person2")`
    tuple instead of the current hardcoded module-level constant.

### 3. Tax-phase changes (`src/tax_model.py`)

- `_tax_phase()` gains a `household_type` parameter. When `"single"`, always return one of
  `{"pre_retirement", "retirement"}` — the `one_deceased` parameter is not applicable and
  should not be passed/read for single households (the EndOfPlan event for `person1` ends
  the simulation, not a phase transition).
- `resolve_tax_system()` / `resolve_state_tax_system()` — filing status defaults
  (`DEFAULT_TAX_FILING_STATUS`) need a `"single"` household path that defaults to filing
  status `"single"` instead of `"married_joint"` for both pre-retirement and retirement
  phases (this is also a natural intersection point with the state-tax-schedule plan, since
  filing status selection feeds directly into bracket lookup for both federal and state).

### 4. Spending / withdrawal policy changes

- `resolve_survivor_spending()` and the `survivor_cash_target` / `survivor_withdrawal_order`
  / `survivor_surplus_order` resolution in `resolve_withdrawal_policy()` (`model.py` ~L1149)
  should never be invoked for single households — guard at the call site, not inside these
  functions (keeps the functions' existing couple-household contract unchanged).
- `validate_scenario()` should emit a **warning** (not error) if a single-household scenario
  sets `survivor_*` fields — most likely a copy-paste leftover from a couple template, worth
  flagging but not worth failing validation over.

### 5. EndOfPlan / event synsynthesis

- `_sync_end_of_plan_years()`, `_resolve_retirement_events()`, `_resolve_social_security_events()`
  all key off `config[str(event["person"])]` for a `person` field on `[[events]]` entries.
  These already tolerate a missing person key gracefully (`config.get(str(...), {})`) — verify
  this during implementation, but no design change appears necessary here; single-household
  scenarios simply never declare events with `person = "person2"`.

### 6. UI changes (`templates/setup_panel.html`)

- Add a "Household Type" control (radio or toggle) near the People section, wired the same
  way the Data Source radio (`ds_mode`) already toggles tab visibility — precedent:
  `setAccountsTabVisibility()` / `setManualSetupTabVisibility()` added 2026-07-04.
- When `household_type = "single"`: hide the entire Person 2 row (not just gray it out —
  hidden, per the validation rule that `[person2]` must be absent, not zeroed).
- `updatePersonLabels()`, `collectSyntheticData()` (if applicable), and the quick-controls
  save payload (`_QUICK_CONTROL_MAP`) all need a single-household branch that omits
  `person2_name` / `person2_retirement_year` / etc. from the save payload entirely — tomlkit
  writes must not silently create an empty `[person2]` table.
- **Naming debt to fix opportunistically:** the field id `person2_retirement_year` is a leaked
  Person 1-household-specific name inside otherwise-generic markup (`person1_retirement_year`
  has the same issue). Both should be renamed to `person1_retirement_year` /
  `person2_retirement_year` as part of this work, since the single-person UI branch touches
  this exact code anyway. Confirm no other code (JS or Python backend) depends on the old
  field names before renaming — `grep -rn "person1_retirement_year\|person2_retirement_year"`.

### 7. Starter template

- Restore a real single-person path in `scenarios/starter.toml`, but correctly this time:
  add `household_type = "single"` as a commented-out alternative near `[scenario]`, and
  make the `[person2]` section's comment accurate: *"Delete this entire section AND set
  `household_type = \"single\"` above if modeling one person — deleting this section alone
  will fail validation."*
- Consider adding a second template, `scenarios/starter-single.toml`, pre-configured for
  the single-person path, so single users don't have to perform template surgery themselves.

---

## Phased Implementation

| Phase | Scope | Depends on |
|---|---|---|
| 1 — Engine core | `household_type` config field, validation rule, `_run_projection_yearly()` branch, `_initial_retirement_owner_state()` / RMD-share single-person paths | — |
| 2 — Tax phase | `_tax_phase()` single-person branch, filing-status defaults for single | Phase 1 |
| 3 — Withdrawal/spending | Guard survivor-policy resolution at call sites, validation warning for stray `survivor_*` fields | Phase 1 |
| 4 — Setup Panel UI | Household Type control, Person 2 row hide/show, save-payload branch, `person1_retirement_year`/`person2_retirement_year` rename | Phase 1 (needs stable config shape) |
| 5 — Starter templates | Fix `starter.toml` comment/example, optionally add `starter-single.toml` | Phases 1-4 |
| 6 — Tests | Unit tests for single-person `_run_projection_yearly()` end-to-end (deterministic mode at minimum), validation tests for the new `household_type`/`person2`-presence rule | Phases 1-3 |

Each phase should ship independently and be individually re-rendered/verified against a
live single-person test scenario before moving to the next — consistent with this
project's "one issue at a time, confirm before moving on" collaboration rule.

## Verification Plan

1. Create a real (not deleted-and-restored) single-person test scenario using the Phase 5
   template, with `household_type = "single"` and no `[person2]` section.
2. Run `run.py --scenario <slug>` for all three render modes (deterministic, historical,
   Monte Carlo) — must complete without exception.
3. Confirm the rendered Accounts/Cash Flow/Tax tabs show no `person2`-labeled rows or
   `$0.00`-everywhere columns (a stubbed-zero approach, if accidentally reintroduced, would
   show a spurious "Person 2" row full of zeros — that's the visible symptom of Option A
   creeping back in).
4. Confirm no `survivor` tax phase ever appears in the `tax_phase` DataFrame column for the
   single-person scenario.
5. Confirm `validate_scenario()` rejects a `household_type = "single"` scenario that still
   has `[person2]` present, with a clear error message.
6. Confirm every existing two-person scenario TOML (`default.toml`, `comfortable.toml`,
   etc.) still renders identically before/after this change (no `household_type` field
   needed on them — implicit `"couple"` default).

## Open Questions for Person 1

- Should `household_type` default to `"single"` or `"couple"` when completely unset AND
  `[person2]` is absent (for a *new* scenario that never declares the field at all)? This
  plan assumes `"couple"` remains the default for backward compatibility, meaning a brand
  new scenario that forgets to declare `household_type` and omits `[person2]` still fails
  validation with a clear message — is that acceptable, or should absence-of-`[person2]`
  auto-imply `household_type = "single"` for new (undeclared) scenarios specifically?
- Is a dedicated `starter-single.toml` worth the maintenance (Phase 5, optional) or is
  documenting the `household_type` toggle in the existing `starter.toml` sufficient?
