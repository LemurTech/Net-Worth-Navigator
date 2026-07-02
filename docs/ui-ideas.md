# Net Worth Navigator — UI Improvement Ideas

| Idea | Status | Notes |
|---|---|---|
| Sticky table headers | ✅ Done | Build-time split: header wrapper (sticky) + body scroll wrapper |
| Frozen first column (row labels) | ✅ Done | JS transform + box-shadow in scroll sync handler |
| Horizontal grab-to-pan scroll | ✅ Done | Mousedown-drag on `.body-scroll` and `.tabulator-tableholder` |
| Column highlighting (click year → highlight all tables) | ✅ Done | `data-col` attributes + event delegation on `document` |
| Deselect all highlights (double-click / Esc / Account header) | ✅ Done | Double-click year header, click "Account" header, or press Escape |
| Overscroll dead space fix | ✅ Done | `overflow: hidden` on `.datatable` + wider year columns (130px) |
| Surplus bar visualization removed | ✅ Done | Replaced with simple numeric row; breakdown in individual rows above |
| Mobile legend/x-axis overlap (Cash Flow chart) | ✅ Done | Matched Portfolio chart height (420px), margins, legend bgcolor |

---

## Chart & KPI Layer

### Goal / reference lines on the chart
🔄 Partially done — Cash Reserve tab shows dashed stepped target lines for cash reserves per phase. Main-chart milestone lines not yet implemented.

### Year-range scrubber
A dual-handle range slider below the chart to zoom into a specific decade (e.g., 2030–2040). The full start→end view compresses the interesting transition years (retirement, mortgage payoff, SS start). A scrubber lets you focus on the decade that matters without editing projection parameters.

### Snapshot composition at hover or click
The main chart is a stacked area showing net worth composition over time. The tooltip currently shows only the total. Show the per-bucket breakdown at hover (cash / taxable / trad IRA / Roth / home equity) plus the year-over-year delta.

### Cash reserve gauge
✅ Done — New Cash Reserve tab with cash-balance vs phase-target chart, below-target highlighting (red/orange fill), and summary card with per-phase status.

---

## Table Layer (Accounts, Cash Flow, Portfolio, Tax)

### Surplus routing visualization in Cash Flow
The Cash Flow table shows a "Surplus Routing" section with per-bucket additions as numbers. A small horizontal stacked bar per year showing how surplus was split across Roth → taxable → trad_ira would make the routing policy's real effect visible at a glance, without scanning columns of numbers.

### Row-highlight cross-referencing
Click a row in any table → all tabs highlight that year. Helps trace a specific year's story across Income, Expenses, Portfolio, and Tax tabs.

### Tax tab cumulative summary row
A summary row at the bottom of the Tax tab showing total taxes paid lifetime and average effective tax rate. Puts tax drag in perspective.

---

## Scenario & Navigation

### Scenario brief card on the shell page
When you select a scenario in the dropdown, a compact "Brief" appears showing only what differs from default — retirement year, stock return, cash target delta. Quick orientation without loading the full diff.

### Side-by-side KPI comparison
Mini-KPIs (net worth at retirement, end-of-plan balance, retirement age) in the shell page as a stacked comparison row — one column per selected scenario. Lets you compare trajectory outcomes without loading a separate page.

### Keyboard shortcuts for the shell page
Left/right arrow to cycle scenarios, number keys to switch render modes (1=deterministic, 2=historical, 3=MC), R to refresh iframe.

---

## Config Editor

### Quick-edit panel for frequent controls
✅ Done — Structured controls above the raw editor with data source radio, cash targets, returns, retirement years, drag-reorder chips. Backed by tomlkit API endpoints.

### Scenario cloning from the UI
✅ Done — "Clone Scenario" button in the quick-panel action bar prompts for name/slug/description, creates the new TOML file, and redirects.

### "What-if" quick re-render
One or two sliders (e.g., stock return ±, retirement year ±) that re-render only the deterministic chart in real-time — no full model run, just a live chart update. Useful for exploring sensitivity without committing to a new scenario TOML.

---

## New Views

### Liabilities payoff calendar
✅ Done — See the new Liabilities tab. Shows a Plotly debt payoff trajectory chart above a year-by-year amortization table with per-liability balance decline, payoff-year callout (✓), rate and monthly payment in the row label.

### Export buttons in page chrome
Download current chart as PNG, projection data as CSV, event schedule as CSV. The sidecars already write these files — surface them with download links in the shell page toolbar.

### Sensitivity overlay mode
A toggle on the chart that lets you pick a parameter (inflation, stock return, retirement age) and a range (±1%, ±2%) and overlays those trajectories as thin transparent lines behind the main projection. Shows the fan without needing separate manual scenario clones.

### Net Worth composition at milestone years
A small 100% horizontal bar or treemap below the chart showing the portfolio mix at key milestones (today, retirement year, mortgage payoff, end-of-plan). Quick visual check on whether Roth/trad mix and home equity are in a healthy range.

### Render progress persistence
The render modal already shows progress. When the user navigates away or closes the tab mid-render, the job continues server-side but the user has no way to know it completed. A notification or job-status indicator in the editor chrome would close this gap.

---

## Data Source & Monarch Bridge

### Data source management UI
✅ Done — Data Sources & Accounts tab in the Setup Panel shows each account's source (cache/Monarch), balance, category dropdown, and disabled checkbox. Refresh from Monarch button. Cache timestamp displayed.

### Manual balance entry (non-Monarch path)
✅ Done — Synthetic Setup tab with structured form for investable balances, non-investable assets, property values (add/remove), auto-detected liability balances. Writes `[synthetic_start]` and toggles `data_source.mode`.

### Data freshness indicator on the shell page
✅ Done — Green/yellow dot + "Live balances: <date>" shown below the title in the scenario shell page. Hidden when no cache is available (synthetic mode). Turns yellow with days-old count when cached data is >30 days stale.

### Account classification editor
✅ Done — Data Sources & Accounts tab lists Monarch accounts with category dropdowns, disabled checkbox, and unmatched accounts section. Saves to `[accounts]` via tomlkit.

### Balance import/export
Support importing starting balances from CSV or JSON for users who track accounts in a spreadsheet or different tool. One-shot import populates `[synthetic_start]`. Export current cached balances as CSV for external analysis.

### Balance history mini-chart
If the cache is retained across runs (it's a single snapshot now), we could store timestamped snapshots and show a mini trend line per account. Not actionable for the model but useful for "am I trending in the right direction?" check-ins between full projection runs.

### First-run setup wizard
Detect whether Monarch is available on first launch. If yes, walk through the Monarch connection + initial classification flow. If no, walk through manual balance entry. Today both paths are filesystem operations with no guided UI.

---

## ~~Windows Compatibility~~ ✅ DONE (2026-07-02)

**Status:** Implemented. Cross-platform path detection added to `monarch_bridge.py` via `_mcp_python_binary()` function. README and `starter.toml` now show both Linux/macOS and Windows commands. New `docs/windows-compatibility.md` guide added.

The app is cross-platform: pure Python 3.14, Plotly HTML output, FastAPI config editor, `pathlib.Path` throughout.

### ~~Monarch bridge paths (the main blocker)~~ ✅ FIXED
**Was:** `monarch_bridge.py` hardcoded Linux paths (`/opt/monarch-mcp-server/.venv/bin/python3`).  
**Now:** Uses `sys.platform` detection — Windows gets `.venv\Scripts\python.exe`, Unix gets `.venv/bin/python3`. Configurable via `MONARCH_MCP_PATH` env var.

### ~~Run commands~~ ✅ FIXED
**Was:** Docs showed only `.venv/bin/python run.py`.  
**Now:** README and `starter.toml` show both Linux/macOS and Windows examples side-by-side.

### Deployment / serving output
Currently served via nginx (Docker) at casalemuria.lan. On Windows, options:
- **Direct file open** — the HTML output is entirely self-contained (inline Plotly, embedded CSS). Just double-click `output/projection.html`.
- **`python -m http.server`** — one-command local server for the config editor and API.
- **PyInstaller bundle** — single `.exe` that embeds the server and opens the browser, zero-dependency.

### Persistent state paths
The app writes output and cache to relative paths (`output/`, `output/balances_cache.json`). Already portable. No registry, no `/var`, no systemd.

### Summary of remaining work (optional enhancements)
- A `run.py --serve` or `run.py --open` flag for convenience
- Optionally: a `pyproject.toml` entry point so `pip install` makes `nwn` a CLI command


