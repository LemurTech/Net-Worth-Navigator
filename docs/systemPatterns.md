# System Patterns — Net Worth Navigator

**Last Review:** 2026-06-16

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

- **Config is the single source of truth for assumptions.** No rates, ages, or amounts are hardcoded in source files. Everything Person 1 might tune flows through `config.toml`.
- **Events are typed.** Each `[[events]]` entry has a `type` field that determines how it impacts the model. Event types have defined property schemas.
- **Events are togglable.** Every event has `enabled = true/false`. Disabling never requires deleting the entry.
- **Monarch bridge is the live anchor.** Year 0 balances come from Monarch. All prior-year assumptions are overridden by live data on each run.
- **Output is always regenerated, never cached.** `python run.py` always produces a fresh chart.

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
| `NewJob` | Permanent start | `person`, `year`, `annual_income` — replaces income |
| `CareerBreak` | Bounded | `person`, `start_year`, `end_year` — zeroes earned income |
| `Education` | Bounded | `person`, `start_year`, `end_year`, `annual_cost` |
| `Marriage` | Singular | `year` — currently informational; future: tax filing status change |

### Model Impact Rules

- `Retire`: sets `person.income = 0` from `year` onward
- `SocialSecurity`: adds `monthly_benefit * 12` to income from `year` onward
- `Expense`: subtracts `amount` from liquid assets in `year`
- `Income`: adds `amount` per year within `[year, end_year]` (or just `year` if no `end_year`)
- `BuyHome`: subtracts `down_payment` in `year`, adds mortgage payment as annual expense, increases net worth via home equity (simplified: home value grows at inflation)
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
- **Simplified tax in V1:** Full tax modeling is a scope trap. V1 uses flat effective rates. Adopted 2026-06-16.
- **No OWL in V1:** OWL is a downstream decumulation tool. NWN must establish the strategic picture first. Adopted 2026-06-16.

## Promoted Learnings

- OWL is a decumulation optimizer (withdrawal phase only). NWN is the lifecycle trajectory model. They are complementary, not competing.
- Monarch does not provide growth rates, SS estimates, or planned events — those are always manual in config.
