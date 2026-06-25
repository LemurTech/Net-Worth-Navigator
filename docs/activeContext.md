# Active Context — Net Worth Navigator

**Last updated:** 2026-06-24
**Status:** Stable. All charts and tests passing. Compare page CSV parsing hardened against quoted-field delimiters.

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
| http://casalemuria.lan/finances/config/ | Raw TOML config editor |
| http://casalemuria.lan/finances/definitions.html | Parameter glossary |

## Active Scenarios

| Slug | Description |
|---|---|
| `default` | Conservative baseline — Person 1's primary scenario |
| `comfortable` | Earlier retirement, more travel |
| `optimistic` | Higher returns, earlier aligned retirements |
| `restrictive` | Bearish markets, later retirement |
| `default-early-mortgage` | Default + accelerated mortgage paydown |
| `comfortable-early-mortgage` | Comfortable + accelerated mortgage paydown |
| `optimistic-early-mortgage` | Optimistic + accelerated mortgage paydown |
| `early-death-person1` | Person 1 passes in his 60s |
| `early-death-person2` | Person 2 passes in her 60s |
| `sample` / `sample-a` / `sample-b` | Synthetic share-safe demo scenarios (Alex & Sam) |

All household TOMLs are **gitignored local files**. `annual_401k_employer_match = 5688` is set in all 9 household scenarios.

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
  - Accumulation: $64,000 | Retirement: $95,000 | Survivor: $66,500

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

### Immediate Roadmap

Grouped by implementation area.

#### Projection Page — Cash Flow Tab

- [x] **Add cash flow graph to the Cash Flow tab.** Model after the existing cash flow graph on the `Compare` page, reusing the same visual structure, data conventions, formatting, and interaction patterns.

#### 401(k) Contribution Model

- [x] **Reassess 401(k) contribution modeling.** Currently flat annual contribution + flat annual increase. Evaluate refactoring to percentage-of-gross-income contributions with variables: `GrossIncome`, `GrossIncomeAnnualIncreasePercent`, `RetirementContributionPercent`, `RetirementContributionAnnualIncreasePercent`, `RetirementContributionMaxPercent`. Design decision: replace flat-dollar entirely, or support both with a user-selectable method. Update `ContributionChange` event to support percentage-based changes.

#### Compare Page — Annual Cash Flow Card

- [x] **Round net flow values in chart popup overlays.** Net flow values should use the same currency rounding and formatting conventions used elsewhere in the application.
- [x] **Fix negative currency formatting.** Negative amounts display as `$-` instead of `-$`. Expected: `-$1,250` not `$-1,250`.

#### Compare Page — Investment Portfolio Trajectory

- [x] **Investigate sudden drop-to-zero in portfolio trajectory graph.** Root cause: JS `parseCSV()` used naive `line.split(',')` which split on commas inside quoted CSV fields — the `events_active` column contains comma-separated event labels, and 6 rows had those commas treated as field delimiters, shifting `taxable`/`trad_ira`/`roth` into wrong columns. Fixed by replacing with a state-machine `parseCSVLine()` parser that respects CSV quoting.

---

## Known Pitfalls

- **Monarch auth expires** → re-auth: `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- **`nwn-config-editor` must be restarted after any `admin_app.py` change.** `cd /opt/hal-pages && docker compose restart nwn-config-editor`. Symptom: `{"detail":"Not Found"}` from `/render-jobs` or `/jobs/{id}`.
- **`output/` is gitignored.** Do not commit generated HTML or sidecar data.
- **Scenario TOMLs are local-only** (gitignored). Rollback via backups in `output/config-backups/<slug>/`.
- **Plotly y-axis title standoff** alone is insufficient when `margin.l` is too narrow. Fix: `automargin: true` + `margin.l >= 80` for `$X.XXM`-format tick labels.
- **CSV fields containing the delimiter must be quoted.** Pandas `to_csv()` quotes fields containing commas by default, but a naive JS `split(',')` parser will still split inside quotes. Use a state-machine parser (`parseCSVLine`) that tracks `inQuotes` and strips wrapping double-quotes. The `events_active` column is the primary offender — it contains comma-separated event labels.
- **Delta chart y-axis labels with `+` prefix are wider.** The `tickformat: '+$.2f'` format adds a `+` sign to all values, making labels wider than the standard `$.2f` format used in other charts. This can cause bottom-left corner overlap with x-axis year labels. Increase `margin.l` (≥100) and `margin.b` (≥72) beyond the values used for other charts.
- **IRS 401(k) cap constants** are hardcoded at 2025 values. Update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` each year.
- **Employer match is always prefunded** — never a cash outflow from take-home. Routes into same `annual_401k_contribution_split` as the employee contribution. Do not double-count as income.
- **Plotly `add_vrect` annotation_text** collides with vline labels — use a separate `add_annotation` with `yref="paper"` instead.
- **For routine UI/layout tweaks**, prefer targeted checks + `run.py --offline`. Reserve the full test suite for model changes or pre-commit passes.
