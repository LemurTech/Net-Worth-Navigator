# Active Context — Net Worth Navigator

**Last updated:** 2026-07-07
**Status:** v1.3.0 — Windows Unicode fix (non-ASCII chars in print() crash cp1252). Accounts tab loads Manual Entry fields on first click. Two commits pushed.

---

## Quick Reference

```bash
cd /home/lemurtech/Net-Worth-Navigator
.venv/bin/python run.py                    # full run (live Monarch) + deploy
.venv/bin/python run.py --offline          # fast re-render from cache
.venv/bin/python run.py --scenario <slug>  # single scenario
.venv/bin/python -m pytest tests/ -q       # run tests
```

**Docs layout:** `docs/` root holds six core Memory Bank files. Plans/references live under `docs/plans/` and `docs/references/`.

| URL | Purpose |
|-----|---------|
| http://casalemuria.lan/finances/projection.html | Shell / scenario selector |
| http://casalemuria.lan/finances/compare.html | Scenario comparison page |
| http://casalemuria.lan/finances/config/setup | Scenario Setup Panel |
| http://casalemuria.lan/finances/definitions.html | Parameter glossary |

## Active Scenarios

| Slug | Description |
|------|-------------|
| `default` | Conservative baseline — max 401k, 70/30 split, $40K cash |
| `comfortable` | Earlier retirement, more travel |
| `optimistic` | Higher returns, earlier aligned retirements |
| `restrictive` | Bearish markets, later retirement |
| `early-death-person1` | Person 1 passes in their 60s |
| `early-death-person2` | Person 2 passes in their 60s |
| `sample` | Single-person share-safe demo (Alex, b. 1972) |
| `sample-couples` | Couples share-safe demo (Alex & Sam) |
| `sample-a` / `sample-b` | A/B comparison pair |
| `starter` / `starter-couple` | Blank-slate templates (hidden from dropdown) |

## Cron Jobs

| Job | ID | Schedule | Delivery |
|-----|----|----------|----------|
| NWN — monthly full run | `43255de12c21` | 1st of month, 6am | Telegram |
| NWN — offline render | `da16c8dcea42` | Manual only | local |

---

## What's New

### Windows Unicode Print Fix (2026-07-07)

Replaced all non-ASCII characters (`→`, `–`, `❌`, `—`, `─`) in `print()` calls and validation error strings with ASCII-safe equivalents (`=>`, `-`, `ERROR`, `--`). These characters crashed Python on Windows (cp1252 code page) with `UnicodeEncodeError`, blocking scenario renders entirely.

**Files patched:** `run.py` (8 sites), `src/monarch_bridge.py` (2 sites), `src/model.py` (1 site).

### Accounts Tab — Manual Entry Fields Loading (2026-07-07)

When selecting a sample/Manual Entry scenario and clicking the Accounts tab, the synthetic input fields (investable balances, property values, liability balances) remained empty because `loadSyntheticTab()` was never called — only the radio change handler triggered it, which never fires on initial page load.

**Fix:** Added `loadSyntheticTab()` call in `initAccountsTab()` after `applyAccountsTabModeState()` for synthetic mode.

### State Tax System — Full Coverage (2026-07-07)

**Engine:** Generalized `resolve_state_tax_system()` to dispatch by mode instead of hardcoded Oregon-only check. Four-path dispatch: no-tax → named engine → bracket table → disabled. `STATE_TAX_ENGINES` registry, `KNOWN_NO_INCOME_TAX_STATES` set.

**50 state TOML files** under `config/tax_tables/`:
- 9 no-income-tax: AK, FL, NV, NH, SD, TN, TX, WA, WY
- 17 flat-rate: AZ 2.5%, AR 4.9%, CO 4.25%, GA 5.39%, IA 3.8%, ID 5.8%, IL 4.95%, IN 3.05%, KY 4%, MA 5%, MI 4.25%, MS 4.7%, NC 4.5%, OH 3.5%, PA 3.07%, RI 3.75%, UT 4.65%
- 1 special engine: OR (table+charts in `oregon_tax_2025.py`)
- 21 progressive: AL, CA, CT, DE, HI, KS, LA, ME, MD, MN, MO, MT, ND, NE, NJ, NM, NY, OK, SC, VT, VA, WI, WV
- Montana and Alabama flagged `tax_social_security = true`

**Source registry:** `docs/references/state-tax-data-sources.md` tracks every state's source URL, access date, notes, and standard deduction amounts.

**Setup Panel:** State Tax dropdown in Metadata → Assumptions & Years section. Fetches available states via `GET /api/tax-states`. Saves `table_set` to `[taxes].table_set` in scenario TOML.

### README Rewrite (2026-07-06)

- GUI-first onboarding (Web UI as Option A everywhere)
- Creator's note: vibe coded, no finance background, PowerShell > Python
- Novice Python install instructions
- Feature overview table, expanded sample scenarios table
- Data source comparison (Manual / Monarch / CSV)
- Security notes (no auth, homelab use)
- Support section with donation links
- Monarch referral link

## Open Items

### Feature gaps

- `resolve_state_tax_system()` in `src/tax_model.py` — Maryland's county-level income tax (1.75%-3.2%) is not modeled. State-only brackets provide a useful approximation.
- Validation hardening (Phase 3 from state tax plan): `validate_scenario()` should fail on unknown/misspelled state names instead of silently producing $0.
- No-verification flag on several states' bracket data — should verify against official DOR sources.

### Confirmation needed

- Confirm survivor spending percentage (currently 70% of retirement spending).
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available.
- Validate `[withdrawal_policy]` cash targets match intent: Accumulation $40K, Retirement $50K, Survivor $30K.

---

## Project Structure (tax table focus)

```
config/tax_tables/
├── 2025_us_federal_oregon.toml          ← Original (Oregon engine)
├── 2025_us_federal_california.toml      ← 10 brackets
├── 2025_us_federal_new_york.toml        ← 7 brackets
├── 2025_us_federal_arizona.toml         ← flat 2.5%
├── 2025_us_federal_washington.toml      ← no tax
├── 2025_us_federal_florida.toml         ← no tax
├── ... 44 more files for remaining states
docs/references/
└── state-tax-data-sources.md            ← source registry
```

## Known Pitfalls

- **Monarch not installed:** Set `[data_source].mode = "synthetic"` or select Manual Entry in Setup Panel.
- **Monarch auth expires:** Re-auth via `cd /opt/monarch-mcp-server && uv run python login_setup.py`
- **`nwn-config-editor` must be restarted after `admin_app.py` changes.** `cd /opt/hal-pages && docker compose restart nwn-config-editor`.
- **`output/` is gitignored.** Generated HTML and sidecar data not tracked.
- **`POST /api/save-classification` replaces entire `[accounts]` section.** Send ALL accounts.
- **`table_set` in `_QUICK_CONTROL_MAP`** writes to `[taxes].table_set`. Selector defaults to None if no `table_set` is set.
- **Maryland county tax** is not modeled. State-only brackets approximate state liability.
- **Montana and Alabama tax Social Security** (`tax_social_security = true` in TOML).
