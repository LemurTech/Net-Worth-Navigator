# Real-Dollar JS Toggle — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a client-side JavaScript toggle to the projection page that switches between nominal and real-dollar (inflation-adjusted) views without re-rendering.

**Architecture:** Embed both nominal and real-dollar data in the rendered HTML page. When `real_dollar_basis = true` in the scenario config, the render produces dual chart divs, dual KPI values, and `data-nominal` attributes on all monetary table cells. A toggle button switches visibility via CSS classes and a lightweight JS swap. localStorage persists the user's preference across page loads.

**Tech Stack:** Python (existing model/charts/tables), Plotly, vanilla JS, CSS

**Key constraint:** All changes are gated behind the existing `[simulation].real_dollar_basis = true` config switch. When `false`, the page renders identically to today — zero overhead.

---

## Architecture Overview

```
run_projection_result()
    └─ yearly_df (nominal, captured pre-deflation)
    └─ _apply_real_dollar_basis(yearly_df) → deflated yearly_df
    └─ ProjectionResult(yearly_df=deflated, nominal_yearly_df=nominal)

build_chart(projection_result)
    ├─ When real_dollar_basis=false: identical to today
    └─ When real_dollar_basis=true:
        ├─ KPI strip: dual <span> per monetary value
        ├─ Main chart: two divs (nwn-chart-nominal, nwn-chart-real)
        ├─ Tables: data-nominal attributes on all monetary cells
        ├─ Portfolio chart: dual divs
        ├─ Liabilities chart: dual divs
        ├─ Cash reserve chart + summary: dual divs + dual values
        └─ Segmented pill toggle + JS integrated in the value-basis badge bar
```

### What gets a dual representation

| Element | Approach | Why |
|---|---|---|
| KPI strip (4 values) | Dual `<span>` with CSS class | Only 4 monetary values; simple |
| Main chart | Two complete `fig.to_html()` divs | Trace structure differs (stacked areas); restyle is fragile |
| Portfolio chart | Two complete `fig.to_html()` divs | Same reason |
| Liabilities chart | Two complete `fig.to_html()` divs | Debt balance traces change |
| Cash reserve chart | Two complete `fig.to_html()` divs | Cash + target values change |
| Cash reserve summary | Dual `<span>` for target/minimum values | Few values |
| Tax summary card | Dual `<span>` for total taxes | Few values |
| All data tables | `data-nominal` attribute on each monetary `<td>` | 70%+ of cells don't change (years, rates, flags, strings); attribute approach avoids doubling table HTML |

### What does NOT get a dual representation

| Element | Why |
|---|---|
| Gantt timeline | No monetary values |
| Assumptions tab | Config values, not computed data |
| Scenario Parameters tab | Config values, not computed |
| Simulation tab (MC/historical) | Percentages already invariant to deflation; terminal values get data-nominal |
| Cash flow chart | Plotly, but all values are flow — needs dual div eventually; deferred to Task 13 |

---

## Tasks

---

### Task 1: Add `nominal_yearly_df` to `ProjectionResult`

**Objective:** Extend the dataclass to carry the pre-deflation DataFrame.

**Files:**
- Modify: `src/model.py`

**Step 1: Add field to dataclass**

At line ~201 in `src/model.py`, add after `clamped_start_year`:

```python
@dataclass
class ProjectionResult:
    # ... existing fields ...
    clamped_start_year: int | None = None
    nominal_yearly_df: pd.DataFrame | None = None   # pre-deflation copy
```

**Step 2: Capture nominal DataFrame in `run_projection_result()`**

In `run_projection_result()`, there are two call sites where `_apply_real_dollar_basis()` is called:

**Site A — deterministic path** (~line 3041):
```python
# BEFORE:
if simulation_settings.get("real_dollar_basis"):
    yearly_df = _apply_real_dollar_basis(yearly_df, config)

# AFTER:
nominal_yearly_df = None
if simulation_settings.get("real_dollar_basis"):
    nominal_yearly_df = yearly_df.copy()       # capture nominal
    yearly_df = _apply_real_dollar_basis(yearly_df, config)
```

**Site B — stochastic path** (~line 3123):
```python
# BEFORE:
if simulation_settings.get("real_dollar_basis"):
    run_frames = [_apply_real_dollar_basis(f, config) for f in run_frames]

# AFTER:
nominal_run_frames = None
if simulation_settings.get("real_dollar_basis"):
    # Save nominal copies before deflating
    nominal_run_frames = [f.copy() for f in run_frames]
    run_frames = [_apply_real_dollar_basis(f, config) for f in run_frames]
```

For the stochastic path, the nominal frames need to be reduced to a primary path (like `_build_primary_path_from_runs`) and stored. After `primary_df = _build_primary_path_from_runs(run_frames)` (which uses deflated frames), add:

```python
nominal_primary_df = None
if nominal_run_frames is not None:
    nominal_primary_df = _build_primary_path_from_runs(nominal_run_frames)
nominal_yearly_df = nominal_primary_df
```

**Step 3: Pass `nominal_yearly_df` into `ProjectionResult` constructor (deterministic path)**

Find the `ProjectionResult(...)` constructor call for deterministic mode and add `nominal_yearly_df=nominal_yearly_df`.

**Step 4: Pass `nominal_yearly_df` into `ProjectionResult` constructor (stochastic path)**

Do the same for the stochastic constructor call.

**Verification:**
```bash
cd /home/lemurtech/Net-Worth-Navigator
.venv/bin/python -c "
from src.model import run_projection_result, ProjectionResult
# Quick smoke test with sample scenario
from src.config_loader import load_config, resolve_runtime_config
config = resolve_runtime_config(load_config('scenarios/sample.toml'))
result = run_projection_result(
    {'cash': 40000, 'taxable': 150000, 'trad_ira': 300000, 'roth': 100000},
    home_value=500000,
    config=config
)
print(f'yearly_df shape: {result.yearly_df.shape}')
print(f'nominal_yearly_df is None: {result.nominal_yearly_df is None}')
if result.nominal_yearly_df is not None:
    # First non-zero net worth value should differ
    y0_nominal = result.nominal_yearly_df['total_net_worth'].iloc[0]
    y0_real = result.yearly_df['total_net_worth'].iloc[0]
    print(f'Year 0: nominal={y0_nominal:,.0f}, real={y0_real:,.0f}')
"
```

Expected: `nominal_yearly_df is None: False` (sample.toml has `real_dollar_basis = true`). The Year 0 values should be equal (no deflation at year 0), but later years should differ.

**Commit:**
```bash
git add src/model.py
git commit -m "feat: add nominal_yearly_df to ProjectionResult for dual-view render"
```

---

### Task 2: Extend `_fmt()` and `_fmt_currency()` with nominal value support

**Objective:** Add optional `nominal_val` parameter to table cell formatters so cells carry both nominal and real-dollar data.

**Files:**
- Modify: `src/tables.py`

**Step 1: Extend `_fmt()` (line ~33)**

```python
def _fmt(value: float, nominal_val: float | None = None) -> str:
    if pd.isna(value) or value == 0:
        return "<td class='zero'>—</td>"
    color = "neg" if value < 0 else ""
    data_attr = f" data-nominal='${nominal_val:>12,.0f}'" if nominal_val is not None else ""
    return f"<td class='{color}'{data_attr}>${value:>12,.0f}</td>"
```

**Step 2: Extend `_fmt_currency()` (line ~68)**

Only used in the tax summary, assumptions, and cash reserve summary — places where a formatted string (no `<td>` wrapper) is returned. Since these are wrapped in `<td>` or `<span>` by the caller, add a `data_nominal` return path or extend as needed:

```python
def _fmt_currency(value, nominal_val=None) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.0f}"
```

For now, `_fmt_currency` does not produce `<td>` elements directly — it returns plain strings. The data-nominal will be added at the call site (see Task 4).

**Verification:**
```bash
.venv/bin/python -c "
from src.tables import _fmt
print(_fmt(123456, nominal_val=125000))
# Should output: <td class='' data-nominal='$     125,000'>$     123,456</td>
print(_fmt(0))
# Should output: <td class='zero'>—</td>
"
```

**Commit:**
```bash
git add src/tables.py
git commit -m "feat: add nominal_val parameter to _fmt() table formatter"
```

---

### Task 3: Extend `_data_row()` to pass nominal values

**Objective:** The `_data_row()` helper calls `_fmt()` for each value. It needs to accept a parallel nominal values list and pass each through.

**Files:**
- Modify: `src/tables.py`

**Step 1: Add `nominal_values` parameter to `_data_row()` (~line 1047)**

```python
def _data_row(label: str, values: list[float], indent: bool = False,
              bold: bool = False, separator: bool = False,
              nominal_values: list[float] | None = None) -> str:
    cls_parts = []
    if indent:   cls_parts.append("indent")
    if bold:     cls_parts.append("total")
    if separator: cls_parts.append("sep")
    cls = " ".join(cls_parts)
    tag = "th" if bold else "td"
    cells = "".join(
        _fmt(v, nominal_val=(nominal_values[i] if nominal_values else None)).replace(
            "<td", f"<td data-col='{i+1}'"
        )
        for i, v in enumerate(values)
    )
    return f"<tr class='{cls}'><{tag} class='rowlabel'>{label}</{tag}>{cells}</tr>"
```

**Verification:**
```bash
.venv/bin/python -c "
from src.tables import _data_row
row = _data_row('Test', [100, 200], nominal_values=[105, 210])
print(row[:200])
# Should contain data-nominal='$       105' and data-nominal='$       210'
"
```

**Commit:**
```bash
git add src/tables.py
git commit -m "feat: pass nominal values through _data_row() for dual-view cells"
```

---

### Task 4: Update all table builders to accept and forward nominal values

**Objective:** Each `build_*_table()` function gets an optional `nominal_df` parameter. When provided, it extracts nominal values for each cell and passes them alongside the deflated values.

**Files:**
- Modify: `src/tables.py`

**Functions to update:**
- `build_accounts_table(df, config=None, nominal_df=None)` — ~line 1063
- `build_cashflow_table(df, config=None, nominal_df=None)` — ~line 1113
- `build_tax_table(df, nominal_df=None)` — check exact location
- `build_portfolio_table(df, config=None, nominal_df=None)` — check exact location
- `build_liabilities_table(df, config=None, nominal_df=None)` — check exact location

**Pattern for each table builder:**

The existing pattern is:
```python
years  = _display_years(df)
subset = df[df["year"].isin(years)].set_index("year")

def col(field: str) -> list[float]:
    return [subset.loc[y, field] if y in subset.index else 0.0 for y in years]
```

Add a parallel `col_nominal()` that extracts from `nominal_df`:
```python
nom_subset = nominal_df[nominal_df["year"].isin(years)].set_index("year") if nominal_df is not None else None

def col_nominal(field: str) -> list[float] | None:
    if nom_subset is None:
        return None
    return [nom_subset.loc[y, field] if y in nom_subset.index else 0.0 for y in years]
```

Then in every `_data_row()` call, pass both:
```python
# Before:
rows.append(_data_row("Traditional IRA / 401k", col("trad_ira"), indent=True))

# After:
rows.append(_data_row("Traditional IRA / 401k", col("trad_ira"),
                       indent=True, nominal_values=col_nominal("trad_ira")))
```

**Specifics for each table:**

- **Accounts table:** `trad_ira`, `trad_ira_person1`, `trad_ira_person2`, `roth`, `roth_person1`, `roth_person2`, `taxable`, `cash`, investable portfolio sum, `home_value`, mortgage (negated), `home_equity`, `total_net_worth` — all need nominal
- **Cash flow table:** income rows, spending rows, surplus rows — all monetary columns
- **Tax table:** monetary tax columns
- **Portfolio table:** investable account columns
- **Liabilities table:** `_build_liabilities_table` uses `_fmt()` and `_fmt_currency()` — needs nominal for balance and payment cells

**Verification:** Run the full build and inspect the output for `data-nominal` attributes on monetary cells.

```bash
.venv/bin/python run.py --scenario sample --offline
grep -c 'data-nominal' output/scenarios/sample/deterministic/projection.html
# Should return a positive number
```

**Commit:**
```bash
git add src/tables.py
git commit -m "feat: update all table builders to accept nominal_df for dual-view cells"
```

---

### Task 5: Dual KPI strip values

**Objective:** `_build_kpi_summary()` renders dual `<span>` elements for monetary values.

**Files:**
- Modify: `src/charts.py`

**Step 1: Add `nominal_df` parameter to `_build_kpi_summary()`**

```python
def _build_kpi_summary(
    config: dict,
    projection: pd.DataFrame | ProjectionResult,
    nominal_df: pd.DataFrame | None = None,
) -> str:
```

**Step 2: Compute nominal KPI values from `nominal_df`**

After the existing extraction of `first_row`, `last_row`, `retirement_row` from `df`, compute parallel nominal rows:

```python
    nominal_first_row = nominal_df.iloc[0] if nominal_df is not None else None
    nominal_last_row = nominal_df.iloc[-1] if nominal_df is not None else None
    nominal_retirement_row = None
    if nominal_df is not None and retirement_year is not None:
        match = nominal_df[nominal_df["year"] == retirement_year]
        if not match.empty:
            nominal_retirement_row = match.iloc[0]
```

**Step 3: Wrap monetary values in dual spans**

Replace the KPI value rendering. Currently:
```python
f"<div class='kpi-value'>{value}</div>"
```

For monetary values (when `nominal_df` is provided):
```python
def _dual_kpi_val(real_val: str, nominal_val: str | None, *, is_monetary: bool = True) -> str:
    if nominal_val is None or not is_monetary:
        return f"<div class='kpi-value'>{real_val}</div>"
    return (
        f"<div class='kpi-value'>"
        f"<span class='nwn-view-real'>{real_val}</span>"
        f"<span class='nwn-view-nominal' style='display:none'>{nominal_val}</span>"
        f"</div>"
    )
```

Monetary KPI values are the net-worth ones and terminal values:
- "Net Worth (EOY)" → real from `first_row`, nominal from `nominal_first_row`
- "Net Worth at Retirement" → both
- "Net Worth at End" → both
- "Median Terminal Net Worth" → both (MC/historical modes)
- "Worst-Decile Terminal Net Worth" → both

Non-monetary: "Retirement Age", success rates (percentages) — no dual needed.

**Verification:**
```bash
.venv/bin/python run.py --scenario sample --offline
grep -o 'nwn-view-real\|nwn-view-nominal' output/scenarios/sample/deterministic/projection.html | sort | uniq -c
# Both should appear
```

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual KPI strip values for real-dollar toggle"
```

---

### Task 6: Dual main chart rendering

**Objective:** `build_chart()` produces two complete chart divs when `real_dollar_basis = true`.

**Files:**
- Modify: `src/charts.py`

**Step 1: Modify `build_chart()` to accept `nominal_df`**

The `build_chart()` already receives a `ProjectionResult` via `projection`. The `ProjectionResult` now carries `nominal_yearly_df`. Extract it:

```python
    projection_result = _coerce_projection_result(projection)
    df = projection_result.yearly_df
    nominal_df = projection_result.nominal_yearly_df
```

**Step 2: Build nominal chart when available**

After the existing `fig = _build_figure(df, config, ...)`:

```python
    nominal_fig_html = ""
    if nominal_df is not None:
        nominal_fig = _build_figure(
            nominal_df, config, projection_result=projection_result,
            real_dollar_basis=False  # force nominal mode for this figure
        )
        nominal_fig_html = nominal_fig.to_html(
            full_html=False,
            include_plotlyjs=False,  # Plotly already loaded by the real chart
            div_id="nwn-chart-nominal",
            config=dict(scrollZoom=True, displaylogo=False),
        )
```

Wait — `_build_figure()` currently reads `real_dollar_basis` from `projection_result.simulation`. For the nominal figure, we need it to NOT append "(in 2026 dollars)" to the subtitle. Pass a flag:

**Step 2a: Add `real_dollar_basis` override parameter to `_build_figure()`**

```python
def _build_figure(
    df: pd.DataFrame,
    config: dict,
    projection_result: ProjectionResult | None = None,
    force_real_dollar_basis: bool | None = None,
) -> go.Figure:
```

In the subtitle section (~line 2615), use the override:
```python
    real_dollar_basis = (
        force_real_dollar_basis
        if force_real_dollar_basis is not None
        else (
            projection_result is not None
            and projection_result.simulation.get("real_dollar_basis", False)
        )
    )
```

**Step 3: Wrap both charts in a container with toggle classes**

```python
    chart_wrapper = ""
    if nominal_df is not None:
        chart_wrapper = (
            f"<div id='nwn-chart-container' class='nwn-dual-chart'>"
            f"<div class='nwn-view-real'>{chart_div}</div>"
            f"<div class='nwn-view-nominal' style='display:none'>{nominal_fig_html}</div>"
            f"</div>"
        )
    else:
        chart_wrapper = chart_div
```

The CSS classes `.nwn-view-real` and `.nwn-view-nominal` are toggled by JS.

**Step 4: No Plotly JS duplication**

The real chart uses `include_plotlyjs="cdn"`. The nominal chart uses `include_plotlyjs=False`.

**Verification:**
```bash
.venv/bin/python run.py --scenario sample --offline
grep -c 'nwn-chart-nominal' output/scenarios/sample/deterministic/projection.html
# Should be > 0
grep -c 'Plotly.newPlot' output/scenarios/sample/deterministic/projection.html
# Should be 2 (one for each chart div)
```

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual main chart rendering for real-dollar toggle"
```

---

### Task 7: Wire `build_chart()` to pass `nominal_df` to all sub-builders

**Objective:** `build_chart()` already calls sub-builders for tables, KPI, portfolio chart, liabilities, cash reserve. Pass `nominal_df` to each.

**Files:**
- Modify: `src/charts.py`

**Step 1: Extract `nominal_df` at the top of `build_chart()`**

```python
    nominal_df = projection_result.nominal_yearly_df
```

**Step 2: Pass to KPI**
```python
    kpi_html = _build_kpi_summary(config, projection_result, nominal_df=nominal_df)
```

**Step 3: Pass to table builders**

Update the calls:
```python
    accounts_html = _wrap_table_with_sticky_header(
        build_accounts_table(df, config=config, nominal_df=nominal_df)
    )
    cashflow_html = _wrap_table_with_sticky_header(
        build_cashflow_table(df, config=config, nominal_df=nominal_df)
    )
    tax_html = _wrap_table_with_sticky_header(
        build_tax_table(df, nominal_df=nominal_df)
    )
```

**Step 4: Pass to portfolio chart**
```python
    portfolio_html = _build_portfolio_chart(
        df, config=config, projection_result=projection_result,
        nominal_df=nominal_df,
    )
```

**Step 5: Pass to liabilities and cash reserve**

Similarly for `_build_liabilities_chart`, `_build_cash_reserve_chart`, `_build_cash_reserve_summary`, `_build_tax_result_card`.

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: wire nominal_df through build_chart() to all sub-builders"
```

---

### Task 8: Dual portfolio chart

**Objective:** `_build_portfolio_chart()` produces two chart divs.

**Files:**
- Modify: `src/charts.py`

**Pattern:** Same as main chart (Task 6). Accept `nominal_df`, build nominal figure when present, wrap both in a `.nwn-dual-chart` container.

```python
def _build_portfolio_chart(
    df: pd.DataFrame,
    config: dict | None = None,
    projection_result: ProjectionResult | None = None,
    nominal_df: pd.DataFrame | None = None,
) -> str:
```

Build nominal figure with `force_real_dollar_basis=False`, use `include_plotlyjs=False`.

**Verification:**
```bash
.venv/bin/python run.py --scenario sample --offline
grep -c 'portfolio-chart-nominal' output/scenarios/sample/deterministic/projection.html
# Should be > 0
```

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual portfolio chart for real-dollar toggle"
```

---

### Task 9: Dual liabilities chart

**Objective:** `_build_liabilities_chart()` produces two chart divs.

**Files:**
- Modify: `src/charts.py`

Same pattern as Task 8. Add `nominal_df` parameter.

**Verification:** Same approach — check for nominal div ID in output.

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual liabilities chart for real-dollar toggle"
```

---

### Task 10: Dual cash reserve chart + summary

**Objective:** `_build_cash_reserve_chart()` produces two chart divs; summary values use dual spans.

**Files:**
- Modify: `src/charts.py`

Same pattern for the chart.

For `_build_cash_reserve_summary()`, the cash target/minimum values need data-nominal. These are rendered via `_fmt_currency()`. Pass nominal values and wrap in dual spans.

**Verification:** Check output.

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual cash reserve chart and summary for real-dollar toggle"
```

---

### Task 11: Dual tax summary card

**Objective:** Tax summary card total amounts get dual span values.

**Files:**
- Modify: `src/charts.py`

The `_build_tax_result_card()` renders total federal tax, total state tax, combined total. These three values need nominal counterparts.

Pass `nominal_df` and compute from it.

**Verification:** Check output.

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: dual tax summary values for real-dollar toggle"
```

---

### Task 12: Segmented pill toggle integrated in the value-basis badge bar

**Objective:** Replace the static server-rendered value-basis badge with an interactive segmented pill control that switches nominal/real-dollar views. The badge description text updates to match the active mode.

**Files:**
- Modify: `src/charts.py` (in `build_chart()` and the `<style>` block)

**Design:** The toggle is NOT a standalone button in the toolbar. It's a two-segment pill (`💰 Real | 📊 Nominal`) right-aligned inside the `.modeling-note` badge bar below the KPI strip. Clicking either segment activates that mode. The descriptive text left of the pill also changes.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Value basis: All figures in 2026 dollars (deflated by assumed inflation).    │
│                                                          [💰 Real | Nominal]│
└──────────────────────────────────────────────────────────────────────────────┘

Toggle to nominal:
┌──────────────────────────────────────────────────────────────────────────────┐
│ Value basis: All figures in nominal (future-year) dollars. Inflation not     │
│ adjusted.                                                  [Real | 📊 Nominal]│
└──────────────────────────────────────────────────────────────────────────────┘
```

**Why inline with the badge:**
- The badge already describes what the toggle controls — co-locating them eliminates guessing
- Uses dead space on the right side of the badge bar
- Self-documenting: the description *changes with the toggle*
- Both options visible at once (segmented control pattern), so the user knows what the alternative is before clicking

**Step 1: Replace static value-basis badge with interactive dual-badge + pill**

In `build_chart()`, replace the current `value_basis_html` block (~line 2244–2252):

```python
    # Value-basis bar with integrated segmented pill toggle
    value_basis_html = ""
    if projection_result.simulation.get("real_dollar_basis"):
        sim = config.get("simulation", {})
        start_year = int(sim.get("start_year", 2026))
        value_basis_html = (
            "<div class='modeling-note value-basis-bar'>"
            # ── Real-dollar text (visible when mode=real) ──
            "<span class='nwn-view-real basis-text'>"
            f"<strong>Value basis:</strong> All figures in {start_year} dollars (deflated by assumed inflation)."
            "</span>"
            # ── Nominal text (visible when mode=nominal) ──
            "<span class='nwn-view-nominal basis-text' style='display:none'>"
            "<strong>Value basis:</strong> All figures in nominal (future-year) dollars. Inflation not adjusted."
            "</span>"
            # ── Segmented pill toggle ──
            "<span class='value-toggle-pill' id='nwn-value-toggle'>"
            "<span class='toggle-segment nwn-toggle-real' data-mode='real'>💰 Real</span>"
            "<span class='toggle-segment nwn-toggle-nominal' data-mode='nominal'>📊 Nominal</span>"
            "</span>"
            "</div>"
        )
```

The `.value-basis-bar` uses flexbox: descriptive text on the left, pill on the right.

**Step 2: Add CSS for the segmented pill and badge bar**

```css
/* ── Value-basis badge bar (flex row: text left, pill right) ── */
.value-basis-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.basis-text {
  flex: 1 1 auto;
  min-width: 0;
}

/* ── Segmented pill toggle ── */
.value-toggle-pill {
  display: inline-flex;
  flex-shrink: 0;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid rgba(148,163,184,0.28);
  background: rgba(148,163,184,0.08);
  font-size: 12px;
  line-height: 1;
}
.toggle-segment {
  padding: 4px 10px;
  cursor: pointer;
  color: rgba(226,232,240,0.60);
  transition: background 0.15s, color 0.15s;
  user-select: none;
  white-space: nowrap;
}
.toggle-segment:hover {
  color: rgba(226,232,240,0.85);
  background: rgba(148,163,184,0.12);
}
/* Active segment highlight */
body.nwn-real .nwn-toggle-real,
body.nwn-nominal .nwn-toggle-nominal {
  background: rgba(45,212,191,0.18);
  color: #e2e8f0;
  font-weight: 600;
}

/* ── Body-class visibility for badge text ── */
body.nwn-nominal span.nwn-view-real.basis-text { display: none !important; }
body.nwn-nominal span.nwn-view-nominal.basis-text { display: inline !important; }
body.nwn-real span.nwn-view-real.basis-text { display: inline !important; }
body.nwn-real span.nwn-view-nominal.basis-text { display: none !important; }
```

Note: `.basis-text` uses `span` (not `div`) so the flex row stays horizontal. The `!important` overrides the inline `style='display:none'` set on the nominal span.

**Step 3: JavaScript — pill click handlers replace button click**

The JS from the original Task 12 stays largely the same, but the toggle trigger changes from a single button to clicking either segment:

```javascript
(function() {
  var STORAGE_KEY = 'nwn-value-basis';
  var currentMode = localStorage.getItem(STORAGE_KEY) || 'real';

  function swapTableCells(toMode) {
    var cells = document.querySelectorAll('[data-nominal]');
    cells.forEach(function(cell) {
      if (toMode === 'nominal') {
        cell.setAttribute('data-real', cell.innerHTML);
        cell.innerHTML = cell.getAttribute('data-nominal');
      } else {
        var realVal = cell.getAttribute('data-real');
        if (realVal) {
          cell.innerHTML = realVal;
          cell.removeAttribute('data-real');
        }
      }
    });
  }

  function applyMode(mode) {
    document.body.classList.remove('nwn-real', 'nwn-nominal');
    document.body.classList.add('nwn-' + mode);
    swapTableCells(mode);
    localStorage.setItem(STORAGE_KEY, mode);
    currentMode = mode;
  }

  // Apply stored preference on load
  if (currentMode === 'nominal') {
    applyMode('nominal');
  }

  // Segmented pill: click either segment to switch
  var pill = document.getElementById('nwn-value-toggle');
  if (pill) {
    pill.addEventListener('click', function(e) {
      var seg = e.target.closest('.toggle-segment');
      if (!seg) return;
      var mode = seg.getAttribute('data-mode');
      if (mode && mode !== currentMode) {
        applyMode(mode);
      }
    });
  }
})();
```

The subtitle update and separate badge display logic from the original Task 12 are removed — the badge text itself is now part of the `.nwn-view-real`/`.nwn-view-nominal` dual-span pattern and toggled via CSS (no JS needed).

**Step 4: Add CSS for body-class-driven element visibility**

```css
body.nwn-nominal .nwn-view-real { display: none !important; }
body.nwn-nominal .nwn-view-nominal { display: block !important; }
body.nwn-real .nwn-view-real { display: block !important; }
body.nwn-real .nwn-view-nominal { display: none !important; }

/* For inline spans (KPI values, summary values, badge text) */
body.nwn-nominal span.nwn-view-real { display: none !important; }
body.nwn-nominal span.nwn-view-nominal { display: inline !important; }
body.nwn-real span.nwn-view-real { display: inline !important; }
body.nwn-real span.nwn-view-nominal { display: none !important; }
```

**Step 5: Store real-dollar subtitle note for Plotly chart title restore**

The Plotly chart title/subtitle is set in `_build_figure()` and lives inside the chart div, not as a DOM element. When toggling to nominal, we can't easily update the Plotly title. Embed the note string as a JS variable:

In `build_chart()`, when `nominal_df is not None`, add before the chart wrapper:
```html
<script>var NWN_REAL_DOLLAR_NOTE = " (in {start_year} dollars)";</script>
```

Then in `applyMode()`, update the chart subtitle via Plotly API:
```javascript
function updateChartSubtitle(mode) {
  var note = typeof NWN_REAL_DOLLAR_NOTE !== 'undefined' ? NWN_REAL_DOLLAR_NOTE : '';
  var chartEl = document.getElementById('nwn-chart');
  if (!chartEl || !chartEl._fullLayout) return;
  var currentSubtitle = chartEl._fullLayout.title.text;
  if (mode === 'nominal') {
    // Remove real-dollar note
    if (note) {
      Plotly.relayout(chartEl, { 'title.text': currentSubtitle.replace(note, '') });
    }
  } else {
    // Re-add real-dollar note if missing
    if (note && currentSubtitle.indexOf(note) === -1) {
      Plotly.relayout(chartEl, { 'title.text': currentSubtitle + note });
    }
  }
}
```

Call `updateChartSubtitle(mode)` inside `applyMode()`.

Actually, simpler approach: since we're using two chart divs (Task 6), and each div has its own subtitle baked into `_build_figure()`, the body-class toggle already handles subtitle visibility. The real-dollar chart subtitle says "(in 2026 dollars)" and the nominal chart subtitle doesn't. No JS subtitle manipulation needed at all! Drop Step 5.

**Verification:**
```bash
.venv/bin/python run.py --scenario sample --offline
grep -c 'value-toggle-pill' output/scenarios/sample/deterministic/projection.html
# Should be 1
grep -c 'toggle-segment' output/scenarios/sample/deterministic/projection.html
# Should be 2
grep -c 'nwn-toggle-real' output/scenarios/sample/deterministic/projection.html
# Should be 1
```

Open in browser, verify:
- Pill sits right-aligned in the badge bar
- Clicking "💰 Real" activates real-dollar view (default)
- Clicking "📊 Nominal" switches to nominal view
- Badge text changes to match
- Chart swaps (dual div, "in YYYY dollars" subtitle on real view only)
- Table values change
- KPI values change
- Refresh page → preference preserved

**Commit:**
```bash
git add src/charts.py
git commit -m "feat: segmented pill toggle integrated in value-basis badge bar"
```

---

### Task 13: Integration test and edge cases

**Objective:** Full end-to-end verification of the toggle across all tabs and modes.

**Step 1: Render all modes**
```bash
.venv/bin/python run.py --scenario sample --offline
```

**Step 2: Verify page loads without JS errors**
Check browser console after loading the output page.

**Step 3: Verify toggle behavior for each view element:**

| Element | Nominal mode | Real-dollar mode |
|---|---|---|
| Main chart | Values match nominal, no "(in 2026)" subtitle | Values deflated, subtitle shows year-dollar note |
| KPI strip | Higher end-year values | Lower end-year values |
| Accounts table | Nominal balances | Deflated balances |
| Cash flow table | Nominal income/spending | Deflated values |
| Tax table | Higher tax amounts | Deflated tax amounts |
| Portfolio chart | Higher portfolio values | Deflated values |
| Liabilities chart | Higher debt balances | Deflated balances |
| Cash reserve chart | Higher target/cash values | Deflated values |
| Cash reserve summary | Nominal target amounts | Deflated target amounts |
| Tax summary card | Nominal totals | Deflated totals |

**Step 4: Edge cases**
- Toggle while on a non-default tab → tab stays selected, values swap
- Toggle on MC/historical mode → chart bands swap, KPI values swap
- Refresh page → preference preserved
- No real_dollar_basis → toggle pill absent, no dual data, badge identical to pre-feature
- Toggle with zero values → `data-nominal` not present on zero cells, no error

**Step 5: Render without toggle (real_dollar_basis=false)**
```bash
# Temporarily set real_dollar_basis=false in a test copy
cp scenarios/sample.toml /tmp/sample-nominal.toml
# Edit to set real_dollar_basis = false
.venv/bin/python run.py --scenario sample --offline
```
Verify: no toggle button, no `data-nominal` attributes, page identical to pre-feature output.

**Commit:** (if any fixes needed)
```bash
git add src/charts.py src/tables.py
git commit -m "fix: edge case handling for real-dollar toggle"
```

---

### Task 14: (absorbed into Task 12)

The value-basis badge and toggle are now a single integrated component. Task 12 handles both. No separate task needed.

---

### Task 15: Starlight User Guide update

**Objective:** Document the toggle feature in the User Guide FAQ and Config Reference.

**Files:**
- Modify: `docs/guide/src/content/docs/` — relevant .mdx files

**Step 1: Update Config Reference**

In the `real_dollar_basis` field description, add:
```
When enabled, an inline toggle pill (💰 Real | 📊 Nominal) appears in the value-basis badge bar 
below the KPI strip, allowing instant switching between inflation-adjusted and nominal views without re-rendering.
```

**Step 2: Update FAQ**

Add Q&A:
```
### How do I switch between real and nominal dollars?

When `real_dollar_basis = true`, a segmented toggle pill (💰 Real | 📊 Nominal) appears 
in the value-basis bar below the KPI numbers. Click either side to switch between inflation-adjusted 
(start-year) dollars and nominal (future-year) dollars. Your preference is remembered across page reloads.
```

**Step 3: Add screenshot**

Take a screenshot showing the segmented toggle pill in the value-basis bar. Add to `docs/guide/public/` and reference with `<ImagePreview>`.

**Commit:**
```bash
git add docs/guide/
git commit -m "docs: document real-dollar toggle in User Guide"
```

---

## Summary

| Task | File(s) | Lines changed | Risk |
|---|---|---|---|
| 1. `nominal_yearly_df` on `ProjectionResult` | `model.py` | ~20 | Low — additive field |
| 2. Extend `_fmt()` with `nominal_val` | `tables.py` | ~5 | Low — backward-compatible |
| 3. Extend `_data_row()` | `tables.py` | ~10 | Low |
| 4. Update table builders | `tables.py` | ~80 | Medium — many functions |
| 5. Dual KPI values | `charts.py` | ~30 | Low |
| 6. Dual main chart | `charts.py` | ~25 | Medium — two Plotly divs |
| 7. Wire `nominal_df` through `build_chart()` | `charts.py` | ~20 | Low |
| 8. Dual portfolio chart | `charts.py` | ~20 | Low |
| 9. Dual liabilities chart | `charts.py` | ~15 | Low |
| 10. Dual cash reserve chart + summary | `charts.py` | ~25 | Low |
| 11. Dual tax summary card | `charts.py` | ~15 | Low |
| 12. Segmented pill toggle + JS | `charts.py` | ~120 | Medium — new JS + CSS |
| 13. Integration test | — | — | Verification only |
| 14. (absorbed into Task 12) | — | — | — |
| 15. Starlight docs update | `docs/guide/` | ~20 | Low |

**Total estimated: ~400 lines, 14 commits (one absorbed), across 3 files + docs.**

## Design Decisions

1. **Dual chart divs, not Plotly.restyle()**: Restyle would require embedding trace data in JS and patching every trace individually. Two complete `fig.to_html()` divs are self-consistent, handle edge cases (stacked areas, percentile bands, different trace counts) automatically, and avoid fragile JS data serialization. The cost (~100KB extra HTML per page) is acceptable for a local app.

2. **`data-nominal` attributes for tables, not dual table HTML**: Non-monetary cells (years, rates, flags, strings, booleans) don't change between modes — they'd waste space if duplicated. Only ~25% of cells are monetary. The attribute approach adds ~10 bytes per cell vs ~200 bytes for full cell duplication.

3. **Body-class-driven CSS, not JS iteration of elements**: `body.nwn-nominal .nwn-view-real { display: none }` is simpler, faster, and less error-prone than JS that iterates all dual-view elements. The only JS-driven part is table cell `innerHTML` swap (because `data-nominal` content can't be read via CSS).

4. **`localStorage` for preference**: The user's choice persists across page reloads. No cookie, no server round-trip.

5. **Segmented pill in the badge bar, not a separate toolbar button**: The value-basis badge already describes what the toggle controls. Co-locating the toggle (as a two-segment pill right-aligned in the badge bar) makes the relationship explicit, uses dead space, and eliminates the separate badge-update JS — the description text itself is a dual-span element that CSS toggles with the same body-class mechanism as everything else.

## Feature Branch

```bash
git checkout -b feat/real-dollar-toggle
# ... implement tasks ...
# When satisfied with local display:
git checkout main
git merge feat/real-dollar-toggle
```
