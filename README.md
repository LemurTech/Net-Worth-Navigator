# Net Worth Navigator

A local net worth projection and financial event modeling system originally built for a two-person household, but general enough to adapt to other households with similar planning needs. **Monarch Money is optional** — the app runs fully from manually entered balances.

## Quick Start

### 1. Install and Verify

```bash
# Clone the repository
git clone https://github.com/YourOrg/Net-Worth-Navigator.git
cd Net-Worth-Navigator

# Create virtual environment and install dependencies
# Linux/macOS:
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Windows:
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Verify installation
python scripts/verify_install.py
```

### 2. Try the Sample Scenario (Recommended First Step)

See the app in action with a working example before creating your own scenario:

```bash
# Linux/macOS:
.venv/bin/python run.py --scenario sample

# Windows:
.venv\Scripts\python.exe run.py --scenario sample

# Open the output
# Linux/macOS: open output/scenarios/sample/deterministic/projection.html
# Windows: start output\scenarios\sample\deterministic\projection.html
```

The sample scenario uses **fictional household data** (Alex & Sam) with synthetic balances. This shows you what the projection looks like before you enter your own data.

### 3. Create Your Own Scenario

Once you've seen the sample, create your household scenario:

```bash
# Linux/macOS:
cp scenarios/starter.toml scenarios/myhousehold.toml
nano scenarios/myhousehold.toml
# Fill in every field marked  ← YOUR VALUE
# Update [scenario].slug to "myhousehold"
.venv/bin/python run.py --scenario myhousehold

# Windows:
copy scenarios\starter.toml scenarios\myhousehold.toml
notepad scenarios\myhousehold.toml
# Fill in every field marked  ← YOUR VALUE
# Update [scenario].slug to "myhousehold"
.venv\Scripts\python.exe run.py --scenario myhousehold
```

**Or use the web UI:** Start the config editor and use the Setup Panel for a GUI-based experience:

```bash
# Linux/macOS:
.venv/bin/python admin_app.py
# Open http://localhost:8010/setup

# Windows:
.venv\Scripts\python.exe admin_app.py
# Open http://localhost:8010/setup
```

Click **"New from Template"** to create a scenario from the starter template, then use the **Synthetic Setup** tab to enter your balances.

---

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

## Advanced: Using Monarch Money (Live Balance Sync)

If you subscribe to Monarch Money and want automatic balance updates instead of manual entry, you can connect the Monarch MCP server.

### Prerequisites

1. Active Monarch Money subscription
2. [Monarch MCP Server](https://github.com/Agentic-Insights/monarch-mcp) installed on your system
3. Authenticated Monarch MCP session (run `uv run python login_setup.py` in the MCP directory)

### Linux / macOS

```bash
# 1. Set the Monarch MCP path (if not at default /opt/monarch-mcp-server)
export MONARCH_MCP_PATH=/path/to/your/monarch-mcp-server

# 2. Copy and edit a Monarch-mode scenario
cp scenarios/sample.toml scenarios/myhousehold.toml
nano scenarios/myhousehold.toml
# Keep [data_source].mode = "monarch"
# Update person details, assumptions, and events

# 3. Run with live Monarch data
.venv/bin/python run.py --scenario myhousehold

# 4. Or run offline (uses cached balances from last successful fetch)
.venv/bin/python run.py --scenario myhousehold --offline
```

### Windows

```powershell
# 1. Set the Monarch MCP path (persistent)
# System Properties → Environment Variables → New user variable:
#   Name: MONARCH_MCP_PATH
#   Value: C:\path\to\monarch-mcp-server

# 2. Copy and edit a Monarch-mode scenario
copy scenarios\sample.toml scenarios\myhousehold.toml
notepad scenarios\myhousehold.toml
# Keep [data_source].mode = "monarch"
# Update person details, assumptions, and events

# 3. Run with live Monarch data
.venv\Scripts\python.exe run.py --scenario myhousehold

# 4. Or run offline (uses cached balances)
.venv\Scripts\python.exe run.py --scenario myhousehold --offline
```

See `docs/plans/windows-compatibility.md` for detailed Windows setup instructions.

---

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
├── scripts/
│   └── verify_install.py ← Installation health check
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
> carries `person1`/`person2` compatibility paths.

## Web Output

Charts are served statically via the `hal-pages` nginx container at:
`http://casalemuria.lan/finances/`

Output is deployed by running `python run.py` — it writes to `/srv/web-projects/finances/`.

## Memory Bank

See `docs/` for full project documentation maintained across sessions.
