# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.

## [Unreleased]

### Added

- Recurring events via optional `repeat_every_years`, `repeat_until_year`, and `repeat_count` fields on events with `year` or `start_year`
- Runtime event expansion shared by the projection model and Gantt timeline
- Regression coverage for recurring event expansion and yearly application under `tests/test_recurring_events.py`
- Raw TOML config editor page at `/finances/config/`
- Validate, Save, and Save + Re-render actions for `config.toml`
- Automatic timestamped config backups under `output/config-backups/` before each save
- Small FastAPI admin backend and template for config editing
- Projection page toolbar shortcut: `Edit Config`
- Dockerized config-editor service for nginx proxying within the local Compose stack
- Gantt tab added to the projection page
- Gantt supports milestone vs span semantics by event type
- Gantt includes liability payoff milestones derived from projection output
- Gantt row labels include event/liability icons
- Gantt includes survivor-period shading aligned to projection output
- Main chart title suffix is configurable via `[display].projection_title` in `config.toml`
- First-pass tax modeling now applies effective tax rates to Social Security and positive income events while preserving current job income as net cash
- Cash Flow tab now exposes positive income events in Income and `Estimated taxes` in Expenses
- Event-level taxability is configurable in `config.toml` via optional `taxable` and `taxable_fraction` fields on `Income` and `SocialSecurity` events
- Withdrawal-source sequencing is now active: deficits are covered from cash → taxable → trad IRA → Roth, and taxable/trad withdrawals feed the simplified tax model

### Changed

- Projection page moved to a cohesive dark theme across chrome, tables, and both Plotly charts
- Main chart x-axis uses 2-year ticks with 6px tick-label standoff on both axes
- Table horizontal navigation now supports grab-to-pan and moderated wheel scrolling
- Gantt now resizes correctly when shown from a hidden tab

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
