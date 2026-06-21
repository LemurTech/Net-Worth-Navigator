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
