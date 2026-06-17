# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-16 → 2026-06-17
**Current Status:** V1 complete. Chart + tabbed tables live. Session ending — resume via `personal-finance-modeling` skill.

## Current State

- `python run.py` — full run (live Monarch), deploys chart
- `python run.py --offline` — offline run (cached), fast re-render
- Chart: http://casalemuria.lan/finances/projection.html
- Accounts tab: trad IRA / Roth / taxable / cash / home equity / total net worth (yearly columns)
- Cash Flow tab: income / living expenses / event outflows / net (yearly columns)
- Both tables scroll horizontally, yearly tick columns

## Cron Jobs

| Job | ID | Schedule | Delivery |
|---|---|---|---|
| NWN — monthly full run | `43255de12c21` | 1st of month, 6am | Telegram |
| NWN — offline render | `da16c8dcea42` | Manual only | local |

**Manual trigger:** `hermes cron run <job_id>`

## Resuming This Project

Load the `personal-finance-modeling` skill — it contains all project
context, run commands, file structure, V1 inventory, and V2 candidates.
Then load `docs/activeContext.md` from the repo for current iteration state.

## Open Items for Next Session

- Confirm `survivor_annual = 66500` feels right (currently 70% of $95K)
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available
- Decide on V2 priority: Gantt tab, tax modeling, or withdrawal sequencing
- Surgery event amount is $18,000 in config — Person 1 confirmed this is correct

## Known Pitfalls

- Monarch auth expires periodically → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- Plotly `add_vrect` annotation_text collides with vline labels — use separate `add_annotation` with `yref="paper"` instead
- `annotation_textangle=-90` + `annotation_position="top right"` is the correct vertical label approach
- `output/` is gitignored — do not commit generated HTML or cache
