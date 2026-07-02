# Net Worth Navigator

A local net worth projection and financial event modeling system originally built for the Household household, but general enough to adapt to other households with similar planning needs. **Monarch Money is optional** — the app runs fully from manually entered balances.

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

## Getting Started Without Monarch

Monarch Money is **not required**. You can run a full projection using manually entered balances.

### Linux / macOS

```bash
# 1. Install dependencies
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 2. Copy the starter template and give it your own name
cp scenarios/starter.toml scenarios/myhousehold.toml

# 3. Edit your copy — fill in every  ← YOUR VALUE  field
nano scenarios/myhousehold.toml

# 4. Update [scenario].slug to match your filename (e.g. "myhousehold")

# 5. Run the projection
.venv/bin/python run.py --scenario myhousehold
```

### Windows

```powershell
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Copy the starter template and give it your own name
copy scenarios\starter.toml scenarios\myhousehold.toml

# 3. Edit your copy — fill in every  ← YOUR VALUE  field
notepad scenarios\myhousehold.toml

# 4. Update [scenario].slug to match your filename (e.g. "myhousehold")

# 5. Run the projection
.venv\Scripts\python.exe run.py --scenario myhousehold
```

The starter template has `[data_source].mode = "synthetic"`, which means the model reads your account balances from the `[synthetic_start]` section of the TOML — no Monarch account, no API key, no external service needed.

**Using the web UI instead of editing TOML directly:**
If you have the config editor running (see the deployment section below), open
`/finances/config/setup?scenario=myhousehold` and use the **Synthetic Setup** tab
to enter and update your balances through a form interface.

**Keeping balances current:**
With synthetic mode you update your balances manually — typically once a year or
before a major planning decision. Edit `[synthetic_start]` in your scenario TOML
(or use the Synthetic Setup tab) and re-run the projection.

**Connecting Monarch later (optional):**
If you later subscribe to Monarch Money and install the Monarch MCP server, you can
switch any scenario to live balances by changing `[data_source].mode` from
`"synthetic"` to `"monarch"` in the TOML. The `[accounts]` section maps your
Monarch account names to the model's buckets (taxable, trad_ira, roth, etc.).

## Quick Start (with Monarch)

### Linux / macOS

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

### Windows

```powershell
# Install dependencies into the local venv
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Edit assumptions/scenario inputs
notepad scenarios\default.toml

# Run projection (live Monarch)
.venv\Scripts\python.exe run.py

# Fast offline rerender (uses cache)
.venv\Scripts\python.exe run.py --offline

# View output in browser
start output\projection.html
```

**Note for Monarch users on Windows:** Set the `MONARCH_MCP_PATH` environment variable to point to your Monarch MCP server installation directory (the folder containing `.venv` and `src`), for example:

```powershell
$env:MONARCH_MCP_PATH = "C:\Users\YourName\monarch-mcp-server"
```

The default Linux path (`/opt/monarch-mcp-server`) won't work on Windows.

## Project Structure

```
Net-Worth-Navigator/
├── config.toml          ← Legacy compatibility fallback during migration
├── config/
│   └── tax_tables/      ← Shared tax reference files
├── scenarios/
│   ├── starter.toml     ← Blank-slate template for new users (no Monarch required)
│   ├── sample.toml      ← Synthetic demo scenario (Alex & Sam household)
│   └── default.toml     ← Active default scenario (gitignored for personal data)
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
