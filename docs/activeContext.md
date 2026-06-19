# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-19 → 2026-06-19
**Current Status:** V1 is stable, and the next planned architecture shift is a move from one root config to a scenario-based model. The immediate design direction is shared tax-table extraction plus one-scenario-per-file with editor-driven rendering and a manifest-backed shell projections page.

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (cached), fast re-render
- Chart: http://casalemuria.lan/finances/projection.html
- Analysis sidecars now emit on each run under `output/`: `projection_yearly.csv`, `event_flows.csv`, `scenario_manifest.json`, and `accounts_snapshot.json`
- Accounts tab: trad IRA / Roth / taxable / cash / home equity / total net worth (yearly columns)
- Cash Flow tab: income / portfolio funding withdrawals / living expenses / event outflows / net (yearly columns)
- Portfolio tab: dedicated projected investment portfolio chart for taxable / traditional IRA / 401k / Roth, separate from cash, home equity, and the main net worth view
- First-pass tax modeling is now active: job income remains net cash; Social Security and positive income events are taxed via the 2025 federal ordinary-income bracket schedule plus standard deduction, with effective-rate fallback retained only for compatibility
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
- Social Security event timing and monthly benefit are now synced at runtime from each person's `ss_start_age` + `ss_monthly_benefit`; `ss_start_year` has been removed from the person-level config surface
- `Expense` events now support optional `expense_kind = "mandatory" | "discretionary"`; discretionary expenses use 🏖️, mandatory expenses keep 💸, and retirement events now use 🎉
- Cash Flow tab now separates mandatory event expenses from discretionary event expenses while preserving total-expense math
- Gantt tab: enabled-event timeline derived from `config.toml`, with milestone vs span semantics by event type
- Recurring events now expand at runtime for both the model and Gantt via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Recurring event definitions can now set `chart_first_occurrence_only = true` so the event still affects the model and tables on every occurrence while only the first occurrence is annotated on the main projection chart
- Raw config editor is now available at `http://casalemuria.lan/finances/config/`
- Editor supports validate, save, and save+offline-rerender actions with timestamped backups under per-scenario paths in `output/config-backups/<slug>/`
- The active default scenario now lives in `scenarios/default.toml`; root `config.toml` is a migration fallback only
- Projection page now includes a bottom-fixed `Edit Config` shortcut
- The editor backend now runs as a small FastAPI app, proxied behind the static nginx container
- Gantt includes liability payoff milestones derived from the projection output and uses a centered legend
- Gantt row labels now include event/liability icons, use larger tick-label text, and the Gantt includes a survivor-period band aligned to the projection output
- Assumptions tab now summarizes the current config inputs for people, market assumptions, spending, and withdrawal-policy cash targets
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

- Execute the next scenario-transition slice in [scenario-transition-plan.md](D:/Dev/Net-Worth-Navigator/docs/scenario-transition-plan.md)
  - add scenario clone/create flows on top of the new scenario registry and editor selector
  - build the shell projections page against `output/scenarios/index.json`
  - retire the root `config.toml` fallback once the scenario workflow is fully in place
- Design the scenario manifest and default-scenario source of truth before wiring the shell projections page
- Decide whether root `config.toml` gets a short compatibility window or a one-cut migration into `scenarios/default.toml`
- Confirm `survivor_annual = 66500` feels right (currently 70% of $95K)
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
