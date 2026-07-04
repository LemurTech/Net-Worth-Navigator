# State-by-State Tax Schedule Support — Design Plan

> **Status:** Proposed. Not started.
> **See also:** `src/tax_model.py`, `src/oregon_tax_2025.py`, `config/tax_tables/2025_us_federal_oregon.toml`, `src/config_loader.py`

**Goal:** Let a household in any US state configure accurate state income tax treatment,
instead of the current single-state (Oregon) hardcoded implementation that silently produces
$0 state tax for every other state.

**Non-goal:** This plan does not attempt full generality (all 50 states + DC + territories,
every state's specific quirks — e.g. states with no income tax, states that tax Social
Security, states with local/county income tax on top of state tax, states with special
retirement-income exclusions). It defines an extensible architecture and ships a first
useful slice (a config-driven progressive-bracket engine plus 2-3 states as proof, prioritized
by NWN's likely user base), not a complete 50-state tax database in one pass.

**Why this matters:** Flagged alongside single-person household support (see
`docs/plans/2026-07-04-single-person-household-support.md`) as one of two gaps blocking NWN
from being useful to a wider audience beyond Person 1's own Oregon household. Right now,
anyone outside Oregon who enables `[taxes.state].enabled = true` silently gets $0 state tax
with no warning — a correctness bug disguised as a missing feature.

---

## Current State (evidence from the codebase)

`src/tax_model.py::resolve_state_tax_system()`:

```python
def resolve_state_tax_system(config, *, filing_status):
    state = config.get("taxes", {}).get("state", {})
    if not state.get("enabled"):
        return StateTaxSystem()

    state_name = str(state.get("name", "")).strip().lower()
    ...
    if state_name == "oregon":
        return StateTaxSystem(enabled=True, name="oregon", ...)

    return StateTaxSystem()   # ← any other state name silently gets a disabled/no-op system
```

And the tax calculation site (`_calculate_state_taxes`, ~L279):

```python
if state_tax_system.name != "oregon":
    return 0.0, 0.0, 0.0
```

Oregon's actual bracket/table data lives in `src/oregon_tax_2025.py` as two Python literals:
`OREGON_2025_TAX_TABLE` (the low-income lookup table from the OR-40 instructions) and
`OREGON_2025_RATE_CHARTS` (the Chart S / Chart J formulas for income above $50K). The
calculation itself, `calculate_oregon_state_tax()`, is Oregon-specific: it hardcodes the
$50,000 low-income-table cutoff and the two-tier chart-based formula that Oregon's actual
OR-40 instructions use — this specific bracket structure is Oregon's own quirk, not a
generic progressive-bracket shape.

Compare to how **federal** brackets are handled: `calculate_progressive_tax()` is fully
generic — it takes a `brackets: list[dict]` of `{up_to, rate}` and a `standard_deduction`,
with no state-specific logic. The federal brackets themselves live in
`config/tax_tables/2025_us_federal_oregon.toml` as pure data (`[[taxes.brackets.single]]`,
`[[taxes.brackets.married_joint]]`), loaded through the existing shared config-loader
(`src/config_loader.py`) that merges scenario TOML + `config/tax_tables/*.toml`.

**Key finding: the federal path already has the right architecture. The state path does
not use it — it duplicates a state-specific special case instead of reusing the generic
bracket engine.** Most US states with income tax use a straightforward progressive-bracket
structure (like federal) that `calculate_progressive_tax()` already models correctly. Oregon
is actually the unusual case (low-income lookup table below $50K, chart formula above) —
building the *general* architecture around Oregon's specific quirk was the original design
mistake this plan corrects.

---

## Design

### 1. Generalize the state tax data shape to match the federal one

Add a `[taxes.state.brackets.<filing_status>]` array-of-tables, identical in shape to the
existing `[taxes.brackets.<filing_status>]` federal ones:

```toml
[taxes.state]
enabled = true
name = "california"
tax_social_security = false   # states vary; CA excludes SS from state tax

[taxes.state.standard_deduction]
single = 5540
married_joint = 11080

[[taxes.state.brackets.single]]
up_to = 10756
rate = 0.01

[[taxes.state.brackets.single]]
up_to = 25499
rate = 0.02

# ... etc, terminal bracket omits `up_to` (matches existing federal convention)
```

This lets `resolve_state_tax_system()` call the **existing** `calculate_progressive_tax()`
for any state whose tax system is a plain progressive bracket table — which covers the
large majority of states with income tax (e.g., California, New York, most others).
No new calculation code is needed for these states; only new *data*.

### 2. Keep Oregon's special-case engine, but as a named implementation, not the only path

Oregon's low-income-table + two-tier chart approach doesn't fit the generic bracket shape.
Rather than force-fitting it (which would risk breaking the already-verified-against-OR-40
Oregon numbers), keep `calculate_oregon_state_tax()` and `oregon_tax_2025.py` as-is, but
register it behind a `state_tax_engine` selector instead of a hardcoded `if name ==
"oregon"` string check:

```python
STATE_TAX_ENGINES = {
    "oregon": calculate_oregon_state_tax,          # existing OR-40-table-based special case
    # states below this line use the generic progressive engine directly —
    # no entry needed here, `resolve_state_tax_system` falls through to
    # calculate_progressive_tax() when brackets are present and no named
    # engine is registered.
}
```

This is the extensibility seam: a future state with its own non-bracket quirk (e.g., a flat
tax with a specific credit structure) gets a named function added to this dict, while every
"just a progressive bracket table" state needs zero new Python code — only a new
`config/tax_tables/<state>.toml`-shaped data block. This mirrors the plugin/provider
pattern this codebase already uses elsewhere (model-provider plugins registering by name)
rather than inventing a new extension mechanism.

### 3. No-income-tax states

Nine states have no state income tax (Alaska, Florida, Nevada, New Hampshire — dividends/
interest only historically, South Dakota, Tennessee, Texas, Washington, Wyoming). These
need an explicit `"none"` entry (not just "no brackets configured," which should remain a
validation error to avoid silently producing $0 for a *misspelled* state name — the exact
bug this plan fixes for the *existing* unlisted-state case).

```toml
[taxes.state]
enabled = true
name = "texas"
# no [taxes.state.brackets.*] needed; "texas" is in the KNOWN_NO_INCOME_TAX_STATES set
```

### 4. Validation

`validate_scenario()` (`src/model.py`) should be extended to check, when
`[taxes.state].enabled = true`:
- `name` is either in `KNOWN_NO_INCOME_TAX_STATES`, has a registered `STATE_TAX_ENGINES`
  entry, OR has a non-empty `[taxes.state.brackets.<filing_status>]` table for the
  scenario's resolved filing status(es).
- If none of the above match, **fail validation with a clear error** — e.g. *"Unknown state
  'foo' in [taxes.state].name — add bracket data to
  config/tax_tables/<year>_<state>.toml or set name to a supported/no-tax state."* This
  directly closes the silent-$0 bug: today an unsupported/misspelled state name produces no
  error and no state tax, which is indistinguishable from a correctly-configured no-tax
  state. After this change, only an intentional `"none"`/known-no-tax-state name produces
  $0 state tax; anything else either calculates real tax or fails loudly.

### 5. Data sourcing and file organization

Each state gets its own tax-table TOML under `config/tax_tables/`, following the existing
`<year>_<jurisdiction>.toml` naming convention already used for
`2025_us_federal_oregon.toml`. Splitting is recommended: separate the state block out of
that combined file into its own `2025_oregon_state.toml` (federal brackets stay in a
`2025_us_federal.toml`), so a household can mix "current-year federal + any state" without
the combined-file naming implying a fixed state pairing. This is a refactor of the existing
file, not new architecture — `config_loader.py`'s merge behavior should be confirmed to
support loading two separate tax-table files (federal + state) instead of one combined file
before this split is finalized.

**Data source per state:** each state's department of revenue current-year individual
income tax bracket/standard-deduction publication (analogous to how `oregon_tax_2025.py`
cites the OR-40 instructions). This is manual data entry work, not something to scrape
automatically — tax brackets change year to year and must be sourced from an authoritative
publication, one state at a time.

### 6. UI (Setup Panel)

Currently `templates/setup_panel.html` has **zero** exposure of `[taxes.state]` — it's a
raw-TOML-only concern today. Recommended for this plan:
- Add a state dropdown (populated from whatever states have registered tax-table data,
  plus a "no state income tax" and "not configured / effective-rate fallback" option) to
  the quick-edit panel's Assumptions section, alongside the existing `effective_tax_rate_*`
  fields it currently exposes.
- This is deliberately scoped as **Phase 3** (see below) — the engine/data work must land
  first, and the UI should only offer states that actually have real bracket data behind
  them (no dropdown entry should be able to silently produce the effective-rate fallback
  the user didn't ask for).

---

## Phased Implementation

| Phase | Scope | Depends on |
|---|---|---|
| 1 — Generic engine wiring | `STATE_TAX_ENGINES` registry, `KNOWN_NO_INCOME_TAX_STATES` set, `resolve_state_tax_system()` rewritten to try (a) named engine, (b) generic bracket table, (c) known-no-tax passthrough, (d) validation failure — in that order. Oregon's existing behavior must be verified byte-identical before/after (regression risk: Oregon is the only state currently exercised by real scenario data). | — |
| 2 — First new states' data | Pick 2-3 states based on likely NWN user geography (candidates: California, Washington [no income tax — cheap first proof of the no-tax path], a third bracket-based state). Each is pure TOML data + a validation test asserting known bracket outputs at a few reference income levels. | Phase 1 |
| 3 — Validation hardening | Extend `validate_scenario()` with the unknown-state-name failure case described above. | Phase 1 |
| 4 — Setup Panel UI | State dropdown in Assumptions section, sourced dynamically from whichever states have registered data (no hardcoded UI list to keep in sync manually). | Phases 1-3 |
| 5 — Config file split (optional, can be deferred) | Split `2025_us_federal_oregon.toml` into separate federal/state files; verify `config_loader.py` merge behavior first. | Phase 1 |

## Verification Plan

1. **Regression baseline:** before any change, capture Oregon tax output (a few representative
   `taxable_income` values across both the low-income-table and chart-formula ranges) from
   `calculate_oregon_state_tax()` directly. After Phase 1, re-run the same inputs through the
   new `resolve_state_tax_system()` → engine-dispatch path and confirm byte-identical results.
2. For each newly added state (Phase 2), cross-check calculated tax at 2-3 reference income
   levels against that state's published tax tables/calculators (e.g. the state's own DOR
   withholding calculator, at zero withholding adjustments, as an approximate cross-check —
   not a substitute for citing the primary bracket source in the TOML file's comments, same
   convention as `oregon_tax_2025.py`'s citation of the OR-40 instructions).
3. Confirm a scenario with an unsupported/misspelled state name fails `validate_scenario()`
   with the new clear error, both via CLI (`run.py`) and the Setup Panel's Validate button
   API endpoint (`GET /api/validate-scenario`).
4. Confirm a no-income-tax state (e.g. Texas) produces exactly $0 state tax **and** passes
   validation — distinguishing this from the silent-failure case it replaces.
5. Re-render all existing personal scenario TOMLs (Oregon-based) and confirm output is
   unchanged from before this work — this is the most important regression check, since
   Oregon is Person 1's live scenario data.

## Open Questions for Person 1

- Which 2-3 states should be prioritized for Phase 2's initial data? (No signal yet on who
  else might use NWN outside Oregon — if this is purely a "make the architecture honest"
  pass with no near-term second user, Washington [no-tax, near-zero effort] + California
  [large population, clean bracket structure] are reasonable low-risk choices to prove the
  architecture without deep research investment.)
- Should states that tax Social Security differently (several do, with varying thresholds/
  exemptions) be handled in this same architecture pass, or deferred as a documented
  limitation per-state (similar to how federal SS taxability already has its own
  provisional-income logic that would need per-state variants)? Recommend deferring —
  scope creep risk — and documenting it as a known per-state limitation until a specific
  state's data work surfaces the need.
