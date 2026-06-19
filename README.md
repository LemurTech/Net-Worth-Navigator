# Net Worth Navigator

A local net worth projection and financial event modeling system for the Household household.

## What It Does

Net Worth Navigator projects household net worth forward over time, anchored to live account balances from Monarch Money. It models:

- Year-by-year compound growth across account types (taxable, traditional IRA/401k, Roth, cash)
- Household income and planned retirement dates
- Discrete financial events (expenses, income changes, home purchase, career changes, etc.)
- Social Security income at planned start ages
- Configurable scenarios — toggle events on/off, adjust assumptions

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Edit assumptions
nano config.toml

# Run projection
python run.py

# View output
open output/projection.html
# or visit http://casalemuria.lan/finances/ on the LAN
```

## Project Structure

```
Net-Worth-Navigator/
├── config.toml          ← Main household/scenario config
├── config/
│   └── tax_tables/      ← Shared tax reference files
├── run.py               ← Entry point
├── src/
│   ├── model.py         ← Year-by-year simulation engine
│   ├── monarch_bridge.py ← Live account balances from Monarch MCP
│   └── charts.py        ← Plotly HTML chart generation
├── output/              ← Generated HTML (gitignored)
└── docs/                ← Memory Bank — project reference documentation
```

## Configuration

Scenario-specific parameters live in `config.toml`. Shared tax reference data now
loads from `config/tax_tables/` via `[taxes].table_set`. Edit the main config
directly before re-running:

- `[matthew]` / `[weny]` — personal parameters, income, retirement year
- `[assumptions]` — growth rates, inflation, allocation
- `[[events]]` — financial events with `enabled = true/false` toggle

## Web Output

Charts are served statically via the `hal-pages` nginx container at:
`http://casalemuria.lan/finances/`

Output is deployed by running `python run.py` — it writes to `/srv/web-projects/finances/`.

## Memory Bank

See `docs/` for full project documentation maintained across sessions.
