# Plan: Auto-align start_year with Balance Data As-Of Date

**Status:** Draft
**Date:** 2026-07-10
**Related:** Balance-update callout confusion in README (resolved textually, behavior unchanged)

---

## Problem

The model always starts its projection at the configured `start_year` and uses the user's balance data as the starting point — regardless of when that data was actually captured. If `start_year` is 2026 and the user imports balances from 2030, those 2030 numbers are treated as the 2026 starting point, producing a projection that double-counts 4 years of growth it shouldn't have.

Currently, nothing warns the user about this. The README callout now advises keeping `start_year` aligned with latest data, but the app itself doesn't enforce or even hint at the mismatch.

## Goal

When a user imports fresh balance data (CSV or Monarch), the projection should use that data as the current-year starting point — not as the `start_year` starting point years in the past.

## Approach: Auto-clamp `start_year` at Render Time

The simplest correct fix: **at the moment of rendering, if the balance data has a known "as of" date, clamp `start_year` forward to match.**

### Where the data flows

```
CSV Import             Monarch Sync
  parse_csv()            monarch_bridge.fetch_raw_accounts()
    ↓                      ↓
  {name, balance, date}   balance data (no explicit date, but "now")
    ↓                      ↓
  build_csv_starting_inputs()   classify_accounts() + extract_*
    ↓                      ↓
  run_projection(balances, config)
    ↓
  start_year = config["simulation"]["start_year"]
  portfolio = {taxable, trad_ira, roth, cash}  # from balances dict
  for year in range(start_year, end_year + 1):
    ...
```

Three touch points:

1. **CSV Import** — `parse_csv()` already knows the latest date per account. Surface the maximum of those dates as a `data_as_of` value that survives through to `build_csv_starting_inputs()`.

2. **Monarch Sync** — No explicit date, but the fetch happens "now". Use the current date at fetch time as `data_as_of`.

3. **Render (`_run_projection_yearly()` or `run.py`)** — Before entering the year loop, if `data_as_of_year > start_year`, clamp `start_year = data_as_of_year` and log the adjustment. Don't persist the change to the TOML — this is a render-time clamp only, preserving the user's explicit config.

### Detailed changes

#### Phase 1: Surface `data_as_of` from import paths

**`csv_importer.py`:**
- `parse_csv()` already returns `date` per entry. Export it: change return shape or add a parallel return value so the caller knows the latest date across all accounts.
- `build_csv_starting_inputs()` currently returns a 6-tuple `(portfolio, extras, liability_balances, property_values, retirement_owner_balances, basis_seeds)`. Add a 7th return value: `data_as_of: date | None`.
- Callers in `run.py` and `admin_app.py` (CSV save endpoint) need to handle the new return value.

**`monarch_bridge.py`:**
- `fetch_raw_accounts()` knows when it ran. Surface `data_as_of` as today's date.
- Or at `run.py` level: record `datetime.now().date()` at the time of Monarch fetch and pass it alongside the balances.

**`sqlite approach` (not taken right now):**
- Don't store `data_as_of` in the TOML config or in a separate cache file yet. Keep it as a runtime-only value for now. This keeps Phase 1 simple.

#### Phase 2: Clamp `start_year` at render

**`run.py` (or `_run_projection_yearly()`):**
- Accept an optional `data_as_of: date | None` parameter.
- If `data_as_of` is provided and `data_as_of.year > start_year`, issue a console message:
  ```
  Note: Balance data is from 2030. Projection start adjusted from 2026 to 2030.
  ```
- Set `start_year = data_as_of.year` before entering the year loop.

**What this means for the projection:**
- The chart now starts at `data_as_of.year`, not the user's configured `start_year`.
- All years between the original `start_year` and `data_as_of.year` are silently dropped.
- Income/wage values keyed to the original `start_year` still apply at the adjusted start year — the user may need to adjust them too.

#### Phase 3: UI feedback (Setup Panel)

When the user saves or renders via the Web UI and a `start_year` clamp happens, surface a visible message:

- **Async render modal:** Show a yellow info banner: *"Start year adjusted from 2026 to 2030 to match imported balance data. Verify your income and contribution settings reflect the correct current year."*
- **Standalone render (`run.py`):** The console message above serves this role.

#### Phase 4: Optional — Allow the user to opt out

A user may legitimately want to run a what-if simulation that starts in 2020 using today's balances. Provide an escape hatch:

- `[simulation].clamp_start_year = false` (default: `true`)
- When `false`, the old behavior applies: balances are used as the `start_year` starting point regardless of their as-of date.

### Files to touch

| File | Change |
|------|--------|
| `src/csv_importer.py` | Surface latest date from `parse_csv()`; add 7th return value to `build_csv_starting_inputs()` |
| `src/monarch_bridge.py` | Surface `data_as_of` from fetch path |
| `src/model.py` (`_run_projection_yearly()` or `run_projection_result()`) | Accept `data_as_of` param, clamp `start_year` |
| `run.py` | Pass `data_as_of` from CSV/Monarch/offline paths into model call |
| `admin_app.py` (render endpoints) | Pass `data_as_of` into async render jobs |
| `templates/setup_panel.html` | Show UI feedback when clamp occurs |

### What this does NOT do

- Does **not** shift income/wage values — if the user's `annual_take_home` was configured for 2026 and the start_year is now 2030, that income is still applied starting at 2030. This is a separate concern.
- Does **not** store history — only the latest balance snapshot matters. Historical progression between original start_year and data_as_of year is invisible.
- Does **not** persist the config change — the TOML file stays untouched.

### Risks

- **Silent data loss:** Years between original start_year and data_as_of year are dropped from the chart without the user noticing if the UI feedback is missed. Mitigation: always show a visible message, and make the opt-out escape hatch well-documented.
- **Income/contribution/year-based events misalign:** The user's income, retirement year, Social Security start age, and events with absolute years all reference the original timeline. Clamping start_year forward without adjusting those creates a different kind of mismatch. Mitigation: the UI message should explicitly mention this.

## Alternative: Store Historical Balance Snapshots (Not Recommended Now)

Instead of clamping start_year, the model could store a sequence of balance snapshots over time:

```toml
[balance_history]
"2026-01-15" = { taxable = 50000, trad_ira = 100000, roth = 30000, cash = 40000 }
"2027-01-15" = { taxable = 55000, trad_ira = 110000, roth = 35000, cash = 42000 }
```

At render time, the model would use known historical balances for past years (interpolating or using the nearest snapshot) rather than projecting through them. This is more intellectually honest — the model would *know* what happened in 2026–2029 rather than *project* from a 2030 starting point.

**Why not now:**
- Requires a new config section, a cache file format, or both
- Touches the core simulation loop (which currently assumes year-0 is the only input point)
- CSV import would need to carry forward *all* historical rows, not just the latest per account
- Monarch sync would need to store snapshots over time (or rely on CSV export history)
- This is a V2 feature, not a quick fix

## Acceptance Criteria

- [ ] `parse_csv()` surfaces the latest date across all accounts
- [ ] Monarch fetch path surfaces fetch date as `data_as_of`
- [ ] `_run_projection_yearly()` accepts optional `data_as_of` and clamps `start_year`
- [ ] Console message shown when clamp occurs (CLI run)
- [ ] UI banner shown when clamp occurs (Web UI render)
- [ ] `[simulation].clamp_start_year = false` escape hatch works
- [ ] Existing tests pass with no behavior change when `data_as_of` is absent
