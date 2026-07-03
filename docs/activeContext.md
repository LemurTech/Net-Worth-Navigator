# Active Context — Net Worth Navigator

**Last updated:** 2026-07-03
**Status:** Phase 3 (validation, help mode, sample guidance) shipped 2026-07-02. Follow-up bug fix pass on help-mode/iframe/tooltip UX complete 2026-07-03 — see `progress.md` for full list. Ready to commit/push per user instruction.

---

## Quick Reference

```bash
cd /home/lemurtech/Net-Worth-Navigator
.venv/bin/python run.py                    # full run (live Monarch) + deploy
.venv/bin/python run.py --offline          # fast re-render from cache
.venv/bin/python run.py --scenario <slug>  # single scenario
.venv/bin/python -m pytest tests/ -q       # run tests
```

| URL | Purpose |
|---|---|
| http://casalemuria.lan/finances/projection.html | Shell / scenario selector |
| http://casalemuria.lan/finances/compare.html | Scenario comparison page |
| http://casalemuria.lan/finances/config/ | Raw TOML config editor (legacy) |
| http://casalemuria.lan/finances/config/setup | Scenario Setup Panel (new) |
| http://casalemuria.lan/finances/definitions.html | Parameter glossary |

## Active Scenarios

| Slug | Description |
|---|---|
| `default` | Conservative baseline — max 401k, 70/30 split, $40K cash |
| `comfortable` | Earlier retirement, more travel |
| `optimistic` | Higher returns, earlier aligned retirements |
| `restrictive` | Bearish markets, later retirement |
| `early-death-person1` | Person 1 passes in his 60s |
| `early-death-person2` | Person 2 passes in her 60s |
| `sample` / `sample-a` / `sample-b` | Synthetic share-safe demo scenarios (Alex & Sam) |
| `starter` | Blank-slate template for new non-Monarch users |

All household TOMLs use 24% 401k contribution ($31K IRS cap), 70/30 trad/Roth split, and $40K/$50K/$30K cash targets.

## Cron Jobs

| Job | ID | Schedule | Delivery |
|---|---|---|---|
| NWN — monthly full run | `43255de12c21` | 1st of month, 6am | Telegram |
| NWN — offline render | `da16c8dcea42` | Manual only | local |

**Manual trigger:** `hermes cron run <job_id>`

---

## Open Items

### Confirmations needed

- Confirm survivor spending percentage feels right (currently 70% of retirement spending).
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available.
- Validate `[withdrawal_policy]` cash targets match intent:
  - Accumulation: $40,000 | Retirement: $50,000 | Survivor: $30,000

### Recent changes requiring re-render

- User needs to run a full manual re-render to reflect the updated scenario configs (24% 401k, 70/30 split, new cash targets, deleted early-mortgage scenarios).

### Ignidash port plan status

| Phase | Status | Notes |
|---|---|---|
| 1 — Result contracts | ✅ Done | `ProjectionResult`, normalized sidecars |
| 2 — Monte Carlo / Historical | ✅ Done | All three render modes, Simulation tab |
| 3 — Richer account mechanics | ✅ Done | Cost basis, Roth basis, owner splits |
| 4 — Contribution rules | ✅ Done | IRS caps enforced, employer match modeled |
| 5 — Tax engine refactor | 🔄 Ongoing | Federal + Oregon active; see below |
| 6 — Comparison UX | ✅ Done | `compare.html` with deep-linking, delta chart |
| 7 — Interchange layer | — | Optional; low priority |

### Phase 4 follow-ons (contribution rules)

- IRS cap **year-over-year indexing** — currently fixed at 2025 values; update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` annually.
- Rate-based employer match (`annual_401k_employer_match_rate` as % of salary proxy) — V2 if needed.
- HSA modeling — optional later slice.

### Phase 5 (tax engine)

- Oregon state tax refinement and validation.
- Gross-income migration for wages is optional unless targeting a full household tax return.

### Monarch-optional roadmap

Plan: `docs/plans/2026-07-01-monarch-optional.md`

| Phase | Status | Description |
|---|---|---|
| 1 — Error handling | ✅ Done | Pre-flight check in `fetch_raw_accounts()`; `MONARCH_MCP_PATH` env var; clean error in `run.py` |
| 2 — Setup Panel UI | ✅ Done | Synthetic-mode banner in Accounts tab; disable Refresh button; clean 503 from API; radio sync |
| 3 — Starter template | ✅ Done | `scenarios/starter.toml` blank-slate TOML; README "Getting Started Without Monarch" section |
| 4 — New-scenario flow | ✅ Done | "New from Template" button in Setup Panel; clone-source warning |
| 5 — Structural / CSV | 🔲 Future | CSV import, DataSourceProvider abstraction, Docker portability |



Grouped by implementation area.

#### Projection Page — Cash Flow Tab

- [x] **Add cash flow graph to the Cash Flow tab.** Model after the existing cash flow graph on the `Compare` page, reusing the same visual structure, data conventions, formatting, and interaction patterns.

#### 401(k) Contribution Model

- [x] **Reassess 401(k) contribution modeling.** Currently flat annual contribution + flat annual increase. Evaluate refactoring to percentage-of-gross-income contributions with variables: `gross_income`, `gross_income_annual_increase_percent`, `retirement_contribution_percent`, `retirement_contribution_annual_increase_percent`, `retirement_contribution_max_percent`. Design decision: replace flat-dollar entirely, or support both with a user-selectable method. Update `ContributionChange` event to support percentage-based changes.

#### Compare Page — Annual Cash Flow Card

- [x] **Round net flow values in chart popup overlays.** Net flow values should use the same currency rounding and formatting conventions used elsewhere in the application.
- [x] **Fix negative currency formatting.** Negative amounts display as `$-` instead of `-$`. Expected: `-$1,250` not `$-1,250`.

#### Compare Page — Investment Portfolio Trajectory

- [x] **Investigate sudden drop-to-zero in portfolio trajectory graph.** Root cause: JS `parseCSV()` used naive `line.split(',')` which split on commas inside quoted CSV fields — the `events_active` column contains comma-separated event labels, and 6 rows had those commas treated as field delimiters, shifting `taxable`/`trad_ira`/`roth` into wrong columns. Fixed by replacing with a state-machine `parseCSVLine()` parser that respects CSV quoting.

#### Surplus Routing

- [x] **Change surplus routing from proportional-by-balance to ordered priority.** `_apply_surplus_with_reserve_target` now iterates through `*_surplus_order` as a strict priority chain. Default order: Roth → taxable.
- [x] **Add Roth IRA contribution caps to surplus routing.** Per-person age-dependent limits ($7K under 50, $8K 50+) enforced on surplus to Roth bucket. Planned IRA contributions subtract from remaining room. Excess spills to next surplus_order bucket.
- [x] **Fix SellHome reinvestment timing.** Reinvestment processing moved inside the tax iteration loop, before the surplus sweep, so reinvested proceeds reach their target before the ordered priority applies.
- [x] **Add Surplus Routing section to Cash Flow table.** Dedicated rows for `Surplus to Roth`, `Surplus to taxable brokerage`, `Surplus to traditional IRA / 401k`.
- [x] **Update all personal scenario TOMLs** to reflect new surplus order `["roth", "taxable"]`. Sample scenarios left unchanged.

---

## Known Pitfalls

- **Monarch not installed:** `run.py` now exits cleanly with an actionable message rather than a Python traceback. Set `[data_source].mode = "synthetic"` in the scenario to bypass Monarch entirely. Set `MONARCH_MCP_PATH` env var to override the default `/opt/monarch-mcp-server` location.
- **Monarch auth expires** → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- **`nwn-config-editor` must be restarted after any `admin_app.py` change.** `cd /opt/hal-pages && docker compose restart nwn-config-editor`. Symptom: `{"detail":"Not Found"}` from `/render-jobs` or `/jobs/{id}`.
- **`output/` is gitignored.** Do not commit generated HTML or sidecar data.
- **Scenario TOMLs are local-only** (gitignored). Rollback via backups in `output/config-backups/<slug>/`. Backups are kept for 14 days (min 5 most recent); deduplication prevents redundant backups when saving the same state.
- **Plotly y-axis title standoff** alone is insufficient when `margin.l` is too narrow. Fix: `automargin: true` + `margin.l >= 80` for `$X.XXM`-format tick labels.
- **CSV fields containing the delimiter must be quoted.** Pandas `to_csv()` quotes fields containing commas by default, but a naive JS `split(',')` parser will still split inside quotes. Use a state-machine parser (`parseCSVLine`) that tracks `inQuotes` and strips wrapping double-quotes. The `events_active` column is the primary offender — it contains comma-separated event labels.
- **Delta chart y-axis labels with `+` prefix are wider.** The `tickformat: '+$.2f'` format adds a `+` sign to all values, making labels wider than the standard `$.2f` format used in other charts. This can cause bottom-left corner overlap with x-axis year labels. Increase `margin.l` (≥100) and `margin.b` (≥72) beyond the values used for other charts.
- **IRS 401(k) cap constants** are hardcoded at 2025 values. Update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` each year.
- **Employer match is always prefunded** — never a cash outflow from take-home. Routes into same `annual_401k_contribution_split` as the employee contribution. Do not double-count as income.
- **Plotly `add_vrect` annotation_text** collides with vline labels — use a separate `add_annotation` with `yref="paper"` instead.
- **For routine UI/layout tweaks**, prefer targeted checks + `run.py --offline`. Reserve the full test suite for model changes or pre-commit passes.
- **`POST /api/save-classification` replaces the entire `[accounts]` section.** The client must send ALL accounts, not just changed ones. Any account omitted from the request body is removed from the TOML. If you test with a single-account payload, the accounts section will be wiped and the next render will produce $0 investable/home values. Restore from a backup in `output/config-backups/<slug>/`.
- **Table sticky headers require build-time splitting** (`src/charts.py:_wrap_table_with_sticky_header`). `position: sticky` on `<thead>` fails inside any ancestor with `overflow-x: auto` — the overflow container becomes the sticky scrollport. The fix: split each `<table>` into a header table (in `.sticky-header-wrap`, no overflow ancestor → sticky works) and a body table (in `.table-scroll`, overflow-x: auto). Both use `table-layout: fixed` with explicit `<colgroup>` pixel widths so columns align identically.
- **`position: sticky; left: 0` on `<th>` is unreliable.** Use JS `transform: translateX(scrollX)` + `boxShadow` on the header rowlabel instead. The box-shadow fills the gap where the cell was before translation.
- **`data-col` attributes must be on both header `<th>` and body `<td>` cells** for year-highlight to work. If `git checkout` restores an old version of `src/tables.py`, these are lost. Verify with `search_files('data-col')` in the output.
- **Plotly chart height directly affects mobile legend spacing.** If two charts share identical responsive legend/margin logic, they must also share height and initial margins. A 340px chart with the same legend config as a 420px chart will overlap.
- **Tabulator.js frozen/sticky features require Tabulator's own internal scroll container** — they won't engage in full-height tables with page-level scrolling.
- **Help-mode/tooltip wiring exists in TWO places (`build_scenario_shell()` and `build_compare_page()` in `scenario_shell.py`).** They render separate documents and do not share JS — verify a fix lands in the function whose output is actually deployed, not just "a" matching function in the file. See `systemPatterns.md` UI Engineering Lessons (2026-07-03) for the full iframe/tooltip lesson set (position:fixed centering, iframe content clipping, box-sizing mismatches, touch `:hover` limitations).
