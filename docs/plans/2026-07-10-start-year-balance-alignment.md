# Plan: Auto-align start_year with Balance Data As-Of Date

**Status:** Reviewed and refined
**Date:** 2026-07-10
**Assessment by:** Codex (Hermes Agent)
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
CSV Import             Monarch Sync              Offline / Cache
  parse_csv()            monarch_bridge.fetch      load_cache()
    ↓                      ↓                         ↓
  {name, balance, date}   balance data (now)        cache_timestamp
    ↓                      ↓                         ↓
  build_csv_starting...   classify_accounts()       (no date in data itself)
    ↓                      ↓                         ↓
  └──────────────────┬──────────────────────────────┘
                     ↓
              run_projection_result(balances, config, data_as_of=...)
                     ↓
              _run_projection_yearly()
                     ↓
              1. Clamp start_year = max(config_start, data_as_of_year)
              2. Log clamp message
              3. Scan events, list any that fall before clamped year
              4. Store clamped start_year in result metadata
              5. Enter year loop
```

Three data-source paths surface `data_as_of`:
1. **CSV Import** — latest date across all accounts from `parse_csv()`
2. **Monarch Sync** — current date at fetch time ("now")
3. **Offline / Cache** — `cache_timestamp` from `balances_cache.json`
4. **Synthetic mode** — no date; `data_as_of = None` (no clamp)

---

## Assessment Gaps Incorporated

The original draft was reviewed against current code. The following gaps were identified and are reflected in this version:

| # | Gap | Original | Fix incorporated |
|---|-----|----------|-----------------|
| A1 | **No offline/cache path** | Only covered CSV and Monarch | Cache timestamp (`balances_cache.json` → `cache_timestamp`) is now the third `data_as_of` source. `load_cache()` inconsistency (`"timestamp"` key vs actual `"generated_at"`/`"cache_timestamp"` keys) also cleaned up. |
| A2 | **No synthetic mode handling** | Not mentioned | Explicit `None`-safe handling throughout. `data_as_of = None` → no clamp. |
| A3 | **7-tuple is fragile** | Proposed 7th return value for `build_csv_starting_inputs()` | Instead of expanding the tuple, `parse_csv()` now exposes a helper function `last_csv_data_date()` that returns the max date across parsed entries. Zero-tuple-impact. |
| A4 | **Wrong entry-point function** | Targeted `_run_projection_yearly()` | `data_as_of` parameter goes on `run_projection_result()` (the public API), which passes it through. |
| A5 | **Event misalignment under-mitigated** | Only a text message | Clamp code now scans all enabled events and lists any with `year < clamped_start_year` in the warning banner. |
| A6 | **UI feedback path vague** | No concrete mechanism | The clamped `start_year` is stored in `ProjectionResult.summary["data_as_of_clamped"]` and `summary["clamped_start_year"]`. Render job wrappers inspect these fields to produce UI banners. |
| A7 | **`ProjectionResult` lacks `start_year`** | Not addressed | `ProjectionResult` gains `clamped_start_year: int | None` field. The chart and downstream consumers use this when set, falling back to config. |

---

## Detailed Changes

### Phase 1: Surface `data_as_of` from all import paths

#### `csv_importer.py`

- `parse_csv()` already returns per-entry `date`. Add a helper function:
  ```python
  def last_csv_data_date(entries: list[dict]) -> datetime.date | None:
      """Return the latest date across all CSV entries, or None if empty."""
  ```
- `build_csv_starting_inputs()` stays a 6-tuple — no signature change. Callers that need `data_as_of` call `last_csv_data_date()` on the raw CSV entries independently.

#### `monarch_bridge.py`

- `fetch_raw_accounts()` already has an implicit "now" timestamp. At the call site in `run.py`, record `datetime.now().date()` at the time of Monarch fetch:
  ```python
  monarch_fetch_date = datetime.now().date()
  raw_accounts = monarch_bridge.fetch_raw_accounts()
  ```
  This date becomes the `data_as_of` for the Monarch path.

#### `run.py` — offline (cache) path

- `load_cache()` returns the full cache dict, which has `cache_timestamp` (e.g. `"2026-07-04T22:00:54.912278"`). Parse this to a `date` and surface it alongside the balances.

- **Also fix the `load_cache()` display bug:** the current code reads `data.get("timestamp", "unknown")` but the cache file uses `"cache_timestamp"`. Change to:
  ```python
  ts = data.get("cache_timestamp", data.get("generated_at", "unknown"))
  ```

#### `run.py` — synthetic mode

- `_synthetic_inputs_from_config()` has no date. The caller in `run.py` passes `data_as_of=None`.

### Phase 2: Clamp `start_year` at render

#### `model.py` — `run_projection_result()`

Add an optional `data_as_of: date | None = None` parameter. Before dispatching to `_run_projection_yearly()`:

```python
def run_projection_result(
    balances: dict[str, float],
    ...,
    data_as_of: date | None = None,   # NEW
    config: dict | None = None,
) -> ProjectionResult:
    config = resolve_runtime_config(config or load_config())
    start_year = int(config["simulation"]["start_year"])
    clamp_enabled = config.get("simulation", {}).get("clamp_start_year", True)
    clamped_start_year = start_year

    if data_as_of is not None and clamp_enabled:
        as_of_year = data_as_of.year
        if as_of_year > start_year:
            clamped_start_year = as_of_year
            print(f"Note: Balance data is from {as_of_year}. "
                  f"Projection start adjusted from {start_year} to {as_of_year}.")

            # Scan events that fall before the clamped year
            events = [e for e in config.get("events", [])
                      if e.get("enabled", False)]
            pre_clamp = [e for e in events
                         if isinstance(e.get("year"), int) and e["year"] < as_of_year]
            if pre_clamp:
                labels = ", ".join(e.get("label", str(e.get("year", "?")))
                                   for e in pre_clamp)
                print(f"  Note: {len(pre_clamp)} event(s) before {as_of_year} "
                      f"will not appear: {labels}")

    # Override the config start_year for the downstream call
    config["simulation"]["start_year"] = clamped_start_year
```

#### `model.py` — `_run_projection_yearly()`

No signature change. It already reads `sim["start_year"]` from config (line ~3105). The clamp happens upstream in `run_projection_result()`.

#### `model.py` — `ProjectionResult`

Add the field:
```python
@dataclass
class ProjectionResult:
    mode: str
    yearly_df: pd.DataFrame
    summary: dict[str, object]
    simulation: dict[str, object]
    band_df: pd.DataFrame | None = None
    outcomes_df: pd.DataFrame | None = None
    run_count: int = 1
    display_path_kind: str = "deterministic"
    clamped_start_year: int | None = None   # NEW
```

Store the clamped value in `summary`:
```python
summary["data_as_of_clamped"] = clamped_start_year != start_year
summary["clamped_start_year"] = clamped_start_year
```

### Phase 3: UI feedback (Setup Panel)

When a render job completes and the clamp fired, surface a visible message.

**Mechanism:** The render job wrapper (in `admin_app.py`) captures `run.py --offline` stdout. After the subprocess completes, it parses the note lines (`Note: Balance data is from...`). Those are stored in the render job's `detail` field, which the frontend polls and displays in the async render overlay.

For the Setup Panel:
- The overlay polling JS (`updateOverlayFromJob`) already surfaces `job.detail`. Add a yellow info banner style when `detail` contains "Projection start adjusted":
  ```javascript
  var hintEl = document.getElementById('render-hint');
  if (job.detail && job.detail.indexOf('Projection start adjusted') >= 0) {
    hintEl.innerHTML = '<div class="clamp-notice">⚠️ ' + job.detail + '</div>';
  }
  ```
- For CLI runs, the console message alone serves as feedback.

### Phase 4: Opt-out escape hatch

`[simulation].clamp_start_year` — controls whether the auto-clamp runs:

```toml
[simulation]
start_year = 2026
end_year = 2066
clamp_start_year = true   # default: true (auto-clamp enabled)
```

When `false`, the old behavior applies: balance data is used at the configured `start_year` regardless of its as-of date. Synthetic scenarios can leave this `true` harmlessly since `data_as_of` is `None` — the clamp only fires when a non-None date is provided.

### Phase 5: Add `clamp_start_year` to definitions page

Add an entry to `definitions.html`:

> **`clamp_start_year`** (boolean, optional, default `true`): When `true` and the balance data has a known "as of" date newer than `start_year`, the projection start is automatically moved forward to the data's year. Events before that year are excluded. Set to `false` to disable this behavior.

---

## Files to touch

| File | Change |
|------|--------|
| `src/csv_importer.py` | Add `last_csv_data_date()` helper. No tuple changes. |
| `src/monarch_bridge.py` | (No change needed — caller records date) |
| `src/model.py` | Add `data_as_of` param to `run_projection_result()`, clamp logic, event scan, `ProjectionResult.clamped_start_year`, store in `summary`. |
| `run.py` | Surface `data_as_of` from all 3 paths (Monarch, cache, synthetic). Fix `load_cache()` timestamp key. |
| `admin_app.py` | Pass `data_as_of` into render jobs. Parse clamp messages from stdout for UI. |
| `templates/setup_panel.html` | Yellow banner in render overlay when clamp fires. |
| `src/definitions_page.py` | Add `clamp_start_year` parameter entry. |
| `scenarios/*.toml` | (None — clamp is render-time only, no config change needed) |

---

## What this does NOT do

- Does **not** shift income/wage values — if the user's `annual_take_home` was configured for 2026 and the start_year is now 2030, that income is still applied starting at 2030. This is a separate concern.
- Does **not** store history — only the latest balance snapshot matters. Historical progression between original start_year and data_as_of year is invisible.
- Does **not** persist the config change — the TOML file stays untouched. `clamp_start_year` is the only new config field, and it's a boolean toggle, not a date.

---

## Risks

- **Silent data loss (mitigated):** Years between original start_year and data_as_of year are dropped from the chart. UI banner and CLI message always show when this happens. Pre-clamp events are listed explicitly.
- **Income/contribution/year-based events misalign (mitigated):** Pre-clamp events are listed in the warning. Income amounts still apply at the adjusted start year — the warning recommends checking income/contribution settings.
- **Race condition on cache timestamp:** If the cache was written months ago and the user runs offline, the cache's `cache_timestamp` is the data source's "as of" date. This is correct behavior — the cache was the last snapshot.

---

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

---

## Acceptance Criteria

- [ ] `parse_csv()` exposes a `last_csv_data_date()` helper returning the latest date across all entries
- [ ] Monarch fetch path records fetch date as `data_as_of` at call site in `run.py`
- [ ] `load_cache()` surfaces `cache_timestamp` as `data_as_of`; fixes the `"timestamp"` vs `"cache_timestamp"` key bug
- [ ] Synthetic mode produces `data_as_of=None` — no clamp
- [ ] `run_projection_result()` accepts optional `data_as_of` and clamps `start_year` when `data_as_of.year > config_start_year`
- [ ] Clamp fires for all 3 paths: CSV, Monarch, offline cache
- [ ] Console message shown when clamp occurs, listing pre-clamp events
- [ ] `ProjectionResult.summary` stores `data_as_of_clamped` and `clamped_start_year`
- [ ] `ProjectionResult.clamped_start_year` field populated
- [ ] UI banner in render overlay when clamp fires
- [ ] `[simulation].clamp_start_year = false` escape hatch works
- [ ] `clamp_start_year` entry added to definitions page
- [ ] Existing tests pass with no behavior change when `data_as_of` is absent
