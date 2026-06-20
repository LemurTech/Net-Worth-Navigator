# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-19 → 2026-06-20
**Current Status:** V1 is stable, and the next planned architecture shift is a move from one root config to a scenario-based model. The immediate design direction is shared tax-table extraction plus one-scenario-per-file with editor-driven rendering and a manifest-backed shell projections page. The 2026-06-19 model-accuracy audit delivered the core fixes: separate cash return, inflation-consistent spending basis, explicit contribution bucket routing, explicit pre-retirement spending controls, and configurable wage tax treatment (defaulting to `net_cash` for Monarch semantics).

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (cached), fast re-render
- Chart: http://casalemuria.lan/finances/projection.html
- Analysis sidecars now emit per scenario under `output/scenarios/<slug>/sidecars/`: `projection_yearly.csv`, `event_flows.csv`, `scenario_manifest.json`, and `accounts_snapshot.json`
- Accounts tab: trad IRA / Roth / taxable / cash / home equity / total net worth (yearly columns)
- Cash Flow tab: income / portfolio funding withdrawals / living expenses / event outflows / net (yearly columns)
- Portfolio tab: dedicated projected investment portfolio chart for taxable / traditional IRA / 401k / Roth, separate from cash, home equity, and the main net worth view
- First-pass tax modeling is now active: job income remains net cash; Social Security and positive income events are taxed via the 2025 federal ordinary-income bracket schedule plus standard deduction, with effective-rate fallback retained only for compatibility
- Required Minimum Distribution (RMD) modeling is now supported via optional `taxes.rmd` settings: forced annual traditional-account withdrawals based on IRS life-expectancy factors feed modeled cash flow and taxable income
- Ordinary-income tax brackets, standard deductions, simplified Social Security provisional-income thresholds, and Oregon state tax reference data now load from shared tax-table TOML under `config/tax_tables/`, while scenario-specific tax toggles remain in `config.toml [taxes]`
- Event-level taxability is now configurable in `config.toml` via optional `taxable` and `taxable_fraction` fields on `Income` and `SocialSecurity` events
- Withdrawal-source taxation and sequencing are now active: deficits withdraw from cash → taxable → trad IRA → Roth, with taxable/trad withdrawals feeding the bracket-based ordinary-income tax path
- Withdrawal policy is now configurable by lifecycle phase via `[withdrawal_policy]` in `config.toml`
- Phase-specific cash reserve targets are now supported for accumulation, retirement, and survivor periods
- Surplus cash flow now refills the active cash target first, then allocates the remainder into non-cash investable buckets
- Deficit coverage now honors configurable phase-specific withdrawal order using `cash_above_target` / `cash_below_target` semantics to preserve reserves when possible
- Cash Flow tab now shows positive income events in Income and a `Modeled tax on retirement/event inflows` expense row
- End-of-plan timing is now synced from each person's `dob` + `life_expectancy` at runtime so stale hardcoded event years do not skew the chart
- `SellHome` proceeds are now preserved in cash in the sale year rather than being auto-invested into existing non-cash buckets
- `SellHome` can now optionally reinvest some or all positive net proceeds into the taxable brokerage bucket via `reinvest_to = "taxable"` and optional `reinvest_fraction`
- Real-estate appreciation is now separately configurable from CPI via `[assumptions].real_estate_appreciation`, with inflation retained as the backward-compatible fallback when older configs omit the new field
- Retirement timing and Social Security timing/benefits are now synthesized at runtime from person settings (`retirement_year`, `ss_start_age`, and matching `social_security_benefits` with `ss_monthly_benefit` fallback), while preserving legacy event metadata overrides for compatibility
- Survivor spending can now be configured as `survivor_percent_of_retirement`, with runtime survivor-dollar spending derived from `retirement_annual` and legacy `survivor_annual` retained as a compatibility fallback
- Pre-retirement take-home income can now grow annually from inflation plus person-level `annual_take_home_real_raise`, and 401(k) contributions can now grow from that same income path plus person-level `annual_401k_contribution_extra_increase`
- Person-level `annual_take_home_is_net_of_retirement_contributions` is now supported: when true, retirement contributions are treated as payroll-prefunded (still routed into IRA/Roth buckets) and are not subtracted again from implied pre-retirement spending cash
- `Expense` events now support optional `expense_kind = "mandatory" | "discretionary"`; discretionary expenses use 🏖️, mandatory expenses keep 💸, and retirement events now use 🎉
- Cash Flow tab now separates mandatory event expenses from discretionary event expenses while preserving total-expense math
- Gantt tab: enabled-event timeline derived from `config.toml`, with milestone vs span semantics by event type
- Recurring events now expand at runtime for both the model and Gantt via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Recurring event definitions can now set `chart_first_occurrence_only = true` so the event still affects the model and tables on every occurrence while only the first occurrence is annotated on the main projection chart
- Bounded `Income` events now annotate each active year by default (instead of start-year-only); setting `chart_first_occurrence_only = true` still suppresses labels for later recurring occurrences
- New `SpendingShift` event type (MVP: `mode="replace"`) can change retirement/survivor baseline spending from a start year (optionally through `end_year`) to model regime changes like moving countries
- Raw config editor is now available at `http://casalemuria.lan/finances/config/`
- Config editor projection links now append a one-time `refresh=<timestamp>` nonce on click so `Open projection` avoids stale cached pages
- Editor supports validate, save, and save+offline-rerender actions with timestamped backups under per-scenario paths in `output/config-backups/<slug>/`, auto-pruned to the newest 10 per scenario
- The active default scenario now lives in `scenarios/default.toml`; root `config.toml` is a migration fallback only
- The config editor now supports scenario selection, clone/create inputs, and a `Save + Render All` control for batch output refresh
- The public `projection.html` entry point now serves as a scenario shell page backed by `output/scenarios/index.json`, with rendered scenario pages loaded inside an iframe
- Scenario shell iframe URLs now include a version query parameter (`v=<rendered_at/generated_at>`) and expose a `Refresh Frame` control that appends a nonce to force-load the latest rendered scenario page when browser caching gets sticky
- Scenario TOMLs are intended to be local-only working files rather than shared repository state
- Projection page now includes a bottom-fixed `Edit Config` shortcut
- The editor backend now runs as a small FastAPI app, proxied behind the static nginx container
- Gantt includes liability payoff milestones derived from the projection output and uses a centered legend
- Gantt row labels now include event/liability icons, use larger tick-label text, and the Gantt includes a survivor-period band aligned to the projection output
- Assumptions tab now summarizes the current config inputs for people, market assumptions, spending, and withdrawal-policy cash targets
- New Scenario Parameters tab provides per-scenario audit detail (scenario metadata, tax/RMD controls, withdrawal orders/surplus orders, per-person contribution semantics, enabled-event metrics)
- Scenario Parameters supports baseline-vs-default diff emphasis (`param-diff` row styling) and a `Show only differences` toggle
- Diff-only toggle defaults OFF for default scenario and ON for non-default scenarios
- `run.py` now supports scenario-level synthetic start balances via `[data_source].mode = "synthetic"` and `[synthetic_start]` so shareable scenarios can bypass Monarch/cache entirely
- Added a share-safe `scenarios/sample.toml` synthetic scenario with realistic recurring/one-time events (home maintenance, roof/HVAC replacement, vehicle purchase/replacement, travel, consulting)
- Synthesized retirement/SS labels now use configured person-name initials (e.g., A/S in sample scenarios) instead of hardcoded person-key initials (M/W)
- Gantt row pitch and bar geometry were tuned together for a denser layout: slimmer bars, materially less vertical whitespace, and a more compact overall chart height
- Both tables scroll horizontally, yearly tick columns
- First-column labels and section bands are frozen via JS `translateX(scrollLeft)` + `requestAnimationFrame`
- Table navigation now supports grab-and-drag panning and moderated wheel-to-horizontal scrolling
- Main chart now uses 2-year x-axis ticks with ages shown below each year for Person 1/Person 2 in `(M/W)` form
- Negative-only liquid series now remain visible on the main chart instead of disappearing when their summed values are below zero
- Projection model now supports `SellHome` events keyed to named real-estate accounts, with configurable/default sale-fee rates and optional mortgage payoff linkage
- Projection page now includes a KPI summary strip above the chart: Net Worth (EOY), Net Worth at Retirement, Retirement Age (first retiree), and Net Worth at End
- Page chrome, tables, and both Plotly charts now use a cohesive dark theme
- Main chart subtitle/label after `Net Worth Navigator —` is now configurable via `[display].projection_title` in `config.toml`

## Cron Jobs

| Job | ID | Schedule | Delivery |
|---|---|---|---|
| NWN — monthly full run | `43255de12c21` | 1st of month, 6am | Telegram |
| NWN — offline render | `da16c8dcea42` | Manual only | local |

**Manual trigger:** `hermes cron run <job_id>`

## Resuming This Project

Load the `personal-finance-modeling` skill — it contains all project
context, run commands, file structure, V1 inventory, and V2 candidates.
Then load `docs/activeContext.md` from the repo for current iteration state.

## Open Items for Next Session

### Model Accuracy Findings (2026-06-19, ordered by impact)

1. **Cash bucket currently overstates growth** when modeled with blended invested return. Started fix: cash now has a dedicated `assumptions.cash_return` path (fallback to inflation) instead of inheriting the stock/bond blend.
2. **Wage tax treatment is now configurable and set to net-cash in default scenario.** `taxes.wage_tax_treatment` supports `net_cash` (current default) and `taxable_wages`; with `net_cash`, wages remain cashflow-only and do not enter ordinary-income tax or Social Security provisional-income calculations.
3. **Retirement/survivor spending was flat nominal despite “today’s dollars” comments.** Started fix: `[spending].spending_basis = "real"` now inflates retirement/survivor targets by CPI; `nominal` remains available as an explicit mode.
4. **401(k)/IRA contributions now route to explicit destination buckets** (`trad_ira` / `roth`) before generic surplus allocation, with optional per-person bucket overrides (`annual_401k_contribution_bucket`, `annual_ira_contribution_bucket`). IRS caps/employer match logic is still pending.
5. **Pre-retirement spending control is now implemented with explicit precedence.** The model now applies: `pre_retirement_spending` (highest) → `annual_savings_override` → implied `total_income - cash_required_total_contrib`, with real-dollar inflation handling when `spending_basis = "real"` and support for payroll-prefunded contributions via `annual_take_home_is_net_of_retirement_contributions`.

### Next implementation slices after current in-progress fixes


- Execute the next scenario-transition slice in [scenario-transition-plan.md](scenario-transition-plan.md)
  - retire the root `config.toml` fallback once the scenario workflow is fully in place
  - decide whether to add scenario deletion/rename management or keep clone-plus-manual-edit as the supported workflow
- Design the scenario manifest and default-scenario source of truth before wiring the shell projections page
- Decide whether root `config.toml` gets a short compatibility window or a one-cut migration into `scenarios/default.toml`
- Confirm the survivor spending percentage feels right (currently 70% of retirement spending)
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available
- Validate the new `[withdrawal_policy]` defaults against Person 1's intent
  - accumulation cash target = $64,000 (roughly current liquid reserve)
  - retirement cash target = $95,000 (roughly one year of planned retirement spending)
  - survivor cash target = $66,500 (roughly one year of planned survivor spending)
- Decide whether retirement / survivor withdrawal order should stay `cash_above_target → taxable → trad_ira → roth → cash_below_target` or be tuned further
- Current build target: deeper tax realism
  - bracket-based federal ordinary-income tax model is now the active implementation path
  - simplified Social Security provisional-income banding is now active, but wages still do not enter the provisional-income test because employment income remains net cash in the model
  - Oregon state tax treatment is now active; next state-tax work is refinement/validation rather than first implementation
    - official-source confirmation of Oregon Social Security treatment can be saved for a later pass
    - breaking Cash Flow taxes into separate federal/state rows can also wait for a later pass
  - Gross-income migration for wages is optional, not required, unless the project later aims to model a true full household tax return instead of Monarch-style net-income cash flow
  - route taxable withdrawals and Social Security through the richer tax model without changing current net-income semantics for job income

- Decide whether V2 should stay with raw TOML editing only or add structured form sections for simple config fields
- Extend the config editor toward scenario management only after per-scenario output paths and manifest generation are in place
- Surgery event amount is $18,000 in config — Person 1 confirmed this is correct

## Known Pitfalls

- Monarch auth expires periodically → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- Plotly `add_vrect` annotation_text collides with vline labels — use separate `add_annotation` with `yref="paper"` instead
- `annotation_textangle=-90` + `annotation_position="top right"` is the correct vertical label approach
- `output/` is gitignored — do not commit generated HTML or cache
- For routine NWN UI/layout tweaks, prefer targeted checks plus a real `python run.py --offline` render; reserve the full test suite for broader model or semantic changes
