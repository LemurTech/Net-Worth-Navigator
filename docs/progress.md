# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.

## [Unreleased]

### Added

- Bundled illustrative historical return dataset at `config/return_sequences/us_balanced_returns.csv` plus usage guidance in `docs/historical-return-sequences.md`, making historical mode turnkey for repo-local scenarios
- Historical-sequence simulation mode in `src/model.py`, driven by rolling windows from `simulation.historical_returns_path` CSV data (`year`, `return`)
- Configurable stochastic success/failure settings via `[monte_carlo.success]`, including named `failure_mode`, spending-funded threshold, home-equity/debt allowances, grace-period months, and a basic custom-threshold comparator
- Additional stochastic summary and UI coverage: Scenario Parameters now includes `Stochastic success rules`, simulation summaries now report generic first-failure metrics, and historical runs reuse the same probability-band result surfaces
- Regression coverage for configurable failure modes and historical rolling windows in `tests/test_simulation_modes.py`
- Normalized projection-result contract in `src/model.py`: deterministic and stochastic runs now share a `ProjectionResult` boundary carrying the primary yearly path, simulation summary, and optional yearly percentile bands
- Seeded Monte Carlo MVP in `src/model.py` + `src/charts.py`: `[simulation]` now supports `mode`, `num_runs`, `seed`, and `portfolio_return_volatility`, with stochastic runs varying blended investable returns while preserving existing household/event semantics
- Monte Carlo presentation surfaces: KPI strip, total-net-worth probability-band chart, investable-portfolio probability-band chart, and a `Simulation results` card in Scenario Parameters
- Stochastic-ready sidecar bundle in `src/sidecars.py`: `simulation_summary.json` now ships for every run, and Monte Carlo runs additionally emit `projection_bands_yearly.csv` with yearly percentile bands
- Regression coverage for simulation modes and stochastic sidecars in `tests/test_simulation_modes.py`, `tests/test_sidecars.py`, and `tests/test_recurring_events.py`

- Comparative analysis doc at `docs/ignidash-comparative-analysis.md`, covering NWN vs. ignidash strengths, replacement-fit assessment, Monarch-bridge feasibility, partial scenario-port feasibility, and recommended cross-pollination targets
- High-level feature-port roadmap at `docs/ignidash-feature-port-plan.md`, defining a phased plan to bring ignidash-inspired capabilities into NWN while preserving TOML-first household planning and avoiding SaaS-style infrastructure creep

- Portfolio tab now includes a projected-balances table below the chart, using the shared datatable styling and owner-split retirement rows when present
- Scenario Parameters now includes a compact `Retirement ownership snapshots` card (first retirement year + end year; combined/traditional/Roth shares) sourced from projection owner-split columns
- Accounts, Cash Flow, and Portfolio owner-split labels now resolve from configured person display names (`person1.name` / `person2.name`) instead of hardcoded `Person 1` / `Person 2`
- Assumptions tab baseline-diff support in `src/tables.py` + `src/charts.py`: changed rows now use `param-diff`, includes changed-field count and `Show only differences` filtering parity with Scenario Parameters
- Scenario-aware projection/editor URL propagation updates in `admin_app.py`, `src/charts.py`, and `src/scenario_shell.py` so shell/editor/projection navigation preserves `?scenario=<slug>`
- Config editor render-progress overlay spinner (`templates/config_editor.html`) shown during render-triggering submit actions
- Main-chart event-label control strip (inside chart area, above tax note) with client-side toggles to show all labels or keep only key labels (Retirement, Social Security, End-of-Plan)
- Regression tests for new behavior in `tests/test_assumptions_summary.py`, `tests/test_scenario_shell.py`, `tests/test_editor_scenarios.py`, and `tests/test_recurring_events.py`

- Scenario Parameters tab in projection page (`src/charts.py` + `src/tables.py`) with detailed per-scenario controls: metadata, tax/RMD settings, withdrawal orders/surplus orders, per-person contribution semantics, and enabled-event metrics
- Baseline-diff emphasis in Scenario Parameters: rows that differ from default scenario are marked with `param-diff`, and the tab shows a total changed-field count
- Client-side `Show only differences` filter for Scenario Parameters, including automatic hiding of cards with no diff rows
- Synthetic scenario data-source mode in `run.py`: `[data_source].mode = "synthetic"` with `[synthetic_start]` seeds (portfolio/home/liabilities) bypasses live Monarch and cached balances
- Share-safe sample scenario at `scenarios/sample.toml` using synthetic start balances and realistic recurring/one-time events for demos
- Portfolio tab display cue when taxable/brokerage is zero across all years
- Expanded `[[events]]` documentation in `scenarios/default.toml`: required/optional fields by event type plus copy/paste templates for each supported event type

- Per-bucket cash/investment growth behavior in `model.py`: `cash_return` now applies to `cash`, while non-cash investable buckets keep blended stock/bond growth
- Spending-basis control in `model.py`/scenario config via `spending_basis = "real" | "nominal"`, with inflation indexing for retirement/survivor spending when real mode is selected
- Explicit pre-retirement spending precedence in `model.py`: `pre_retirement_spending` → `annual_savings_override` → implied `income - contributions`
- Explicit retirement contribution routing in `model.py`: contributions deposit to `trad_ira`/`roth` before generic surplus allocation, with optional per-person bucket overrides
- Optional `annual_401k_contribution_split` support in `model.py` and `scenarios/default.toml` so bundled employer retirement contributions can be routed proportionally between traditional and Roth buckets
- Account-level retirement owner attribution in `run.py`, `src/monarch_bridge.py`, and `src/model.py`: `[accounts]` entries can now be inline tables with `category` + `owner`, and live/offline raw-account reclassification seeds `trad_ira` / `roth` owner balances from exact accounts before fallback sharing logic
- Opening-balance split support for bundled retirement accounts in `src/monarch_bridge.py` + scenario config: `[accounts]` inline entries can define `opening_balance_split` so one live account can seed both `trad_ira` and `roth` before the first projection year
- Event-level reserve funding override in `src/model.py` + scenario TOMLs: `Expense` events may now set `funding = "cash_reserve_first"` so emergency/sinking-fund costs can draw from reserve cash before Roth/traditional buckets without weakening the default withdrawal policy
- Scenario sweep across `scenarios/*.toml`: legacy household account mappings were upgraded to owner-aware `opening_balance_split` / `owner` metadata where needed, reserve-first funding flags were added to surgery/vacation/travel/car/home-repair expenses, and all scenarios were rerendered offline with refreshed sidecars
- Early-death survivor modeling improvements in `model.py`: survivor phase now begins immediately after death (not only after both partners retire), and widow/er Social Security can step up from the deceased partner's configured benefit once the survivor reaches `survivor_ss_start_age` (default 60)
- `BuyHome` events now add/update tracked real-estate property state when `price` is provided, so future home purchases flow into `home_value` / `home_equity` and can later be referenced by `SellHome`
- Configurable wage tax treatment in `model.py` via `taxes.wage_tax_treatment = "net_cash" | "taxable_wages"`, including a tracked `taxable_wage_income` output column
- Scenario shell iframe height increased by 25% across desktop/mobile breakpoints in `src/scenario_shell.py`
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
- Retirement now has a single source of truth in person settings: runtime synthesizes Retire events from each person's `retirement_year`, while preserving legacy event metadata overrides (label/enabled) for compatibility
- Social Security now has a single source of truth in person settings: runtime synthesizes SocialSecurity events from each person's `ss_start_age` plus `social_security_benefits` (or legacy `ss_monthly_benefit` fallback), while preserving legacy event metadata overrides (label/enabled/taxability) for compatibility
- Survivor spending can now be configured as `survivor_percent_of_retirement`, with runtime survivor-dollar spending derived from `retirement_annual` and legacy `survivor_annual` retained as a fallback
- Pre-retirement net income can now grow annually from inflation plus person-level `annual_take_home_real_raise`, and 401(k) contributions can now grow from that same income path plus person-level `annual_401k_contribution_extra_increase`
- Cash Flow now exposes a dedicated Portfolio Funding / Withdrawals section with cash reserve drawdown, taxable withdrawals, traditional IRA / 401k withdrawals, Roth withdrawals, and a total portfolio-funding row
- Regression coverage for `SellHome` equity-to-cash behavior under `tests/test_withdrawal_policy.py`
- Main-chart x-axis can now show ages below the year ticks using household DOBs from config
- Small-screen responsive layout now suppresses the parenthetical age labels on the main chart x-axis so the year ticks remain legible on narrow viewports
- Regression coverage for age tick-label generation under `tests/test_recurring_events.py`
- Phase-specific withdrawal policy controls via `[withdrawal_policy]` in `config.toml`
- Cash reserve targets for accumulation, retirement, and survivor periods
- Configurable phase-specific withdrawal order using `cash_above_target` / `cash_below_target` steps
- Regression coverage for reserve-target preservation, phase-specific withdrawal order, and cash-target refill behavior under `tests/test_withdrawal_policy.py`
- Regression coverage for reserve-first expense funding under `tests/test_withdrawal_policy.py`
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

- Survivor-period shading on the main chart and Gantt now starts one visual year earlier than the modeled survivor phase for better readability at the death-to-survivor transition
- Main-chart event annotations now wrap at two events per line, use right-anchored top-down placement into the graph body, and use softer translucent backgrounds (`rgba(15,23,37,0.60)`) for improved readability with multiline labels
- Synthesized `Retirement (...)` and `SS Begins (...)` labels now use configured person-name initials instead of person-key initials, so sample scenarios render A/S (etc.) instead of M/W
- `config.toml [taxes]` now points to shared tax reference data via `table_set = "2025_us_federal_oregon"` instead of inlining the large bracket/deduction tables
- The current root `config.toml` is now treated as the legacy default scenario until real `scenarios/*.toml` files take over
- The default runtime/editor scenario now comes from `scenarios/default.toml`; root `config.toml` remains only as a fallback during migration
- Negative-only liquid series now remain visible on the main chart instead of being suppressed when the series sum is below zero
- Offline/full projection runs now pass named real-estate accounts into the model so `SellHome` can target a specific property
- `BuyHome` docs/examples now document optional `property` naming and the requirement to provide `price` if the purchase should create tracked equity
- Projection config schema and sample config now include `real_estate_sale_fee_rate` plus `SellHome` event examples
- Projection page moved to a cohesive dark theme across chrome, tables, and both Plotly charts
- Main chart x-axis uses 2-year ticks with 6px tick-label standoff on both axes
- Table horizontal navigation now supports grab-to-pan and moderated wheel scrolling
- Gantt now resizes correctly when shown from a hidden tab
- Gantt density was tuned repeatedly to reduce vertical whitespace while preserving readable event bars
- Surplus cash flow now refills the active phase cash target before the remainder is invested into non-cash buckets

### Fixed

- Scenario Parameters `Retirement ownership snapshots` rows now remain visible when non-default scenarios open with `Show only differences` enabled
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
- Emoji icons for all event types: 💀🏖️🏛️💸💰🏠💼⏸️🎓💍🚗
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
