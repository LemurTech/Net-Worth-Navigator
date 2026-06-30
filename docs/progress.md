# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.
Entries belong under a `## YYYY-MM-DD` date header. The `## [Unreleased]` pattern is retired.

## 2026-06-29

### Added

- **Sticky table headers** (`src/charts.py`): Build-time table splitting via `_wrap_table_with_sticky_header()`. Each `<table class='datatable'>` is split into a `.sticky-header-wrap` (sticky header, no overflow ancestor → `position: sticky; top: 0` works) + `.table-scroll` (horizontal scroll container). Both tables use `table-layout: fixed` with explicit `<colgroup>` pixel widths (label=210px, each year=110px) so column alignment is guaranteed identical — no runtime measurement or clone-syncing needed.

- **Horizontal overscroll fix** (`src/charts.py`): Fixed by `table-layout: fixed` + explicit total width on both tables. `scrollWidth` now exactly matches sum of column widths — no overshoot past the last column. The `.table-scroll` wrapper handles all scroll/wheel/drag behavior.

### Changed

- **CSS** (`src/charts.py`): `.table-panel` loses `overflow-x: auto; cursor: grab` and gains `position: relative`. New `.sticky-header-wrap` (sticky, top:0, z-index:10, background/border-bottom) and `.table-scroll` (overflow-x:auto, cursor:grab, drag states). Split tables use `border-radius: 6px 6px 0 0` (header) and `border-radius: 0 0 6px 6px` (body) for continuous visual.

- **JS** (`src/charts.py`): Scroll/wheel/drag handlers now target `.table-scroll` instead of `.table-panel`. `syncLabels()` scoped to each `.table-scroll`'s child rowlabels. Year-highlight click handler unchanged — works across both tables via shared `data-col` attributes.

- **All datatable call sites** (`src/charts.py`): `accounts_html`, `cashflow_html`, `tax_html`, `portfolio_table_html` (×2), `table_html` (simulation) all pass through `_wrap_table_with_sticky_header()` in their respective build functions.

### Added

- **Favicon** (`src/charts.py`): Inline SVG favicon data URI in HTML `<head>` — dark rounded square with blue trend line over bar columns, matching the dark theme.

- **Mobile event-label defaults** (`src/charts.py`): On screens narrower than 768px, the chart now defaults to showing only key events (Show all unchecked, Keep key labels checked) on first load. User can toggle back manually.

- **Employee-only contribution columns** (`src/model.py`): New DataFrame columns `contribution_employee_trad_ira`, `contribution_employee_roth`, `contribution_employee_trad_ira_person1/2`, `contribution_employee_roth_person1/2` — employee-only retirement contributions excluding employer match.

### Changed

- **Cash Flow table** (`src/tables.py`): Per-person contribution rows now use employee-only columns and are labelled `Employee 401k/IRA — Person 1` / `Person 2`. Aggregate rows (`Traditional IRA / 401k contributions`, `Roth contributions`) also use employee-only totals so they match the sum of per-person rows. Employer match rows are shown separately. Per-person employer match rows now appear independently when non-zero (previously required both people to have non-zero match).

- **Household scenario TOMLs**: All 6 scenarios (default, comfortable, optimistic, restrictive, early-death-person1, early-death-person2) updated:
  - `retirement_contribution_percent` → 0.24 (hits $31K IRS cap from year 1)
  - `annual_401k_contribution_split` → 70/30 (trad/Roth)
  - Cash targets → $40K accumulation, $50K retirement, $30K survivor
  - Comments updated to match

- **Default scenario**: Stale comment on line 67 (`# 16%` → `# 24% of gross income ($31K IRS cap)`). Withdrawal policy comments updated.

### Fixed

- **Freed payment calculation** (`src/model.py`): All four sites where freed payments are computed (amortization payoff loop, SellHome liability payoff, auto_reduce active P&I) now use `monthly_base` (contractual P&I) instead of `monthly_total` (which included voluntary `monthly_extra`). Voluntary extra principal is no longer treated as permanently freed cash flow. Also added `monthly_base` to the liability state dict.

- **Event vlines hidden with annotations** (`src/charts.py`): `applyEventLabelVisibility()` JS now also toggles corresponding vline shapes when annotations are hidden. Previously only annotation text visibility was toggled, leaving vertical lines visible.

- **Cash Flow Roth contribution mismatch**: Total `Roth contributions` row was including employer-match Roth portions (5% of match via 95/5 split), creating a gap vs per-person rows. Fixed by making all aggregate contribution rows employee-only. The employer-match Roth portion ($391 in 2026) is now correctly contained within the `Employer match` row.

### Removed

- **Three early-mortgage scenario files**: `default-early-mortgage.toml`, `comfortable-early-mortgage.toml`, `optimistic-early-mortgage.toml` deleted. The early-mortgage scenario's `monthly_base` was also corrected to use `monthly_extra = 1000` before deletion.

### Added

- **Ordered-priority surplus routing** (`src/model.py`): `_apply_surplus_with_reserve_target` now distributes surplus as a strict priority chain via `*_surplus_order` instead of proportional-by-balance. Default order changed from `["taxable", "roth", "trad_ira"]` to `["roth", "taxable"]`. First non-excluded bucket receives ALL remaining surplus; if empty or excluded, falls through to the next. Cash remains the final backstop when no bucket in the order is available. Removed `_surplus_fallback_bucket` (no longer needed).

- **Roth IRA contribution caps on surplus routing** (`src/model.py`): New `_IRS_ROTH_IRA_LIMIT_*` constants, `_roth_ira_limit()` function (returns $7K under 50, $8K 50+ per person), and `_person_ira_contribution_to_roth()` helper. Household Roth surplus cap computed yearly: sum of per-person limits minus planned IRA contributions going to Roth. Applied via new `step_caps` parameter on `_apply_surplus_with_reserve_target`. Cap only active during accumulation (at least one person working); removed after both retire. Excess above cap spills to the next bucket in surplus_order.

- **SellHome reinvestment timing fix** (`src/model.py`): Pending reinvestments (e.g. `reinvest_to="taxable"`) are now processed inside the tax iteration loop, BEFORE the surplus sweep, so reinvestment proceeds reach their target bucket before the ordered priority applies. Previously ran after the loop, leaving no cash for reinvestment after the sweep.

- **Surplus Routing section in Cash Flow table** (`src/tables.py`): Dedicated rows for `Surplus to Roth`, `Surplus to taxable brokerage`, `Surplus to traditional IRA / 401k`. Data already tracked via `surplus_to_*` DataFrame columns.

### Changed

- **Scenario TOML surplus orders**: All 9 personal scenario files updated from `["taxable", "roth", "trad_ira"]` to `["roth", "taxable"]` for all three phases (accumulation, retirement, survivor). `restrictive.toml` kept its differentiated retirement/survivor `["taxable"]` orders unchanged. Sample scenarios left as-is.

### Fixed

- **Zero-surplus deficit branch owner-balance sync** (`src/model.py`): When a deficit is covered from cash and remaining excess cash is swept to a retirement bucket, `owner_balances` are now updated alongside the portfolio. Previously `_sync_retirement_bucket_totals` would overwrite the sweep with stale owner balances, causing Roth/trad_ira surplus additions to disappear during deficit years.

## 2026-06-24

### Fixed

- **Compare page — portfolio chart drop-to-zero bug.** Caused by JS `parseCSV()` using naive `line.split(',')` which split on commas inside quoted CSV fields. The `events_active` column contains comma-separated event labels (e.g. `🎉 Retirement (M), 🏛️ SS Begins (M)`), and 6 of 41 rows had those internal commas treated as field delimiters, shifting `taxable`/`trad_ira`/`roth` into wrong columns. Replaced with a state-machine `parseCSVLine()` parser in `src/scenario_shell.py` that tracks `inQuotes` and handles escaped quotes.
- **Compare page — delta chart bottom-left label overlap.** Y-axis `+$X.XXM` labels (wider due to `+` prefix) encroached on x-axis year labels in the corner. Increased `margin.l` (80→100), `margin.b` (56→72), `xaxis.ticklabelstandoff` (12→16), and `xaxis.title.standoff` (10→20) on the delta chart layout in `src/scenario_shell.py`.

## 2026-06-23

### Added

- **Phase 4 — Employer match and IRS 401(k) cap enforcement** (`src/model.py`, `src/tables.py`):
  - IRS employee elective deferral limits enforced at runtime: $23,500 base + $7,500 catch-up at age ≥ 50 (2025 values). Update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` annually.
  - New per-person config field `annual_401k_employer_match` (flat annual $). Always prefunded; routes through same `annual_401k_contribution_split` as employee. Person 1's household value: $5,688/yr, set in all 9 household scenario TOMLs.
  - New projection DataFrame / sidecar columns: `employer_match_total`, `employer_match_person1`, `employer_match_person2`, `person1_401k_over_irs_cap`, `person2_401k_over_irs_cap`.
  - Cash Flow tab: dedicated employer match row; amber ⚠ cap-exceeded warning banner.
  - Scenario Parameters: `401k employer match (annual)` diff row per person.
- **Scenario comparison page** (`src/scenario_shell.py`):
  - `compare.html` deployed at `/finances/compare.html` — reads sidecar CSVs and `simulation_summary.json` at runtime.
  - Scenario chip toggles (stable colour per slug, min 2 active), mode selector (deterministic / historical / monte_carlo).
  - Three Plotly charts: Total Net Worth trajectory, Investable Portfolio trajectory, Net Worth Delta (scenario − default).
  - KPI table with delta highlighting vs default; MC mode adds probability of success, worst-decile terminal NW, P10/P90, median first failure year, peak pressure rate.
  - Deep-linking via `?a=slug&b=slug` URL params; shell "Compare Scenarios" button pre-scopes to active vs default.
- **Scenario rename** (`admin_app.py`, `templates/config_editor.html`): `POST /rename-scenario` rewrites `[scenario]` block, moves TOML if slug changes, triggers offline render, redirects. Rename fields + button in config editor (disabled on default scenario).
- **Scenario deletion** (`admin_app.py`, `templates/config_editor.html`): `POST /delete-scenario` with slug-confirmation dialog; blocks deletion of default scenario; removes TOML + rendered output; triggers manifest refresh.
- **Two share-safe synthetic demo scenarios**: `sample-a.toml` (moderate: 7% equity, retirement 2038/2043, $82K/yr spending) and `sample-b.toml` (growth: 8.5% equity, retirement 2035/2037, $98K/yr, delayed SS to 70, $6K employer match). Both use Alex & Sam personas.

### Fixed

- Simulation tab legend responsive fix: `nwn-simulation` block added to `applyResponsiveChartLayout()` — legend moves below chart at ≤900px.
- Shell page: "Refresh Frame" button hidden on screens ≤980px; bracketed `[Mode]` suffix removed from scenario description text.
- Compare page: mode selector CSS background shorthand was malformed (missing comma between gradient layers), causing white fallback. Fixed to match shell page pattern.
- Compare page: y-axis title overlap fixed — `automargin: true` + `margin.l = 80` required alongside `standoff`; `standoff` alone is insufficient when left margin is too narrow.

---

## 2026-06-19 to 2026-06-22

### Added

- Monte Carlo simulation mode: seeded multi-run engine, `num_runs`, `seed`, `portfolio_return_volatility`; probability-band charts; stochastic KPI strip; Simulation tab with outcome-timing chart and yearly outcomes table.
- Historical-sequence simulation mode via `simulation.historical_returns_path` CSV; bundled starter dataset at `config/return_sequences/us_balanced_returns.csv`; turnkey without a user-supplied file.
- Configurable stochastic success/failure via `[monte_carlo.success]`: `failure_mode`, spending-funded threshold, home-equity/debt allowances, grace-period months.
- Normalized `ProjectionResult` contract in `src/model.py` shared by deterministic, Monte Carlo, and historical modes.
- Richer stochastic summary metrics: probability of success, spending shortfall, liquid depletion, net worth below zero, home-equity rescue; median/worst-decile terminal NW; first-failure distribution.
- Stochastic outcomes sidecar: `simulation_outcomes_yearly.csv` per run.
- Tax engine refactor: explicit yearly `YearlyTaxInputs` / `YearlyTaxOutputs` contracts in `src/tax_model.py`; `tax_breakdown_yearly.csv` sidecar; dedicated `Tax` tab in projection page.
- Federal bracket-based ordinary-income tax + Oregon state tax layer; SS provisional-income banding; configurable filing status per lifecycle phase; shared tax tables in `config/tax_tables/`.
- RMD modeling via `[taxes.rmd]`: forced traditional-account withdrawals from IRS life-expectancy factors.
- Richer account mechanics: taxable brokerage tracks cost basis vs. unrealized gains; Roth tracks contribution basis vs. earnings; optional basis seeding via `taxable_cost_basis`, `roth_contribution_basis`.
- Owner-level retirement bucket split: `trad_ira_person1/person2`, `roth_person1/person2` through projection pipeline; Accounts and Portfolio show per-person split; labels use configured person display names.
- Per-person `annual_401k_contribution_split` for routing employer-plan contributions proportionally between traditional and Roth.
- Account-level `owner` and `opening_balance_split` metadata in `[accounts]` inline tables for Monarch reclassification.
- `Expense` event `funding = "cash_reserve_first"` override; `expense_kind = "mandatory" | "discretionary"` categorisation.
- `SpendingShift` event type (`mode = "replace"`) for baseline spending regime changes.
- Survivor modeling improvements: survivor phase starts immediately after death; widow/er SS step-up via `survivor_ss_start_age`.
- Pre-retirement spending explicit precedence chain; `spending_basis = "real" | "nominal"` CPI indexing.
- `annual_take_home_is_net_of_retirement_contributions` payroll-prefunded flag.
- Phase-specific withdrawal policy (`[withdrawal_policy]`): per-phase cash targets, configurable withdrawal and surplus order.
- `SellHome` / `BuyHome` event improvements: proceeds preserved in cash; optional `reinvest_to`; real-estate property state tracking; `real_estate_appreciation` separate from CPI.
- Recurring events via `repeat_every_years` / `repeat_until_year` / `repeat_count`; `chart_first_occurrence_only` flag.
- Scenario comparison infrastructure: `compare.html`, deep-linking, delta chart (shipped 2026-06-23; listed here for completeness).
- Static definitions/reference page (`definitions.html`) linked from shell, projection pages, and config editor.
- Config editor: scenario clone, delete, rename; async render jobs with progress overlay; `Save + Render All`; timestamped backups; scenario-scoped projection/editor URL propagation.
- Public shell page: two-dimensional scenario + mode selector; iframe with version nonce; `Refresh Frame` control.
- Share-safe sample scenario (`scenarios/sample.toml`) with synthetic balances.
- `ignidash-comparative-analysis.md` and `ignidash-feature-port-plan.md` added to `docs/`.

### Fixed / Changed

- Main chart: 2-year x-axis ticks; age labels below year ticks; configurable chart title via `[display].projection_title`; event-label wrap and control strip.
- Gantt: denser row pitch, milestone vs span semantics, liability payoff milestones from projection output, survivor-period band, centered legend.
- Scenario Parameters: baseline-diff emphasis, `Show only differences` toggle, `Retirement ownership snapshots` card, `Tax output snapshot` card.
- Assumptions tab: baseline-diff support and `Show only differences` toggle.
- Horizontal table UX: JS `translateX(scrollLeft)` frozen first column + section bands, grab-to-pan, wheel-to-horizontal scroll.
- Portfolio tab: investable-only chart, projected-balances table, zero-taxable display cue, no cash bucket.
- KPI strip above main chart: Net Worth (EOY), Net Worth at Retirement, Retirement Age, Net Worth at End.
- `cash_return` separate from blended investable return; `wages.wage_tax_treatment` config.
- Cohesive dark theme across chrome, tables, and all Plotly charts.

