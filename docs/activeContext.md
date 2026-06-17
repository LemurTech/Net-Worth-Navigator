# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-16 → ongoing
**Current Status:** V1 engine complete and running. Live Monarch balances wired. All core features implemented through End of Plan events.

## Current State

- `python run.py` produces a live chart at http://casalemuria.lan/finances/projection.html
- Monarch bridge pulls live balances via MCP server subprocess
- All 46 Monarch accounts classified in config.toml [accounts]
- Liability amortization running (mortgage + CR-V, auto payoff detection)
- End of Plan events implemented with SS survivor benefit step-up
- All event types carry emoji icons; annotation overlap fixed

## Focus & Next Steps

- [ ] Confirm `survivor_annual = 66500` (70% of $95K) feels right to Person 1
- [ ] Confirm Person 2's SS estimate ($1,200/mo) when SSA.gov is available
- [ ] Consider V2 enhancements (see below)
- [ ] Periodic Monarch re-auth reminder: `cd /opt/monarch-mcp-server && uv run python login_setup.py`

## V2 Candidate Enhancements

- Proper withdrawal sequencing (taxable → trad → Roth) instead of proportional scaling
- Full federal/state tax bracket modeling
- Multi-scenario side-by-side chart comparison (toggle events to compare)
- Streamlit UI for live-reload on config change
- Mortgage payment integration into BuyHome event type
- OWL integration for retirement withdrawal optimization

## Known Issues / Notes

- SocialSecurity event labels now appear only in the start year (correct)
- Survivor period shading label placed in paper-space to avoid collision with vline annotations
- EndOfPlan vlines use bottom-right position to stay clear of survivor label
- `output/` is gitignored — generated HTML is not committed

## Risks / Blockers

- Monarch auth expires periodically — re-auth before planning sessions
- Home equity projected at inflation only (3%/yr) — no real estate market modeling
