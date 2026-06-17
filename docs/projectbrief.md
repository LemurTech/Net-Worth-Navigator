# Project Brief — Net Worth Navigator

**Owner:** Matt
**Last Review:** 2026-06-16

## Summary

Net Worth Navigator is a local Python-based net worth projection and financial event modeling tool for the Household household. It anchors to live Monarch Money account balances and projects household net worth forward across a configurable time horizon, modeling discrete life events, income changes, and retirement transitions.

It is the strategic financial visibility layer. OWL (optimal retirement withdrawal optimizer) is a potential downstream tool, not a competitor.

## Objectives

- Project household net worth from today to life expectancy for both Person 1 and Person 2
- Model discrete financial events (retirement, SS income, expenses, home purchase, career changes, etc.)
- Allow easy scenario comparison by toggling events on/off and adjusting assumptions in config.toml
- Serve results as interactive Plotly HTML on the household LAN
- Live-anchor to Monarch Money account balances on each run

## Scope

In scope:
- Year-by-year net worth projection (accumulation and post-retirement drawdown)
- Per-person modeling (Person 1 and Person 2 with independent retirement dates)
- Event system with typed events and enable/disable flags
- TOML-based configuration (human-readable, easily edited)
- Monarch MCP integration for live balance anchor
- Static Plotly HTML output served via nginx on casalemuria.lan
- GitHub repository for version-controlled config history

Out of scope (V1):
- Full federal/state tax modeling (use simplified brackets)
- Retirement withdrawal optimization (that is OWL's domain)
- Data entry GUI or web form
- Streamlit UI (add later if live-reload is needed)
- Multi-scenario side-by-side chart comparison (V2)

## Roadmap

### Priority #1 — Recurring events
- support recurring expenses/income without duplicating many one-off events
- example: a vacation every X years costing $10,000
- design recurrence semantics that remain understandable in `config.toml`

### Priority #2 — Deeper withdrawal policy controls
- reserve targets / cash-floor behavior
- alternate withdrawal ordering rules
- separate accumulation vs retirement withdrawal behavior

### Priority #3 — Deeper tax realism (after #2)
- bracket-based tax model
- more nuanced Social Security taxation
- state tax treatment

## Success Criteria

- `python run.py` produces a viewable, accurate chart in under 5 seconds
- Changing a config.toml assumption and re-running produces a visibly different chart
- Any LAN device can access the chart at http://casalemuria.lan/finances/
- Events can be toggled on/off without editing Python source
- A new session can resume work immediately from the Memory Bank

## Stakeholders

- Matt — owner, primary user
- Person 2  — modeled household member

## Constraints & Assumptions

- Constraint: No external web services or SaaS dependencies beyond Monarch MCP
- Constraint: Must run on the Hermes host (Linux, Python 3.11+)
- Constraint: Monarch MCP must be authenticated; re-auth via `uv run python login_setup.py` in `/opt/monarch-mcp-server`
- Assumption: Account classification (taxable/trad/Roth/cash) is set once in config and is stable
- Assumption: V1 tax modeling is simplified — full brackets are a V2 enhancement
