# System Patterns — Net Worth Navigator

**Last Review:** 2026-06-19

## Architectural Overview

```
Monarch MCP (live balances)
        ↓
monarch_bridge.py
  → classifies accounts: taxable / trad_ira / roth / cash
  → returns dict of {account_type: balance}
        ↓
model.py (simulation engine)
  → reads config.toml via tomllib
  → anchors year-0 balances from monarch_bridge
  → iterates year by year from simulation_start to max(life_expectancy)
  → applies: income, contributions, growth, events, retirement transitions, SS income
  → returns: DataFrame of {year: net_worth, account_balances, events_active}
        ↓
charts.py
  → receives DataFrame
  → produces Plotly figure with net worth line + event annotations
  → writes self-contained output/projection.html
        ↓
run.py
  → orchestrates the above
  → copies output to /srv/web-projects/finances/
  → sets correct file permissions
```

## Patterns & Conventions

- **Config is the single source of truth for assumptions.** No rates, ages, or amounts are hardcoded in source files. Scenario-specific controls live in `config.toml`, and shared tax reference data now loads from `config/tax_tables/` through a shared config loader.
- **Events are typed.** Each `[[events]]` entry has a `type` field that determines how it impacts the model. Event types have defined property schemas.
- **Events are togglable.** Every event has `enabled = true/false`. Disabling never requires deleting the entry.
- **Monarch bridge is the live anchor.** Year 0 balances come from Monarch. All prior-year assumptions are overridden by live data on each run.
- **Withdrawal behavior is phase-aware.** The model uses `[withdrawal_policy]` to select cash reserve targets and withdrawal order separately for accumulation, retirement, and survivor phases.
- **Tax behavior is phase-aware too.** The model can now choose filing status by lifecycle phase and apply bracket-based federal ordinary-income tax from `[taxes]`, with effective-rate fallback retained for compatibility.
- **State tax treatment is Oregon-specific for now.** The model uses the official 2025 OR-40 tax table for Oregon taxable income under $50,000 and the official rate-chart formulas above that.
- **Wage tax treatment is explicit and configurable.** `taxes.wage_tax_treatment` controls whether `annual_take_home` stays cashflow-only (`net_cash`) or enters ordinary-income taxation (`taxable_wages`). Default scenario currently uses `net_cash` to match Monarch semantics.
- **Pre-retirement income growth is modeled as an approximation on wage inputs.** `annual_take_home` can grow each year from inflation plus `annual_take_home_real_raise`, and 401(k) contributions can grow from that same path plus `annual_401k_contribution_extra_increase`.
- **Pre-retirement spending has explicit precedence controls.** The model resolves spending as: `pre_retirement_spending` → `annual_savings_override` → implied `income - contributions`, with inflation indexing when `spending_basis = "real"`.
- **Retirement contributions route to explicit buckets before surplus allocation.** 401(k)/IRA contributions are deposited into `trad_ira`/`roth` (default routing with optional per-person overrides) before generic non-cash surplus distribution.
- **Gross-income wage migration is optional.** Unless NWN is explicitly re-scoped into a true household tax-return model, Monarch-style net-income wage inputs are acceptable and do not require forced gross-up migration.
- **Cash reserves are protected in two stages.** `cash_above_target` spends only dollars above the reserve; `cash_below_target` taps the reserve itself only as a last resort.
- **Surplus refills cash before investing.** Positive net flow first restores the active cash target, then allocates the remainder across positive non-cash investable buckets.
- **Output is always regenerated, never cached.** `python run.py` always produces a fresh chart.
- **Recurring chart annotations can be decoupled from model recurrence.** `chart_first_occurrence_only = true` keeps repeated events active in the model and tables while suppressing later main-chart annotations for readability.
- **Portfolio funding is now explicit in the data model.** Deficit coverage records bucket-level withdrawals (`cash`, `taxable`, `trad_ira`, `roth`) so the Cash Flow tab can show how retirement spending is funded.
- **Main-chart age labels are responsive UI, not model truth.** The parenthetical ages below year ticks are shown on larger screens but suppressed on narrow viewports so the x-axis remains legible.
- **Social Security person settings are the source of truth.** Runtime config now derives each `SocialSecurity` event year from `ss_start_age` and its benefit from the matching `social_security_benefits` age bracket, with legacy `ss_monthly_benefit` retained as a fallback; `ss_start_year` is not part of the intended person-level control surface.

## Event System

Events are declared in `config.toml` as `[[events]]` array entries. Each event has:

```toml
[[events]]
enabled = true
type = "Expense"           # determines property schema and model behavior
label = "Surgery drawdown"
year = 2026
amount = -6000             # negative = cash outflow
```

### Event Types and Properties

| Type | Duration | Key Properties |
|---|---|---|
| `Retire` | Permanent start | `person`, `year` — stops earned income for that person |
| `SocialSecurity` | Permanent start | `person`, `year`, `monthly_benefit` — adds SS income |
| `Expense` | Singular | `year`, `amount` — one-time cash outflow |
| `Income` | Singular or bounded | `year`, `amount`, `end_year` (optional) |
| `BuyHome` | Singular (down payment) + ongoing (mortgage) | `year`, `down_payment`, `price`, `mortgage_rate`, `term_years` |
| `SellHome` | Singular | `year`, `property`, optional `liability_names`, optional `sale_fee_rate`, optional `reinvest_to`, optional `reinvest_fraction` |
| `NewJob` | Permanent start | `person`, `year`, `annual_income` — replaces income |
| `CareerBreak` | Bounded | `person`, `start_year`, `end_year` — zeroes earned income |
| `Education` | Bounded | `person`, `start_year`, `end_year`, `annual_cost` |
| `Marriage` | Singular | `year` — currently informational; future: tax filing status change |

### Model Impact Rules

- `Retire`: sets `person.income = 0` from `year` onward
- `SocialSecurity`: adds `monthly_benefit * 12` to income from `year` onward
- `Expense`: subtracts `amount` from liquid assets in `year`
- `Income`: adds `amount` per year within `[year, end_year]` (or just `year` if no `end_year`)
- `BuyHome`: subtracts `down_payment` in `year`, adds mortgage payment as annual expense, increases net worth via home equity (property growth now follows `real_estate_appreciation`, with inflation as fallback)
- `SellHome`: converts the named property value into cash proceeds net of sale fees and linked mortgage payoff, then removes that property from future home-value growth
- `NewJob`: replaces `person.income` from `year` onward
- `CareerBreak`: zeroes `person.income` for `[start_year, end_year]`
- `Education`: subtracts `annual_cost` per year for `[start_year, end_year]`
- `Marriage`: no model impact in V1 (placeholder for future tax filing status)

## Critical Paths

- `run.py` → `monarch_bridge.py` → `model.py` → `charts.py` → write output → set permissions
- If Monarch auth is stale: `uv run python login_setup.py` in `/opt/monarch-mcp-server`

## Key Technical Decisions

- **TOML over JSON:** Readable, commentable, stdlib. Adopted 2026-06-16.
- **Static HTML over Streamlit:** No server overhead; simpler architecture. Streamlit is V2 option if live-reload is needed. Adopted 2026-06-16.
- **Simplified tax in V1:** Flat effective-rate tax was the original approximation. As of 2026-06-17, the project has started the deeper-tax-realism path with configurable federal ordinary-income brackets and standard deductions; Social Security taxability and state tax still need more work. Adopted/updated 2026-06-17.
- **Phase-specific withdrawal policy in V1.5:** Reserve targets and withdrawal order live in `[withdrawal_policy]` instead of remaining hardcoded in `model.py`. Adopted 2026-06-17.
- **No OWL in V1:** OWL is a downstream decumulation tool. NWN must establish the strategic picture first. Adopted 2026-06-16.

## Promoted Learnings

- OWL is a decumulation optimizer (withdrawal phase only). NWN is the lifecycle trajectory model. They are complementary, not competing.
- Monarch does not provide growth rates, SS estimates, or planned events — those are always manual in config.
- **Phase-aware withdrawals need explicit config.** Once reserve targets mattered, hardcoded sequencing was too rigid; `[withdrawal_policy]` is now the durable control surface.
- **Cash target semantics are clearer than a generic reserve flag.** Distinguishing `cash_above_target` from `cash_below_target` lets the model preserve liquidity until it truly must break the reserve.
- **Emoji in Plotly annotations:** Unicode emoji render natively in annotation text in all modern browsers. No special config required. Put the emoji directly in the label string.
- **Survivor period vrect label:** do NOT use `annotation_text` on `add_vrect` — Plotly places it top-left in data space and it collides with vline annotations at the same x. Use a separate `add_annotation` with `yref="paper"` instead.
- **Annotation overlap:** alternate `annotation_position` ("top right" / "top left") by index for consecutive vlines. EndOfPlan events use "bottom right" to stay clear of the survivor label.
- **Gantt density tuning must move bar width and chart height deliberately.** Slimmer bars alone leave airy rows; reduce the height formula to compress row pitch, then re-check the served page with a real offline render.
