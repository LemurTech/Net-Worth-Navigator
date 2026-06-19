# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.

## [Unreleased]

### Added

- Shared config loader in `src/config_loader.py` for merged runtime config resolution across model, bridge, and editor
- Shared tax reference file at `config/tax_tables/2025_us_federal_oregon.toml`
- Regression coverage for merged tax-table loading in `tests/test_config_loader.py`
- Scenario discovery/registry helpers in `src/scenarios.py`, including a generated `output/scenarios/index.json` manifest for the future shell page
- Per-scenario output layout now begins under `output/scenarios/<slug>/`, with the legacy top-level `output/projection.html` retained as a compatibility copy
- Config-editor backups are now written per scenario under `output/config-backups/<slug>/`
- Scenario output now stores analysis sidecars under `output/scenarios/<slug>/sidecars/`
- Config-editor backups now auto-prune to the newest 10 files per scenario
- Local scenario/config Git ignore rules now exclude `config.toml` and `scenarios/*.toml`, while `scenarios/.gitkeep` preserves the directory
- Real scenario file introduced at `scenarios/default.toml`, and the editor now supports selecting the active scenario from the discovered scenario list
- The config editor now supports cloning the current scenario into a new `scenarios/<slug>.toml` file and can batch re-render all discovered scenarios
- Public `projection.html` now acts as a scenario shell page that reads `output/scenarios/index.json` and switches between pre-rendered scenario pages without triggering a new render
- `SellHome` event type for converting a named real-estate account into cash proceeds, with default/override sale-fee rates and optional mortgage payoff linkage
- `SellHome` can now optionally reinvest some or all positive net proceeds into the taxable brokerage bucket via `reinvest_to = "taxable"` and optional `reinvest_fraction`
- Analysis sidecar bundle now emits on each run: `projection_yearly.csv`, `event_flows.csv`, `scenario_manifest.json`, and `accounts_snapshot.json`
- Real-estate appreciation is now separately configurable from CPI via `[assumptions].real_estate_appreciation`
- Social Security timing and monthly benefit are now synced from each person's `ss_start_age`, with runtime benefit selection coming from the matching `social_security_benefits` age bracket and legacy `ss_monthly_benefit` retained as a fallback; `ss_start_year` has been removed from the person-level config surface
- Survivor spending can now be configured as `survivor_percent_of_retirement`, with runtime survivor-dollar spending derived from `retirement_annual` and legacy `survivor_annual` retained as a fallback
- Cash Flow now exposes a dedicated Portfolio Funding / Withdrawals section with cash reserve drawdown, taxable withdrawals, traditional IRA / 401k withdrawals, Roth withdrawals, and a total portfolio-funding row
- Regression coverage for `SellHome` equity-to-cash behavior under `tests/test_withdrawal_policy.py`
- Main-chart x-axis can now show ages below the year ticks using household DOBs from config
- Small-screen responsive layout now suppresses the parenthetical age labels on the main chart x-axis so the year ticks remain legible on narrow viewports
- Regression coverage for age tick-label generation under `tests/test_recurring_events.py`
- Phase-specific withdrawal policy controls via `[withdrawal_policy]` in `config.toml`
- Cash reserve targets for accumulation, retirement, and survivor periods
- Configurable phase-specific withdrawal order using `cash_above_target` / `cash_below_target` steps
- Regression coverage for reserve-target preservation, phase-specific withdrawal order, and cash-target refill behavior under `tests/test_withdrawal_policy.py`
- Recurring events via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Runtime event expansion shared by the projection model and Gantt timeline
- Regression coverage for recurring event expansion and yearly application under `tests/test_recurring_events.py`
- `chart_first_occurrence_only = true` event control for decluttering repeated-event annotations on the main projection chart without changing model or table behavior
- `Expense` events now support `expense_kind = "mandatory" | "discretionary"`, with 🏖️ for discretionary, 💸 for mandatory, and 🎉 for retirement
- Cash Flow now splits mandatory event expenses from discretionary event expenses
- KPI summary strip above the chart showing Net Worth (EOY), Net Worth at Retirement, Retirement Age, and Net Worth at End
- Raw TOML config editor page at `/finances/config/`
- Validate, Save, and Save + Re-render actions for `config.toml`
- Automatic timestamped config backups under `output/config-backups/` before each save
- Small FastAPI admin backend and template for config editing
- Projection page toolbar shortcut: `Edit Config`
- Dockerized config-editor service for nginx proxying within the local Compose stack
- Gantt tab added to the projection page
- Assumptions tab added after Gantt, summarizing current person assumptions, market assumptions, spending, and withdrawal-policy cash targets from `config.toml`
- Gantt supports milestone vs span semantics by event type
- Gantt includes liability payoff milestones derived from projection output
- Gantt row labels include event/liability icons
- Gantt includes survivor-period shading aligned to projection output
- Gantt row labels increased in size after the density pass while preserving the compressed layout
- Main chart title suffix is configurable via `[display].projection_title` in `config.toml`
- First-pass tax modeling now applies the 2025 federal ordinary-income bracket schedule plus standard deduction to taxable Social Security, positive income events, and taxable withdrawals while preserving current job income as net cash
- Projection page now includes an explicit tax-modeling note clarifying that employment income is still net cash and the displayed taxes cover modeled taxable retirement/event inflows rather than a full household tax return
- Cash Flow now labels the tax row generically as modeled tax on retirement/event inflows so it remains correct once state tax is included
- Gross-income wage migration is no longer treated as a required next step; it is optional future work only if NWN ever moves from Monarch-style net-income cash-flow modeling to a true full household tax-return model
- Cash Flow tab now exposes positive income events in Income and the modeled-tax row in Expenses
- Event-level taxability is configurable in `config.toml` via optional `taxable` and `taxable_fraction` fields on `Income` and `SocialSecurity` events
- Ordinary-income tax brackets and standard deductions are now configurable in `config.toml [taxes]`
- Simplified Social Security provisional-income thresholds are now configurable in `config.toml [taxes.social_security]`
- Oregon state tax treatment is now configurable in `config.toml [taxes.state]`
- Regression coverage for progressive tax calculation, bracketed Social Security tax, and bracketed trad-IRA-withdrawal tax now lives in `tests/test_tax_model.py`
- Oregon state tax regression coverage (tax table under $50k and chart formulas above $50k) now lives in `tests/test_tax_model.py`
- Withdrawal-source sequencing is now active: deficits are covered from cash → taxable → trad IRA → Roth, and taxable/trad withdrawals feed the bracket-based tax model

### Changed

- `config.toml [taxes]` now points to shared tax reference data via `table_set = "2025_us_federal_oregon"` instead of inlining the large bracket/deduction tables
- The current root `config.toml` is now treated as the legacy default scenario until real `scenarios/*.toml` files take over
- The default runtime/editor scenario now comes from `scenarios/default.toml`; root `config.toml` remains only as a fallback during migration
- Negative-only liquid series now remain visible on the main chart instead of being suppressed when the series sum is below zero
- Offline/full projection runs now pass named real-estate accounts into the model so `SellHome` can target a specific property
- Projection config schema and sample config now include `real_estate_sale_fee_rate` plus `SellHome` event examples
- Projection page moved to a cohesive dark theme across chrome, tables, and both Plotly charts
- Main chart x-axis uses 2-year ticks with 6px tick-label standoff on both axes
- Table horizontal navigation now supports grab-to-pan and moderated wheel scrolling
- Gantt now resizes correctly when shown from a hidden tab
- Gantt density was tuned repeatedly to reduce vertical whitespace while preserving readable event bars
- Surplus cash flow now refills the active phase cash target before the remainder is invested into non-cash buckets

### Fixed

- Frozen first-column table labels and section bands now work reliably via JS `translateX(scrollLeft)`
- Gantt no longer renders condensed from hidden-tab Plotly sizing

---

## [2026-06-17] — V1 Feature Complete

### Added

- Liability amortization: mortgage (3.5%, $2,675/mo total) and CR-V loan (6%, $298/mo)
  with live Monarch balance anchors and auto payoff detection
  - CR-V payoff: 2028 (frees $3,576/yr)
  - Mortgage payoff: 2030 (frees $35,682/yr — 5 yrs before Person 1 retires)
- End of Plan events: Person 1 2054, Person 2 2063
- SS survivor benefit: on Person 1's death, Person 2 steps up to $2,691/mo (his higher check)
- Survivor period: spending switches to survivor_annual ($66,500 = ~70% of $95K)
- Survivor period shading on chart (gray vrect, paper-space label)
- Emoji icons for all event types: ⚰️🏖️🏛️💸💰🏠💼⏸️🎓💍🚗
- Annotation overlap fix: EndOfPlan uses bottom-right; alternating positions for others;
  survivor label moved to paper-space annotation
- Chart subtitle: "Values shown are end-of-year estimates, anchored to live Monarch balances"
- All 46 Monarch accounts classified in config.toml [accounts]
- Account disable list: vehicles and personal operating accounts excluded
- Home equity as separate non-liquid band (brown dotted), grows at inflation

### Changed

- simulation end_year extended from 2054 to 2063 (Person 2 life expectancy)
- monarch_bridge.py: calls MCP server venv via subprocess (version-safe)
- model.py: home value tracked separately from mortgage balance

### Decisions

- **Emoji in annotations via Unicode** — Plotly renders Unicode emoji natively in annotation text. No special config needed. Adopted 2026-06-17.
- **Survivor period label in paper-space** — avoids collision with data-space vline annotations at the same x-coordinate. Adopted 2026-06-17.
- **survivor_annual = 66500** — ~70% of $95K couple target. Standard planning assumption. Adjustable in config.toml. Adopted 2026-06-17.

---



### Added

- Repository created at `LemurTech/Net-Worth-Navigator` on GitHub
- Project scaffolded on Hermes host at `/home/lemurtech/Net-Worth-Navigator`
- Memory Bank initialized: all six core docs/ files created
- `.gitignore`, `README.md` created
- Directory structure: `src/`, `output/`, `docs/`

### Decisions

- **TOML config format** — human-readable, commentable, stdlib Python 3.11+. Adopted.
- **Static Plotly HTML output** — self-contained, no server required locally. LAN access via hal-pages nginx. Adopted.
- **Simplified tax modeling in V1** — full bracket modeling deferred to V2. Adopted.
- **Event system with typed events and enable/disable flag** — every event has `type`, `enabled`, and type-specific properties. Adopted.
- **OWL deferred** — Net Worth Navigator establishes the strategic picture first; OWL is a downstream decumulation tool for the withdrawal phase. Adopted.
- **Household members modeled independently** — Person 1 (retire 2035) and Person 2 (retire 2037) have independent income, retirement year, SS start age, and life expectancy parameters. Adopted.
