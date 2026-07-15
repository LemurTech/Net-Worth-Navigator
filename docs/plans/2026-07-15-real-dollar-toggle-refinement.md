# Real-Dollar Toggle — Code Quality Refinement Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task with two-stage review.

**Goal:** Fix the code issues and inefficiencies identified in the `feat/real-dollar-toggle` code review, primarily the fragile `eval()` + regex script extraction for subsidiary charts.

**Architecture:** All changes are scoped to `src/charts.py` and `src/tables.py` (Python backend) plus optional `tests/` additions. No model-layer changes except as needed for testability. The existing dual-data embedding architecture (CSS-driven toggle, `data-nominal` attributes, lazy chart init) remains unchanged — only the implementation of subsidiary chart dual-rendering is refactored.

**Tech Stack:** Python, Plotly, regex-free script extraction

---

## Issues Summary

| # | Severity | Issue | File(s) | Remediation |
|---|----------|-------|---------|-------------|
| 1 | 🔴 Critical | `eval()` + regex script extraction for subsidiary charts (portfolio, liabilities, cash reserve) | `src/charts.py:2473-2555` | Refactor to JSON serialization (like main chart) |
| 2 | 🟡 Medium | Inline `import json` and `import re` inside `build_chart()` | `src/charts.py:2425, 2483` | Move to module-level imports |
| 3 | 🟡 Medium | Repeated ID-replacement pattern for chart IDs (3 copies) | `src/charts.py:2478-2496, 2504-2515, 2525-2542` | Extract helper function |
| 4 | 🟡 Medium | Missing tests for dual-view model layer | `tests/` | Add `test_real_dollar_toggle.py` |
| 5 | ⚪ Minor | `_dual_currency` / `_dual_currency_str` duplicated across files | `src/charts.py:1807`, `src/tables.py:1551` | Extract shared helper in `tables.py` module scope |

Tasks are ordered by risk and dependency. Each task produces a working, committed state.

---

## Task 1: Inline imports → module level

**Objective:** Remove the two inline `import` statements inside `build_chart()` and move them to the module-level imports in `charts.py`.

**Rationale:** Python caches imports after first execution, so this is not a correctness bug, but inline imports obscure module dependencies and the module-level `import re as _re` (line 1175) already exists — the inline re-import is redundant.

**Files:**
- Modify: `src/charts.py` (lines 2425, 2483)

**Step 1: Confirm current state**

Run: `grep -n "import json as _json\|import re as _re" src/charts.py`
Expected:
```
1175:import re as _re
2425:        import json as _json
2483:        import re as _re
```

Line 1175 is the existing module-level `import re as _re` (for the sticky-header wrapper). That stays.

**Step 2: Add `import json` to module-level imports**

At the top of `charts.py`, add `import json` alongside the existing `from ...` imports.

The top of `charts.py` currently reads:
```python
from io import StringIO
from pathlib import Path
from html import escape
import re as _re
```

Add `import json` after `from html import escape` (or after `import re as _re` — whichever flows naturally).

**Step 3: Replace `import json as _json` with just `_json = json`**

Line 2425 currently: `import json as _json`

Replace with: `_json = json`

This preserves the local alias `_json` so the rest of the code (`_json.dumps(...)`) still works without changes.

**Step 4: Remove `import re as _re` from line 2483**

Line 2483 currently: `import re as _re`

Replace with an empty line or just delete the line. The alias `_re` from the module-level `import re as _re` (line 1175) is already available.

**Step 5: Verify the module still parses**

Run: `python3 -c "import ast; ast.parse(open('src/charts.py').read()); print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add src/charts.py
git commit -m "chore: move inline imports to module level in charts.py"
```

---

## Task 2: Extract `_build_dual_chart_wrapper()` helper

**Objective:** Replace the 3 copies of the ID-replacement + regex-script-extraction pattern with a single helper function.

**Rationale:** The pattern:

```python
nom_xxx = _build_xxx_chart(nominal_df, ...)
nom_xxx = nom_xxx.replace('"nwn-xxx"', '"nwn-xxx-nominal"')
nom_xxx = nom_xxx.replace("'nwn-xxx'", "'nwn-xxx-nominal'")
nom_xxx = nom_xxx.replace('\\"nwn-xxx\\"', '\\"nwn-xxx-nominal\\"')
_sm = _re.search(r'<script>(.*?Plotly\.newPlot.*?)</script>', nom_xxx, _re.DOTALL)
if _sm:
    nom_script = _sm.group(1).strip()
    nom_xxx = f"<script>var NWN_XXX_SCRIPT = {nom_script!r};</script>" + ...
```

…appears 3 times with only the plotly chart ID, JS variable name, and builder function differing. This is a prime candidate for extraction.

**Note:** This task preserves the script-extraction approach (the critical JSON refactor is Task 3). Extraction makes the pattern DRY first, so Task 3's JSON refactor touches only one function.

**Files:**
- Create: (in-place function) `src/charts.py` — new module-level function `_build_dual_chart_html()`
- Modify: `src/charts.py` — 3 call sites in `build_chart()`

**Step 1: Understand the current pattern**

Read the 3 blocks in `build_chart()` at lines 2473–2542. Each block:

1. Builds the real chart HTML via `_build_xxx_chart(df, ...)`
2. Builds the nominal chart HTML via `_build_xxx_chart(nominal_df, ...)`
3. String-replaces chart div IDs in the nominal HTML
4. Regex-extracts the `Plotly.newPlot()` script
5. Wraps both in dual-view divs

The only differences per block are:
- builder function name (`_build_portfolio_chart`, `_build_liabilities_chart`, `_build_cash_reserve_chart`)
- chart div ID (`nwn-portfolio`, `nwn-liabilities`, `nwn-cash-reserve`)
- JS variable name (`NWN_PORTFOLIO_SCRIPT`, `NWN_LIABILITIES_SCRIPT`, `NWN_CASH_RESERVE_SCRIPT`)

**Step 2: Add the helper function**

Add to `src/charts.py` near line 2470 (before the `build_chart()` function's body code that builds the tab content):

```python
def _build_dual_chart_html(
    real_html: str,
    nominal_df: pd.DataFrame | None,
    chart_id: str,
    script_var_name: str,
    builder_fn: callable,
    **builder_kwargs,
) -> str:
    """Wrap real and nominal chart HTML in dual-view divs.

    When nominal_df is None (real-dollar mode is off), returns just real_html.
    When nominal_df is provided, generates a nominal version of the chart,
    extracts its Plotly.newPlot script for lazy initialization, and wraps
    both in CSS-classed divs for the toggle.
    """
    if nominal_df is None:
        return f"<div class='gantt-wrap'>{real_html}</div>"

    nom_html = builder_fn(nominal_df, **builder_kwargs)
    nom_id = f"{chart_id}-nominal"
    nom_html = nom_html.replace(f'"{chart_id}"', f'"{nom_id}"')
    nom_html = nom_html.replace(f"'{chart_id}'", f"'{nom_id}'")
    nom_html = nom_html.replace(f'\\"{chart_id}\\"', f'\\"{nom_id}\\"')

    import re as _re
    _match = _re.search(
        r'<script>(.*?Plotly\.newPlot.*?)</script>', nom_html, _re.DOTALL
    )
    if _match:
        _script = _match.group(1).strip()
        nom_html = (
            f"<script>var {script_var_name} = {_script!r};</script>"
            + nom_html[:_match.start()]
            + nom_html[_match.end():]
        )

    return (
        f"<div class='nwn-view-real'><div class='gantt-wrap'>{real_html}</div></div>"
        f"<div class='nwn-view-nominal' style='display:none'><div class='gantt-wrap'>{nom_html}</div></div>"
    )
```

**Step 3: Replace the Portfolio tab block**

Current code (~line 2473):
```python
    portfolio_html = ""
    if nominal_df is not None:
        real_portfolio = _build_portfolio_chart(df, config=config, projection_result=projection_result)
        nom_portfolio = _build_portfolio_chart(nominal_df, ...)
        nom_portfolio = nom_portfolio.replace(...)
        ...
    else:
        portfolio_html = _build_portfolio_chart(df, config=config, projection_result=projection_result)
```

Replace with:
```python
    portfolio_html = _build_dual_chart_html(
        real_html=_build_portfolio_chart(df, config=config, projection_result=projection_result),
        nominal_df=nominal_df,
        chart_id="nwn-portfolio",
        script_var_name="NWN_PORTFOLIO_SCRIPT",
        builder_fn=_build_portfolio_chart,
        config=config,
        projection_result=projection_result,
    )
```

**Step 4: Replace the Liabilities tab block**

Current code (~line 2501):
```python
    liabilities_chart_html = _build_liabilities_chart(df, config=config)
    liabilities_chart_nom = ""
    if nominal_df is not None:
        ...
```

Replace with:
```python
    liabilities_chart_html = _build_dual_chart_html(
        real_html=_build_liabilities_chart(df, config=config),
        nominal_df=nominal_df,
        chart_id="nwn-liabilities",
        script_var_name="NWN_LIABILITIES_SCRIPT",
        builder_fn=_build_liabilities_chart,
        config=config,
    )
```

Then change `liabilities_html` from:
```python
    liabilities_chart_wrapped = (
        f"<div class='nwn-view-real'><div class='gantt-wrap'>{liabilities_chart_html}</div></div>"
        ...
    )
    liabilities_table_html = build_liabilities_table(df, config=config, nominal_df=nominal_df)
    liabilities_html = liabilities_chart_wrapped + liabilities_table_html
```

To:
```python
    liabilities_table_html = build_liabilities_table(df, config=config, nominal_df=nominal_df)
    liabilities_html = liabilities_chart_html + liabilities_table_html
```

(The `_build_dual_chart_html` helper already wraps in dual-view divs, so the separate wrapping `liabilities_chart_wrapped` variable is no longer needed.)

**Step 5: Replace the Cash Reserve tab block**

Current code (~line 2521):
```python
    cash_reserve_chart_html = _build_cash_reserve_chart(df, config=config)
    cash_reserve_chart_nom = ""
    if nominal_df is not None:
        ...
```

Replace with:
```python
    cash_reserve_chart_html = _build_dual_chart_html(
        real_html=_build_cash_reserve_chart(df, config=config),
        nominal_df=nominal_df,
        chart_id="nwn-cash-reserve",
        script_var_name="NWN_CASH_RESERVE_SCRIPT",
        builder_fn=_build_cash_reserve_chart,
        config=config,
    )
```

Then change the wrapping from:
```python
    cash_reserve_chart_wrapped = (...)
    cash_reserve_summary_html = ...
    cash_reserve_html = cash_reserve_chart_wrapped + cash_reserve_summary_html
```

To:
```python
    cash_reserve_summary_html = _build_cash_reserve_summary(df, config=config, nominal_df=nominal_df)
    cash_reserve_html = cash_reserve_chart_html + cash_reserve_summary_html
```

**Step 6: Verify the module still parses**

```bash
python3 -c "import ast; ast.parse(open('src/charts.py').read()); print('OK')"
```
Expected: `OK`

**Step 7: Check for unused variables**

The original code had `real_portfolio`, `nom_portfolio`, `_sm`, `nom_script`, `liabilities_chart_nom`, `cash_reserve_chart_nom` etc. as local variables. After extraction, verify no dangling references:

```bash
grep -n "real_portfolio\|nom_portfolio\|liabilities_chart_nom\|cash_reserve_chart_nom\|nom_script2\|nom_script3" src/charts.py
```

Expected: no output (all removed).

**Step 8: Commit**

```bash
git add src/charts.py
git commit -m "refactor: extract _build_dual_chart_html helper for subsidiary charts"
```

---

## Task 3: Refactor subsidiary charts to JSON lazy-init (no eval)

**Objective:** Replace the regex + `eval()` script extraction with JSON serialization and `Plotly.newPlot()` — the same pattern used by the main chart.

**Rationale:** The current approach:
1. Calls `fig.to_html()` which produces `<div>` + `<script>Plotly.newPlot(...)</script>`
2. Regex-extracts the script text
3. Stores as a JS string variable via `repr()`
4. In the browser, calls `eval()` on toggle

The main chart uses the clean pattern:
1. Calls `fig.to_plotly_json()` → JSON dict
2. Serializes to JSON string
3. Stores as `var NWN_NOMINAL_FIGURE = {...};`
4. On toggle, calls `Plotly.newPlot('chart-id', figure.data, figure.layout, ...)`

**This task retrofits the `_build_dual_chart_html` helper created in Task 2** to use the JSON pattern, removing both the regex extraction and the `eval()` call from the browser JS.

**Files:**
- Modify: `src/charts.py` — the `_build_dual_chart_html` helper

**Step 1: Understand the main-chart pattern**

Read the main chart dual-rendering code at `build_chart()` lines ~2419–2441:

```python
nominal_fig = _build_figure(
    nominal_df, config, projection_result=projection_result,
    force_real_dollar_basis=False,
)
nominal_figure_json = _json.dumps(
    nominal_fig.to_plotly_json(), default=str
)
nominal_chart_html = (
    f"<div id=\"nwn-chart-nominal\" class=\"plotly-graph-div\""
    f" style=\"height:100%; width:100%;\"></div>\n"
    f"<script>var NWN_NOMINAL_FIGURE = {nominal_figure_json};</script>"
)
```

And the browser-side lazy init at lines ~1099–1105:
```javascript
if (mode === 'nominal' && !_nominalRendered && typeof NWN_NOMINAL_FIGURE !== 'undefined') {
    _nominalRendered = true;
    Plotly.newPlot('nwn-chart-nominal', NWN_NOMINAL_FIGURE.data, NWN_NOMINAL_FIGURE.layout,
        {scrollZoom: true, displaylogo: false, responsive: true});
```

**Step 2: Refactor `_build_dual_chart_html` to use JSON**

Change the helper to:
1. Build both figures via `builder_fn(nominal_df, **kwargs)`
2. Call `fig.to_plotly_json()` on the nominal figure
3. Serialize to a JSON `<script>` variable
4. Add an empty `<div>` for the nominal chart
5. Remove the regex-based script extraction entirely

```python
def _build_dual_chart_html(
    real_html: str,
    nominal_df: pd.DataFrame | None,
    chart_id: str,
    script_var_name: str,
    builder_fn: callable,
    **builder_kwargs,
) -> str:
    """Wrap real and nominal chart HTML in dual-view divs with JSON lazy-init."""
    if nominal_df is None:
        return f"<div class='gantt-wrap'>{real_html}</div>"

    nom_id = f"{chart_id}-nominal"
    nominal_fig = builder_fn(nominal_df, **builder_kwargs)
    nominal_figure_json = json.dumps(
        nominal_fig.to_plotly_json(), default=str
    )

    return (
        f"<div class='nwn-view-real'><div class='gantt-wrap'>{real_html}</div></div>"
        f"<div class='nwn-view-nominal' style='display:none'>"
        f"<div class='gantt-wrap'>"
        f"<div id=\"{nom_id}\" class=\"plotly-graph-div\""
        f" style=\"height:100%; width:100%;\"></div>"
        f"</div>"
        f"<script>var {script_var_name} = {nominal_figure_json};</script>"
        f"</div>"
    )
```

Key changes from the regex version:
- No `nom_html.replace(...)` ID substitution — the nominal chart div is created fresh with the correct ID
- No `_re.search(...)` — the figure is serialized as JSON, not extracted from generated HTML
- No `eval()` needed on the browser side — the JS variable is a plain JSON object, not a function body

**Step 3: Update the browser-side lazy init JS**

In the `<script>` block (around line 1108–1116 in `charts.py`), the subsidiary chart init currently uses `eval()`:

```javascript
['NWN_PORTFOLIO_SCRIPT', 'NWN_LIABILITIES_SCRIPT', 'NWN_CASH_RESERVE_SCRIPT'].forEach(function(varName) {
    if (typeof window[varName] !== 'undefined') {
        try { eval(window[varName]); } catch(e) {}
        delete window[varName];
    }
});
```

Replace with direct `Plotly.newPlot` calls:

```javascript
// Initialize subsidiary nominal charts from stored JSON figures
var _chartDefs = [
    {id: 'nwn-portfolio-nominal',   key: 'NWN_PORTFOLIO_FIGURE'},
    {id: 'nwn-liabilities-nominal', key: 'NWN_LIABILITIES_FIGURE'},
    {id: 'nwn-cash-reserve-nominal', key: 'NWN_CASH_RESERVE_FIGURE'},
];
_chartDefs.forEach(function(def) {
    if (typeof window[def.key] !== 'undefined') {
        Plotly.newPlot(def.id, window[def.key].data, window[def.key].layout,
            {scrollZoom: true, displaylogo: false, responsive: true});
        delete window[def.key];
    }
});
```

**Step 4: Update the JS variable names in the helper**

Change the `script_var_name` values at all three call sites in `build_chart()`:

| Old | New |
|-----|-----|
| `NWN_PORTFOLIO_SCRIPT` | `NWN_PORTFOLIO_FIGURE` |
| `NWN_LIABILITIES_SCRIPT` | `NWN_LIABILITIES_FIGURE` |
| `NWN_CASH_RESERVE_SCRIPT` | `NWN_CASH_RESERVE_FIGURE` |

**Step 5: Remove now-unnecessary `import re`**

After the regex is gone from `_build_dual_chart_html`, check whether `import re as _re` is still used elsewhere in `charts.py`:

```bash
grep -n "_re\." src/charts.py
```

If the only remaining use is the sticky-header wrapper (`_wrap_table_with_sticky_header`), keep the module-level import — it's still needed there. If ALL regex usage was in the old script extraction code and you can remove the import, do so. (Likely the sticky-header code still uses it — leave it.)

**Step 6: Verify the module parses**

```bash
python3 -c "import ast; ast.parse(open('src/charts.py').read()); print('OK')"
```
Expected: `OK`

**Step 7: Verify no dangling `import re as _re` inside `build_chart`**

```bash
grep -n "import re as _re\|import json as _json" src/charts.py
```
Expected: only the module-level `import re as _re` at line 1175 (or wherever it landed).

**Step 8: Commit**

```bash
git add src/charts.py
git commit -m "refactor: replace eval+regex with JSON lazy-init for subsidiary charts"
```

---

## Task 4: Consolidate `_dual_currency` helpers

**Objective:** Replace the duplicated `_dual_currency` (charts.py:1807) and `_dual_currency_str` (tables.py:1551) with a single shared module-level function.

**Rationale:** Both functions produce identical HTML: dual `<span>` elements for real/nominal toggle. The only difference is that `_dual_currency_str` calls `_fmt_currency` (a function only available in `tables.py`), while `_dual_currency` uses inline f-string formatting. Consolidate to a single source of truth.

**Files:**
- Modify: `src/tables.py` — promote `_dual_currency_str` to module-level, rename to `_dual_value`
- Modify: `src/charts.py` — import and use `_dual_value` from `tables.py` (or extract to `charts.py` if that's the natural home)

**Step 1: Decide the canonical home**

`_dual_value` is used by both `charts.py` and `tables.py`. The simplest approach without creating a cross-import is to put a standalone helper in `tables.py` (which has `_fmt_currency` already) and import it in `charts.py`.

If you want to avoid the cross-module dependency, a standalone `_fmt_dual_value(val)` in `tables.py` that doesn't depend on `_fmt_currency` is cleaner:

```python
def _fmt_dual_value(real_val: float, nominal_val: float | None = None) -> str:
    """Format a monetary value with dual spans for real/nominal toggle."""
    if nominal_val is None:
        return f"${real_val:,.0f}"
    return (
        f"<span class='nwn-view-real'>${real_val:,.0f}</span>"
        f"<span class='nwn-view-nominal' style='display:none'>${nominal_val:,.0f}</span>"
    )
```

This is close to what `_dual_currency` in `charts.py` already does. Replace both with this version, import it where needed.

**Step 2: Replace in `charts.py`**

In `_build_cash_reserve_summary()` (line 1807), replace the nested `_dual_currency` with a call to the shared function.

Since `charts.py` doesn't import from `tables.py`, add an import at the module level of `charts.py`:
```python
from src.tables import _fmt_dual_value  # shared dual-value formatting
```

Then change lines 1838–1839:
```python
f"<td ...>{_dual_currency(tgt, None)}</td>"
f"<td ...>{_dual_currency(min_cash, nominal_min_cash)}</td>"
```
To:
```python
f"<td ...>{_fmt_dual_value(tgt, None)}</td>"
f"<td ...>{_fmt_dual_value(min_cash, nominal_min_cash)}</td>"
```

**Step 3: Replace in `tables.py`**

In `build_tax_table()` (line 1551), replace the nested `_dual_currency_str` with the shared `_fmt_dual_value`.

Change lines 1584–1586:
```python
summary_rows = [
    ("Total taxes paid (all years)", _dual_currency_str(cum_taxes, nom_cum_taxes), True),
    ("Federal total", _dual_currency_str(cum_fed, nom_cum_fed), False),
    ("State total", _dual_currency_str(cum_state, nom_cum_state), False),
```
To:
```python
summary_rows = [
    ("Total taxes paid (all years)", _fmt_dual_value(cum_taxes, nom_cum_taxes), True),
    ("Federal total", _fmt_dual_value(cum_fed, nom_cum_fed), False),
    ("State total", _fmt_dual_value(cum_state, nom_cum_state), False),
```

**Step 4: Remove the nested functions**

Delete the `def _dual_currency(...)` nested function at charts.py line 1807.
Delete the `def _dual_currency_str(...)` nested function at tables.py line 1551.

**Step 5: Verify**

```bash
python3 -c "import ast; ast.parse(open('src/charts.py').read()); print('charts OK')"
python3 -c "import ast; ast.parse(open('src/tables.py').read()); print('tables OK')"
```
Expected: both OK

**Step 6: Run existing tests**

```bash
cd /home/lemurtech/Net-Worth-Navigator
python3 -m pytest tests/ -x -q
```
Expected: all passing (no behavioral change).

**Step 7: Commit**

```bash
git add src/charts.py src/tables.py
git commit -m "refactor: consolidate _dual_currency / _dual_currency_str into shared _fmt_dual_value"
```

---

## Task 5: Add model-layer tests for real-dollar toggle

**Objective:** Add targeted tests verifying the dual-data path works correctly.

**Files:**
- Create: `tests/test_real_dollar_toggle.py`

**Step 1: Create test file**

`tests/test_real_dollar_toggle.py`:

```python
"""Tests for the real-dollar toggle dual-view feature."""

from pathlib import Path
import tempfile
from unittest.mock import patch
import pandas as pd
from src.charts import build_chart
from src.model import ProjectionResult


class TestRealDollarModelLayer:
    """Tests for the model-layer dual-data capture."""

    def test_nominal_yearly_df_is_none_when_real_dollar_basis_false(self):
        """When real_dollar_basis is false, nominal_yearly_df should be None."""
        config = {
            "display": {"projection_title": "Test"},
            "person1": {"name": "Alex", "dob": "1972-06-15"},
            "simulation": {"start_year": 2026, "end_year": 2030, "real_dollar_basis": False},
            "assumptions": {"inflation": 0.03, "stock_return": 0.10, "bond_return": 0.04},
            "spending": {"retirement_annual": 60000},
        }

        # Build a minimal projection result manually for testing
        df = pd.DataFrame([
            {"year": 2026, "total_net_worth": 500000.0, "cash": 50000.0, "taxable": 100000.0,
             "trad_ira": 200000.0, "roth": 150000.0, "home_value": 400000.0, "mortgage": 100000.0,
             "home_equity": 300000.0, "net_worth": 500000.0, "person1_income": 80000.0,
             "person2_income": 0.0, "annual_spend": 60000.0, "annual_taxes": 12000.0,
             "net_flow": 8000.0, "survivor": False, "events_active": "",
             "event_items": [], "freed_payments": 0.0, "required_outflows": 72000.0,
             "event_outflow_total": 0.0, "funding_shortfall": 0.0,
             "annual_federal_taxes": 9000.0, "annual_state_taxes": 3000.0,
             "tax_phase": "pre_retirement", "tax_mode": "standard", "tax_filing_status": "joint",
             "taxable_income": 70000.0, "withdrawal_cash": 0.0, "withdrawal_taxable": 0.0,
             "withdrawal_trad_ira": 0.0, "withdrawal_roth": 0.0,
             "contribution_trad_ira": 0.0, "contribution_roth": 0.0,
             "contribution_total": 0.0, "contribution_employee_trad_ira": 0.0,
             "contribution_employee_roth": 0.0, "surplus_to_taxable": 0.0,
             "surplus_to_trad_ira": 0.0, "surplus_to_roth": 0.0,
             "employer_match_total": 0.0, "employer_match_person1": 0.0,
             "employer_match_person2": 0.0, "taxable_cost_basis": 50000.0,
             "taxable_unrealized_gain": 50000.0, "roth_contribution_basis": 150000.0,
             "roth_earnings": 0.0, "cash_reserve_target": 40000.0,
             },
        ])
        result = ProjectionResult(
            mode="deterministic",
            yearly_df=df,
            summary={},
            simulation={"real_dollar_basis": False},
            nominal_yearly_df=None,
        )
        assert result.nominal_yearly_df is None

    def test_build_chart_no_nominal_when_mode_false(self):
        """build_chart should not emit nominal elements when real_dollar_basis is false."""
        config = {
            "display": {"projection_title": "Test"},
            "person1": {"name": "Alex", "dob": "1972-06-15"},
            "simulation": {"start_year": 2026, "end_year": 2030},
            "assumptions": {"inflation": 0.03, "stock_return": 0.10, "bond_return": 0.04},
            "spending": {"retirement_annual": 60000},
        }
        df = pd.DataFrame([
            {"year": 2026, "total_net_worth": 500000.0, "cash": 50000.0, "taxable": 100000.0,
             "trad_ira": 200000.0, "roth": 150000.0, "home_value": 400000.0, "mortgage": 100000.0,
             "home_equity": 300000.0, "net_worth": 500000.0, "person1_income": 80000.0,
             "person2_income": 0.0, "annual_spend": 60000.0, "annual_taxes": 12000.0,
             "net_flow": 8000.0, "survivor": False, "events_active": "",
             "event_items": [], "freed_payments": 0.0, "required_outflows": 72000.0,
             "event_outflow_total": 0.0, "funding_shortfall": 0.0,
             "annual_federal_taxes": 9000.0, "annual_state_taxes": 3000.0,
             "tax_phase": "pre_retirement", "tax_mode": "standard", "tax_filing_status": "joint",
             "taxable_income": 70000.0, "withdrawal_cash": 0.0, "withdrawal_taxable": 0.0,
             "withdrawal_trad_ira": 0.0, "withdrawal_roth": 0.0,
             "contribution_trad_ira": 0.0, "contribution_roth": 0.0,
             "contribution_total": 0.0, "contribution_employee_trad_ira": 0.0,
             "contribution_employee_roth": 0.0, "surplus_to_taxable": 0.0,
             "surplus_to_trad_ira": 0.0, "surplus_to_roth": 0.0,
             "employer_match_total": 0.0, "employer_match_person1": 0.0,
             "employer_match_person2": 0.0, "taxable_cost_basis": 50000.0,
             "taxable_unrealized_gain": 50000.0, "roth_contribution_basis": 150000.0,
             "roth_earnings": 0.0, "cash_reserve_target": 40000.0,
             },
        ])
        result = ProjectionResult(
            mode="deterministic",
            yearly_df=df,
            summary={},
            simulation={"real_dollar_basis": False},
            nominal_yearly_df=None,
        )
        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / "test.html"
                        build_chart(result, out)
                        html = out.read_text(encoding="utf-8")

        # When real_dollar_basis is false: no nominal chart div, no toggle pill
        assert "nwn-chart-nominal" not in html
        assert "nwn-value-toggle" not in html
        assert "data-nominal" not in html

    def test_build_chart_emits_nominal_divs_when_mode_true(self):
        """build_chart should emit nominal elements when real_dollar_basis is true."""
        config = {
            "display": {"projection_title": "Test"},
            "person1": {"name": "Alex", "dob": "1972-06-15"},
            "simulation": {"start_year": 2026, "end_year": 2030, "real_dollar_basis": True},
            "assumptions": {"inflation": 0.03, "stock_return": 0.10, "bond_return": 0.04},
            "spending": {"retirement_annual": 60000},
        }
        df = pd.DataFrame([
            {"year": 2026, "total_net_worth": 500000.0, "cash": 50000.0, "taxable": 100000.0,
             "trad_ira": 200000.0, "roth": 150000.0, "home_value": 400000.0, "mortgage": 100000.0,
             "home_equity": 300000.0, "net_worth": 500000.0, "person1_income": 80000.0,
             "person2_income": 0.0, "annual_spend": 60000.0, "annual_taxes": 12000.0,
             "net_flow": 8000.0, "survivor": False, "events_active": "",
             "event_items": [], "freed_payments": 0.0, "required_outflows": 72000.0,
             "event_outflow_total": 0.0, "funding_shortfall": 0.0,
             "annual_federal_taxes": 9000.0, "annual_state_taxes": 3000.0,
             "tax_phase": "pre_retirement", "tax_mode": "standard", "tax_filing_status": "joint",
             "taxable_income": 70000.0, "withdrawal_cash": 0.0, "withdrawal_taxable": 0.0,
             "withdrawal_trad_ira": 0.0, "withdrawal_roth": 0.0,
             "contribution_trad_ira": 0.0, "contribution_roth": 0.0,
             "contribution_total": 0.0, "contribution_employee_trad_ira": 0.0,
             "contribution_employee_roth": 0.0, "surplus_to_taxable": 0.0,
             "surplus_to_trad_ira": 0.0, "surplus_to_roth": 0.0,
             "employer_match_total": 0.0, "employer_match_person1": 0.0,
             "employer_match_person2": 0.0, "taxable_cost_basis": 50000.0,
             "taxable_unrealized_gain": 50000.0, "roth_contribution_basis": 150000.0,
             "roth_earnings": 0.0, "cash_reserve_target": 40000.0,
             },
        ])
        # Create a nominal_df with higher values (simulating inflation)
        nominal_df = df.copy()
        nominal_df["total_net_worth"] = 530000.0  # ~6% inflation over 1 year

        result = ProjectionResult(
            mode="deterministic",
            yearly_df=df,
            summary={},
            simulation={"real_dollar_basis": True},
            nominal_yearly_df=nominal_df,
        )
        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / "test.html"
                        build_chart(result, out)
                        html = out.read_text(encoding="utf-8")

        # When real_dollar_basis is true: nominal chart div and toggle pill present
        assert "nwn-chart-nominal" in html, "nominal chart div should be present"
        assert "nwn-value-toggle" in html, "toggle pill should be present"
        assert "data-nominal" in html, "data-nominal attributes on table cells"
        # The nominal figure should be stored as JSON
        assert "NWN_NOMINAL_FIGURE" in html
        # Subsidiary chart JSON variables should exist (not eval scripts)
        assert "NWN_PORTFOLIO_FIGURE" in html
        assert "NWN_LIABILITIES_FIGURE" in html
        assert "NWN_CASH_RESERVE_FIGURE" in html
        # No old-style eval scripts should remain
        assert "NWN_PORTFOLIO_SCRIPT" not in html
        assert "NWN_LIABILITIES_SCRIPT" not in html
        assert "NWN_CASH_RESERVE_SCRIPT" not in html
        # KPI strip should have dual spans
        assert "nwn-view-real" in html
        assert "nwn-view-nominal" in html
        # Value basis bar with toggle pill segments
        assert "💰 Real" in html
        assert "📊 Nominal" in html
```

**Important:** The test above references `build_chart(result, out)` where `result` is a `ProjectionResult` (not a DataFrame). Verify that `build_chart` accepts a `ProjectionResult` — the existing test at `test_recurring_events.py:1012` passes a DataFrame directly, but `build_chart` internally calls `_coerce_projection_result(projection)`. Check whether `build_chart` with a `ProjectionResult` argument works correctly, or adjust to use `projection_result=result` keyword if needed by examining the function signature at `charts.py:2389`:

```
def build_chart(
    projection: pd.DataFrame | ProjectionResult,
    out: str | Path = "",
    config: dict | None = None,
    baseline_config: dict | None = None,
    scenario: object = None,
    sample_guide_path: str = "",
) -> str:
```

Yes — `ProjectionResult` is accepted directly. The test should work.

**Step 2: Run the new tests**

```bash
cd /home/lemurtech/Net-Worth-Navigator
python3 -m pytest tests/test_real_dollar_toggle.py -v
```

Expected: 3 passed.

**Step 3: Commit**

```bash
git add tests/test_real_dollar_toggle.py
git commit -m "test: add model-layer tests for real-dollar toggle dual-view"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
cd /home/lemurtech/Net-Worth-Navigator
python3 -m pytest tests/ -x -q
```

Then do a functional render check with `real_dollar_basis = true`:

```bash
.venv/bin/python run.py --scenario sample --offline
```

Verify the output at `output/scenarios/sample/deterministic/projection.html`:
1. Open in browser
2. Toggle between Real and Nominal
3. Check browser console for zero errors
4. Verify all 4 charts switch (main + portfolio + liabilities + cash reserve)
5. Verify table cells switch
6. Verify KPI values switch
7. Verify toggle pill highlight switches
