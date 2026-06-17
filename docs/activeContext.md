# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-16 → ongoing
**Current Status:** V1 engine complete and running. Live Monarch balances wired. All core features implemented through End of Plan events.

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (uses cached balances), deploys chart
- Balances cache: `output/balances_cache.json` — written on every full run
- Chart live at http://casalemuria.lan/finances/projection.html

## Cron Jobs

| Job | ID | Schedule | Delivery |
|---|---|---|---|
| NWN — monthly full run | `43255de12c21` | 1st of month, 6am | Telegram |
| NWN — offline render | `da16c8dcea42` | Manual trigger only | local |

**Manual trigger:** `hermes cron run <job_id>` — works for both jobs.
The offline render job is scheduled far in the future (2099) so it never auto-fires; use `hermes cron run da16c8dcea42` to trigger on demand.

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
