# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-19 → 2026-06-23
**Current Status:** NWN now has both seeded Monte Carlo / turnkey historical modes, the first richer-account-mechanics slice from the ignidash port plan, a static definitions/reference page, and a new scenario comparison page (`compare.html`). The config editor now supports scenario deletion. Several small UI fixes landed this session: Simulation tab legend responsive fix, Refresh Frame hidden on small screens, bracketed mode label removed from shell description, y-axis title standoff corrected on the compare page.

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (cached), fast re-render
- Chart: http://casalemuria.lan/finances/projection.html
- Each scenario render now emits mode-specific artifacts under `output/scenarios/<slug>/<mode>/` for `deterministic`, `historical`, and `monte_carlo`, with the shell page selecting among them via scenario + mode selectors
- Analysis sidecars now emit per scenario under `output/scenarios/<slug>/sidecars/`: `projection_yearly.csv`, `event_flows.csv`, `scenario_manifest.json`, `accounts_snapshot.json`, and `simulation_summary.json`; Monte Carlo runs also emit `projection_bands_yearly.csv`
- Stochastic sidecars now also emit `simulation_outcomes_yearly.csv`, a yearly outcomes surface for success-through-year, cumulative failure, current-year trigger rate, funded-ratio percentiles, and net-worth distribution
- Projection outputs now flow through a normalized `ProjectionResult` contract in `src/model.py`, with deterministic runs exposing a single yearly path and Monte Carlo runs exposing a median display path plus percentile bands
- `[simulation]` now supports `mode`, `num_runs`, `seed`, and `portfolio_return_volatility` so scenarios can opt into seeded Monte Carlo without changing other config semantics
- `[simulation]` historical mode is now supported via `historical_returns_path`, using rolling annual-return windows from a CSV with `year` and `return` columns
- Historical mode is now turnkey with the bundled starter dataset at `config/return_sequences/us_balanced_returns.csv`; the default scenario can switch to `mode = "historical"` without requiring a user-supplied local file
- `[monte_carlo.success]` now controls stochastic failure semantics, including `failure_mode`, `minimum_spending_funded_ratio`, home-equity/debt allowances, and `failure_grace_period_months`
- Stochastic projection pages now show probability-band charts for total net worth and investable portfolio, stochastic KPI strips, and a `Simulation results` summary card in Scenario Parameters
- Stochastic projection pages now also get a dedicated `Simulation` tab with an outcome-timing chart plus a yearly outcomes table driven by the same normalized stochastic results bundle
- The stochastic outcomes bundle now distinguishes raw yearly pressure triggers from actual rule failure, so grace-based modes like `spending_shortfall` can show “temporary pressure” separately from true plan failure
- Stochastic summaries now publish a broader risk/terminal-metrics surface: probability of success, spending shortfall, liquid depletion, net worth below zero, and home-equity-required rescue, plus median/worst-decile terminal net worth and first-failure-period distribution
- The tax path now uses explicit yearly tax input/output contracts centered in `src/tax_model.py`, with normalized federal/state tax-system objects and a dedicated `tax_breakdown_yearly.csv` sidecar for auditability
- Tax outputs now also expose richer yearly subcomponents such as other-taxable-income, Social Security taxable fraction, provisional income, deduction-adjusted federal taxable income, and state taxable income before/after deduction
- Taxable brokerage balances now track remaining cost basis separately from unrealized gains, so taxable withdrawals feed taxes from realized-gain portions instead of a flat bucket fraction once the opening basis state is seeded
- Roth balances now also track contribution basis separately from earnings, with yearly outputs surfacing Roth withdrawal basis vs. earnings portions for auditability and future tax-rule refinement
- Optional basis seeding is now supported via synthetic-start amounts (`taxable_cost_basis`, `roth_contribution_basis`) or account metadata (`basis_fraction`, `roth_contribution_basis_fraction`) when a scenario needs a better opening approximation than the legacy taxable-withdrawal fraction fallback
- The public site now also emits `output/definitions.html`, a static reference page grouped by scenario metadata, simulation, people, spending, withdrawal policy, taxes, assumptions, accounts, and events
- Projection pages, the public scenario shell, and the config editor now all expose a `Definitions` link that opens the static reference page in a new tab
- Scenario TOML comment blocks were harmonized across the full scenario set so the new basis/bucket metadata is described consistently everywhere without expanding into a full handbook inside each file
- Accounts tab: trad IRA / Roth / taxable / cash / home equity / total net worth (yearly columns)
- Cash Flow tab: income / portfolio funding withdrawals / living expenses / event outflows / net (yearly columns)
- Portfolio tab: dedicated projected investment portfolio chart for taxable / traditional IRA / 401k / Roth, separate from cash, home equity, and the main net worth view
- Portfolio tab now also includes a projected-balances table directly below the chart, with owner-split retirement rows when available
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
- Cash Flow can now break modeled taxes into federal and state rows when those components are non-zero, and Scenario Parameters now includes a `Tax output snapshot` card sourced from the rendered projection
- The tax snapshot card now includes the main explanatory subcomponents behind the current year's modeled taxes rather than only top-line tax totals
- Projection page now includes a dedicated `Tax` tab with a yearly audit table for tax context, taxable-income components, federal/state deductions, effective rates, and total modeled taxes
- End-of-plan timing is now synced from each person's `dob` + `life_expectancy` at runtime so stale hardcoded event years do not skew the chart
- `SellHome` proceeds are now preserved in cash in the sale year rather than being auto-invested into existing non-cash buckets
- `SellHome` can now optionally reinvest some or all positive net proceeds into the taxable brokerage bucket via `reinvest_to = "taxable"` and optional `reinvest_fraction`
- `BuyHome` now creates/updates tracked property state when `price` is provided, so future home purchases feed `home_value` / `home_equity` instead of only reducing cash
- Real-estate appreciation is now separately configurable from CPI via `[assumptions].real_estate_appreciation`, with inflation retained as the backward-compatible fallback when older configs omit the new field
- Retirement timing and Social Security timing/benefits are now synthesized at runtime from person settings (`retirement_year`, `ss_start_age`, and matching `social_security_benefits` with `ss_monthly_benefit` fallback), while preserving legacy event metadata overrides for compatibility
- Survivor phase now starts immediately in the first full model year after a person's `EndOfPlan`, even if the surviving partner is still working; survivor spending, tax phase, and survivor chart state no longer wait for both partners to be retired
- Survivor-period shading in the main chart and Gantt is now drawn from the deceased partner's `EndOfPlan` line through the surviving partner's `EndOfPlan` line, matching the visible lifecycle boundaries without changing model semantics
- Survivor Social Security now supports widow/er-style step-up before the survivor's own claim year by using the deceased partner's configured SS benefit once the survivor reaches optional `survivor_ss_start_age` (default 60)
- Survivor spending can now be configured as `survivor_percent_of_retirement`, with runtime survivor-dollar spending derived from `retirement_annual` and legacy `survivor_annual` retained as a compatibility fallback
- Pre-retirement take-home income can now grow annually from inflation plus person-level `annual_take_home_real_raise`, and 401(k) contributions can now grow from that same income path plus person-level `annual_401k_contribution_extra_increase`
- Person-level 401(k) totals can now optionally split between `trad_ira` and `roth` via `annual_401k_contribution_split`, so bundled employer plans do not need to force the whole amount into one bucket
- `[accounts]` entries can now carry inline retirement owner metadata (`{ category = "...", owner = "person1|person2" }`), and live/offline account reclassification uses that to seed owner-level `trad_ira` / `roth` balances before fallback share logic
- `[accounts]` retirement entries can now also define `opening_balance_split` so a bundled account (for example one 401k containing both traditional and Roth dollars) seeds both buckets correctly before the first projection year
- Household person schema is now generic and canonicalized as `[person1]` / `[person2]` with event references `person = "person1" | "person2"`; runtime `matthew`/`weny` compatibility paths were removed in favor of a full staged refactor
- Retirement buckets now retain owner-level breakdown columns (`trad_ira_person1/person2`, `roth_person1/person2`) through the projection pipeline; Accounts and Portfolio views expose the split, and Cash Flow shows owner-level retirement contributions/withdrawals where present
- Scenario Parameters now includes a compact `Retirement ownership snapshots` card (first retirement year + end year) and keeps it visible under non-default `Show only differences` filtering
- Accounts, Cash Flow, and Portfolio owner-split labels now use configured person display names (`person1.name` / `person2.name`) instead of hardcoded `Person 1` / `Person 2`
- Person-level `annual_take_home_is_net_of_retirement_contributions` is now supported: when true, retirement contributions are treated as payroll-prefunded (still routed into IRA/Roth buckets) and are not subtracted again from implied pre-retirement spending cash
- `Expense` events now support optional `expense_kind = "mandatory" | "discretionary"`; discretionary expenses use 🏖️, mandatory expenses keep 💸, and retirement events now use 🎉
- `Expense` events can now also opt into `funding = "cash_reserve_first"` so named emergency/sinking-fund expenses may tap reserve cash before Roth/traditional withdrawals, without changing the household's normal phase withdrawal order
- Cash Flow tab now separates mandatory event expenses from discretionary event expenses while preserving total-expense math
- Gantt tab: enabled-event timeline derived from `config.toml`, with milestone vs span semantics by event type
- Recurring events now expand at runtime for both the model and Gantt via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Recurring event definitions can now set `chart_first_occurrence_only = true` so the event still affects the model and tables on every occurrence while only the first occurrence is annotated on the main projection chart
- Bounded `Income` events now annotate each active year by default (instead of start-year-only); setting `chart_first_occurrence_only = true` still suppresses labels for later recurring occurrences
- New `SpendingShift` event type (MVP: `mode="replace"`) can change retirement/survivor baseline spending from a start year (optionally through `end_year`) to model regime changes like moving countries
- Raw config editor is now available at `http://casalemuria.lan/finances/config/`
- Config editor projection links now append a one-time `refresh=<timestamp>` nonce on click so `Open projection` avoids stale cached pages
- Config editor `Open projection` now always uses the currently selected scenario slug from the dropdown at click time
- Editor supports validate, save, and save+offline-rerender actions with timestamped backups under per-scenario paths in `output/config-backups/<slug>/`, auto-pruned to the newest 10 per scenario
- Config editor now shows a render-in-progress overlay spinner during render actions (`Save + Re-render`, `Save + Render All`, `Clone`)
- The config editor render overlay is now action-aware and mode-aware: it reports scenario/mode counts and rotates staged progress copy during long multi-mode rerenders
- Async background render jobs: `Save + Re-render` and `Save + Render All` now POST to `/render-jobs`, receive a job id, and poll `GET /jobs/{id}` until the job completes, then redirect — confirmed working after restarting the stale container
- Progress modal hint text no longer flashes: the static "This page will refresh when the render completes." lives in the HTML; the elapsed counter now updates only an inner `<span id="render-elapsed">` so `setOverlayCopy` and the elapsed timer no longer compete over the same element
- The active default scenario now lives in `scenarios/default.toml`; root `config.toml` is a migration fallback only
- The config editor now supports scenario selection, clone/create inputs, and a `Save + Render All` control for batch output refresh
- The public `projection.html` entry point now serves as a scenario shell page backed by `output/scenarios/index.json`, with rendered scenario pages loaded inside an iframe
- The scenario shell is now two-dimensional: it selects both scenario and rendered mode, with URL state preserved as `?scenario=<slug>&mode=<mode>`
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
- Assumptions tab now also supports baseline-vs-default diff emphasis and its own `Show only differences` toggle
- Projection toolbar links are scenario-scoped: per-scenario projection pages now open editor as `/finances/config/?scenario=<slug>`
- Scenario shell `Edit Scenarios` link now follows the currently selected scenario
- Main projection chart event labels now wrap at 2 events per line, sit to the right of their event line, and use softer translucent label backgrounds
- Main projection chart now includes an in-chart event-label control strip (between graph and tax note) to: (a) show all labels, (b) hide non-key labels while keeping Retirement/Social Security/End-of-Plan, or (c) hide all labels
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

## Open Items for Next Session

### Model Accuracy Findings (2026-06-19, ordered by impact)

1. **Cash bucket growth** — `assumptions.cash_return` path now in place (fallback to inflation).
2. **Wage tax treatment** — `taxes.wage_tax_treatment = "net_cash"` is the active default.
3. **Retirement/survivor spending basis** — `[spending].spending_basis = "real"` inflates targets by CPI.
4. **Contribution routing + caps** — IRS 401(k) cap enforcement and employer match now implemented (Phase 4 done). IRS caps hardcoded at 2025 values — update `_IRS_401K_LIMIT_BASE` in `src/model.py` annually.
5. **Pre-retirement spending** — explicit precedence chain active.

### Next implementation slices

- **Phase 4 contribution follow-ons:**
  - Rate-based employer match (`annual_401k_employer_match_rate` as % of salary proxy)
  - IRS cap year-over-year indexing (currently fixed at 2025 limits: $23,500 base / $31,000 catch-up at 50+)
  - HSA modeling (optional later slice)
- **Phase 5 deeper tax (ongoing):**
  - Oregon state tax refinement/validation
  - Gross-income migration for wages is optional unless targeting a full household tax return
- Confirm survivor spending percentage (currently 70% of retirement spending)
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available
- Validate `[withdrawal_policy]` defaults against Person 1's intent

## Known Pitfalls

- Monarch auth expires periodically → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- Plotly `add_vrect` annotation_text collides with vline labels — use separate `add_annotation` with `yref="paper"` instead
- `output/` is gitignored — do not commit generated HTML or cache
- For routine NWN UI/layout tweaks, prefer targeted checks plus a real `python run.py --offline` render
- **nwn-config-editor container must be restarted after any code change to `admin_app.py`.** Command: `cd /opt/hal-pages && docker compose restart nwn-config-editor`.
- **Plotly y-axis title standoff** requires both `automargin: true` and `margin.l >= 80` for `$X.XXM`-format labels. `standoff` alone clips when margin is too narrow.
- **IRS 401(k) cap constants hardcoded at 2025 values** — update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` when IRS adjusts annually.
- **Employer match is always prefunded** — never reduces take-home cash. Routes into same `annual_401k_contribution_split` as employee. Do not double-count as income.
