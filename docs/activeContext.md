# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-16 → 2026-06-17
**Current Status:** V1 complete and extended. Projection chart + tabbed Accounts/Cash Flow tables + Gantt timeline live. Raw TOML config editor is available on the web, recurring events are supported, and the latest UI pass added recurring-event chart decluttering plus a denser, more legible Gantt.

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (cached), fast re-render
- Chart: http://casalemuria.lan/finances/projection.html
- Accounts tab: trad IRA / Roth / taxable / cash / home equity / total net worth (yearly columns)
- Cash Flow tab: income / living expenses / event outflows / net (yearly columns)
- First-pass tax modeling is now active: job income remains net cash; Social Security and positive income events are taxed via effective pre/post-retirement rates
- Event-level taxability is now configurable in `config.toml` via optional `taxable` and `taxable_fraction` fields on `Income` and `SocialSecurity` events
- Withdrawal-source taxation and sequencing are now active: deficits withdraw from cash → taxable → trad IRA → Roth, with taxable/trad withdrawals feeding the simplified tax model
- Withdrawal policy is now configurable by lifecycle phase via `[withdrawal_policy]` in `config.toml`
- Phase-specific cash reserve targets are now supported for accumulation, retirement, and survivor periods
- Surplus cash flow now refills the active cash target first, then allocates the remainder into non-cash investable buckets
- Deficit coverage now honors configurable phase-specific withdrawal order using `cash_above_target` / `cash_below_target` semantics to preserve reserves when possible
- Cash Flow tab now shows positive income events in Income and an `Estimated taxes` expense row
- `Expense` events now support optional `expense_kind = "mandatory" | "discretionary"`; discretionary expenses use 🏖️, mandatory expenses keep 💸, and retirement events now use 🎉
- Cash Flow tab now separates mandatory event expenses from discretionary event expenses while preserving total-expense math
- Gantt tab: enabled-event timeline derived from `config.toml`, with milestone vs span semantics by event type
- Recurring events now expand at runtime for both the model and Gantt via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Recurring event definitions can now set `chart_first_occurrence_only = true` so the event still affects the model and tables on every occurrence while only the first occurrence is annotated on the main projection chart
- Raw config editor is now available at `http://casalemuria.lan/finances/config/`
- Editor supports validate, save, and save+offline-rerender actions with timestamped backups under `output/config-backups/`
- Projection page now includes a bottom-fixed `Edit Config` shortcut
- The editor backend now runs as a small FastAPI app, proxied behind the static nginx container
- Gantt includes liability payoff milestones derived from the projection output and uses a centered legend
- Gantt row labels now include event/liability icons, use larger tick-label text, and the Gantt includes a survivor-period band aligned to the projection output
- Gantt row pitch and bar geometry were tuned together for a denser layout: slimmer bars, materially less vertical whitespace, and a more compact overall chart height
- Both tables scroll horizontally, yearly tick columns
- First-column labels and section bands are frozen via JS `translateX(scrollLeft)` + `requestAnimationFrame`
- Table navigation now supports grab-and-drag panning and moderated wheel-to-horizontal scrolling
- Main chart now uses 2-year x-axis ticks with 6px tick-label standoff on both axes
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

- Confirm `survivor_annual = 66500` feels right (currently 70% of $95K)
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available
- Validate the new `[withdrawal_policy]` defaults against Person 1's intent
  - accumulation cash target = $64,000 (roughly current liquid reserve)
  - retirement cash target = $95,000 (roughly one year of planned retirement spending)
  - survivor cash target = $66,500 (roughly one year of planned survivor spending)
- Decide whether retirement / survivor withdrawal order should stay `cash_above_target → taxable → trad_ira → roth → cash_below_target` or be tuned further
- Current build target: deeper tax realism
  - bracket-based tax model
  - more nuanced Social Security taxation
  - state tax treatment
  - route taxable withdrawals and Social Security through the richer tax model without changing current net-income semantics for job income
- Decide whether taxable brokerage withdrawal taxability should stay at 50% or be customized further
- Decide whether V2 should stay with raw TOML editing only or add structured form sections for simple config fields
- Surgery event amount is $18,000 in config — Person 1 confirmed this is correct

## Known Pitfalls

- Monarch auth expires periodically → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- Plotly `add_vrect` annotation_text collides with vline labels — use separate `add_annotation` with `yref="paper"` instead
- `annotation_textangle=-90` + `annotation_position="top right"` is the correct vertical label approach
- `output/` is gitignored — do not commit generated HTML or cache
- For routine NWN UI/layout tweaks, prefer targeted checks plus a real `python run.py --offline` render; reserve the full test suite for broader model or semantic changes
