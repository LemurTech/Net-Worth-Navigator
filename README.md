# Net Worth Navigator

A local net worth projection and financial event modeling system originally built for the Household household, but general enough to adapt to other households with similar planning needs.

## What It Does

Net Worth Navigator projects household net worth forward over time, anchored to live account balances from Monarch Money. It models:

- Year-by-year compound growth across account types (taxable, traditional IRA/401k, Roth, cash)
- Household income and planned retirement dates
- Discrete financial events (expenses, income changes, home purchase, career changes, etc.)
- Social Security income at planned start ages
- Configurable scenarios — toggle events on/off, adjust assumptions

## Who It Is For

Net Worth Navigator is a good fit for households that:

- want a strategic, year-by-year planning model rather than a budgeting app
- are comfortable editing TOML configuration files directly
- want to test scenario changes such as retirement timing, spending changes, home sale/purchase plans, recurring expenses, or early-death cases
- can work with a simplified but improving tax model
- are comfortable making a few explicit modeling assumptions where the real world is messier than the current engine

In general, it is best for households asking questions like:

- "What happens if one of us retires earlier?"
- "How long does the portfolio last under this spending level?"
- "What if we sell the house, move, or downsize later?"
- "What happens if Social Security starts at a different age?"
- "How different is the outcome if we change contributions, spending, or withdrawal order?"

## Who It Is Not For

Net Worth Navigator is not yet a full-fidelity financial planning system. It is a poor fit if you need any of the following to be modeled precisely today:

- detailed tax-return accuracy, including full wage withholding, credits, deductions, Medicare IRMAA, NIIT, AMT, or state-specific edge cases beyond the current simplified layers
- retirement withdrawal optimization or tax-minimizing decumulation strategy generation
- precise Social Security claiming analysis across all spousal, survivor, divorce, disability, child, or family-benefit rules
- estate planning, trust planning, inheritance flows, probate timing, step-up basis treatment, or beneficiary-by-beneficiary account transfer rules
- required support for more than two household members in the main planning model
- monthly cash flow, paycheck timing, contribution timing within the year, or short-term liquidity sequencing
- highly detailed liability modeling beyond the current amortized loan / mortgage approach
- automatic employer-plan rules such as contribution limits, catch-up contributions, match formulas, vesting schedules, or plan loan behavior
- Monte Carlo simulation, historical backtesting, or probability-of-success analysis
- comprehensive modeling of healthcare, long-term care, insurance claims, or medical underwriting scenarios
- point-and-click consumer onboarding instead of direct config editing

## Current Modeling Checklist

If any of these are essential for a decision, the app currently needs either manual approximation in TOML or future code work:

- events do not automatically cancel just because a person dies unless the model explicitly supports that behavior or you edit the scenario accordingly
- account ownership transfer at death is currently handled by planning assumption, not by a full estate-transfer engine
- survivor Social Security is simplified and intentionally rule-based, not a full SSA calculator
- death is modeled at annual resolution, not as an exact date within the year
- household wages are often modeled as net cash rather than as a full gross-pay tax pipeline
- taxable brokerage withdrawals use simplified taxable-fraction assumptions rather than lot-level cost basis
- spending is modeled annually, not category-by-category with real transaction history
- the engine is scenario-driven, not recommendation-driven: it tells you what your assumptions imply, not what you should choose

## What It Can Reasonably Approximate Today

Even with those limitations, the app is already useful for many real planning questions when you are comfortable using explicit assumptions. It can reasonably support:

- accumulation-to-retirement transition planning
- survivor-phase planning at a household level
- comparing multiple retirement ages or Social Security start ages
- testing recurring expense burdens and one-time shocks
- home sale / relocation / downsizing scenarios
- comparing cash-reserve and withdrawal-order policies
- rough decumulation stress testing before using a more specialized withdrawal optimizer

## Quick Start

```bash
# Install dependencies into the local venv
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Edit assumptions/scenario inputs
nano scenarios/default.toml

# Run projection (live Monarch)
.venv/bin/python run.py

# Fast offline rerender (uses cache)
.venv/bin/python run.py --offline

# View output
open /srv/web-projects/finances/projection.html
# or visit http://casalemuria.lan/finances/ on the LAN
```

## Project Structure

```
Net-Worth-Navigator/
├── config.toml          ← Legacy compatibility fallback during migration
├── config/
│   └── tax_tables/      ← Shared tax reference files
├── scenarios/
│   └── default.toml     ← Active default scenario
├── run.py               ← Entry point
├── src/
│   ├── model.py         ← Year-by-year simulation engine
│   ├── monarch_bridge.py ← Live account balances from Monarch MCP
│   └── charts.py        ← Plotly HTML chart generation
├── output/              ← Generated HTML (gitignored)
└── docs/                ← Memory Bank — project reference documentation
```

## Configuration

Scenario-specific parameters live in `scenarios/*.toml`, starting with
`scenarios/default.toml`. Shared tax reference data loads from
`config/tax_tables/` via `[taxes].table_set`.

### Person schema (current)

Household members are modeled with generic keys:

- `[person1]` / `[person2]` — personal parameters, income, retirement year
- `[assumptions]` — growth rates, inflation, allocation
- `[[events]]` — financial events with `enabled = true/false` toggle

Event person references should use `person = "person1"` or `person = "person2"`.

> Note: this is now the canonical schema for this codebase; the runtime no longer
> carries `matthew`/`weny` compatibility paths.

## Web Output

Charts are served statically via the `hal-pages` nginx container at:
`http://casalemuria.lan/finances/`

Output is deployed by running `python run.py` — it writes to `/srv/web-projects/finances/`.

## Memory Bank

See `docs/` for full project documentation maintained across sessions.
