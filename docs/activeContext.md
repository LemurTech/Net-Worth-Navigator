# Active Context — Net Worth Navigator

**Last updated:** 2026-07-14
**Status:** v1.5.0 — Real-dollar display shipped, Starlight source now tracked in main repo.

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

### Real-Dollar Display — Phase 1 (2026-07-14)

**Merged to main as v1.5.0**

Adds `[simulation].real_dollar_basis = true/false` (default `false`). When enabled, all chart and table monetary values are deflated to start-year purchasing power using the configured inflation rate. Applies to deterministic, historical, and Monte Carlo modes.

**Implementation:** A single `_apply_real_dollar_basis()` function in `model.py` applies cumulative deflation `(1+inflation)^{-(year-start)}` to 76 whitelisted monetary columns, liability balance columns (pattern-match), and percentile-suffixed band columns (pattern-match). Non-monetary columns (ratios, tax rates, flags, names) are untouched.

**Indicators:** When real-dollar mode is active, the chart subtitle shows "(in YYYY dollars)" and a value-basis note appears below the KPI strip. No indicators when nominal (default).

**Bug fixes discovered during development:**
- **Raw TOML edits lost on Save** — `saveEverything()` only read form fields, not the raw textarea. Server returned 200 with correct `toml_content` but didn't persist when form fields hadn't changed. Fixed by sending `_raw_toml_content` and always writing when present.
- **Browser caching setup page** — Cache-control headers set on the wrong Response object (injected param vs returned TemplateResponse). Fixed by setting on the TemplateResponse.
- **HTML entity corruption** — `{{ content }}` in Jinja2 auto-escaped `&` to `&amp;`, breaking tomlkit parsing. Fixed with `{{ content | safe }}`.
- **Bind mount propagation delay** — Docker volume writes weren't immediately visible from the host. Added `os.fsync()` after every scenario file write.
- **Tab row vertical scrollbar** — `overflow-x: auto` forced `overflow-y: auto`. Added `overflow-y: hidden` to `.tabs`.

**Sample and personal scenarios updated** to enable `real_dollar_basis = true` by default.

**Docs:** Config Reference and FAQ updated in Starlight User Guide.

**Phase 2 (planned):** Client-side JS toggle to switch between nominal and real-dollar views in the same rendered page (both datasets embedded).

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

### README + GitHub Pages (2026-07-08)

### Bug Fixes — Setup Panel Clone & Delete (2026-07-10)

**Clone via Setup Panel silently failed** — `initCloneScenario()` sent `FormData` (multipart) but the backend `_parse_form()` only decodes URL-encoded form bodies. The form fields were silently lost; the JS redirected to the new slug where no file existed, showing the "scenarios/ directory is empty" error.

**Fix:** Switched to `URLSearchParams` with `Content-Type: application/x-www-form-urlencoded`, matching the Save/Render/Validate pattern used elsewhere.

**Clone warning false positive** — The Monarch warning when cloning synthetic-mode scenarios read `_accountsData.source_mode`, which is only populated after the Accounts tab loads. If the user cloned without opening Accounts, the fallback defaulted to `'monarch'`.

**Fix:** Now parses `data_source.mode` directly from the TOML textarea content, which is always authoritative regardless of UI state.

**Clone auto-render delay** — After creating a clone, the backend ran `_render_projection_offline()` (all 3 modes) before responding. This made the clone appear to hang.

**Fix:** Removed auto-render from the clone flow. Clones are instant; the user renders via Save + Re-render when ready.

**Delete modal stuck** — After deleting a scenario, the endpoint called `_render_projection_offline(None)` which re-projects all scenarios just to rebuild the shell pages, blocking the response.

**Fix:** Replaced with lightweight shell rebuild: `write_scenarios_index()` + `build_scenario_shell()` + `build_compare_page()` — no projection, instant response.

**Nightly scenario backup** — Nightly cron (`4d0e4e6f1a35`) backs up gitignored personal .toml files to `/home/lemurtech/.nwn-backups/` with 30-day rolling retention.

**Git hooks** — `post-checkout` warns if personal scenarios go missing; `pre-rebase` + `post-rewrite` auto-snapshot and restore; `pre-commit` blocks committing personal scenarios.

- **Badge cleanup:** Replaced CI and Docs badges (no pipeline/docs site yet) with last-commit and GPL license badges.
- **Banner image:** Projection chart screenshot added below the badge row.
- **"How It Started" rewrite** with personal backstory.
- **Donation link:** Buy Me a Coffee placeholder replaced with live `buymeacoffee.com/lemurtech` link.
- **Pre-rendered sample:** `docs/samples/sample-projection.html` committed for in-repo preview.
- **GitHub Pages:** Orphan `gh-pages` branch created with `index.html` landing page and sample projection. Serve from branch root. URL: `https://lemurtech.github.io/Net-Worth-Navigator/`

### Open Items

### Docs source tracking

- **Starlight source now tracked in main repo** (2026-07-14). `docs/guide/` was previously a nested git repo with no remote — source content lived only locally. After accidental deletion during gh-pages deploy, all 30 content pages were restored from live HTML output and `docs/guide/.git` was removed. Future edits to the guide should be made to `docs/guide/src/content/docs/` and committed to main, then re-deployed to gh-pages via `git worktree add`.

### Feature gaps

- `resolve_state_tax_system()` in `src/tax_model.py` — Maryland's county-level income tax (1.75%-3.2%) is not modeled. State-only brackets provide a useful approximation.
- Validation hardening (Phase 3 from state tax plan): `validate_scenario()` should fail on unknown/misspelled state names instead of silently producing $0.
- No-verification flag on several states' bracket data — should verify against official DOR sources.

### Streamlining candidates

- **`[simulation].clamp_start_year`** — The opt-out exists in code (`default: true`) but is undocumented in user-facing README by design. There's no clear use case for disabling it. Consider removing the option entirely in a future version if no one asks for it.

### Safeguards in place

- **Nightly backup cron** (`4d0e4e6f1a35`) — backs up gitignored personal scenario .toml files every midnight to `/home/lemurtech/.nwn-backups/`, 30-day retention.
- **Git hooks** — `post-checkout` warns if personal scenarios go missing; `pre-rebase` + `post-rewrite` auto-snapshot/restore; `pre-commit` blocks committing personal scenarios.

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
- **Docker container needs Monarch MCP mounts.** The `nwn-config-editor` container cannot access `/opt/monarch-mcp-server`, the uv Python binary, or the token directory unless they are explicitly mounted in `docker-compose.yml`. Required mounts: `/opt/monarch-mcp-server` (ro), `/root/.local/share/uv` (ro), `/root/.monarch-mcp-server`. Without these, the "Refresh from Monarch" button returns a 503 with "not installed on this system."
- **`output/` is gitignored.** Generated HTML and sidecar data not tracked.
- **`POST /api/save-classification` replaces entire `[accounts]` section.** Send ALL accounts.
- **`table_set` in `_QUICK_CONTROL_MAP`** writes to `[taxes].table_set`. Selector defaults to None if no `table_set` is set.
- **Maryland county tax** is not modeled. State-only brackets approximate state liability.
- **Montana and Alabama tax Social Security** (`tax_social_security = true` in TOML).
- **`docs/guide/` was a nested git repo** (fixed 2026-07-14). The Starlight site source was initialized as a standalone git repo inside `docs/guide/` with no remote, so none of the source content was tracked by the main NWN repo. This was discovered when it was accidentally deleted during a gh-pages deploy. Fix: `docs/guide/.git` was removed and all files are now tracked by the main NWN repo. Do NOT re-initialize a nested repo there. To deploy: run `python scripts/build_demo.py --deploy` from the repo root — this handles everything: re-rendering samples, building the static read-only setup pages, building the Starlight guide, and pushing to gh-pages.
- **`src/demo_setup_page.py`** — generates static read-only setup pages for the gh-pages demo. No server-side dependencies. Versioned in the main repo alongside `scripts/build_demo.py`. To update the demo setup page, edit this file and re-deploy.
