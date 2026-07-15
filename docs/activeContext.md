# Active Context — Net Worth Navigator

**Last updated:** 2026-07-15
**Status:** v1.8.0 — Real-dollar JS toggle complete on `feat/real-dollar-toggle`; all dual-view elements built, 18 commits, awaiting code review before merge to main.

---

## Real-Dollar JS Toggle (Phase 2) — Feature Summary

**Branch:** `feat/real-dollar-toggle` (18 commits)
**Approach:** Dual-data embedding with CSS-driven toggle

When `[simulation].real_dollar_basis = true`, the projection page embeds both nominal and real-dollar data. A segmented pill (`💰 Real | 📊 Nominal`) in the value-basis badge bar switches all monetary values instantly via CSS body-class toggling. No page reload, no re-render. Preference persists in localStorage.

### Architecture

| Layer | How |
|---|---|
| **Model** (`model.py`) | `ProjectionResult.nominal_yearly_df` captures pre-deflation DataFrame before `_apply_real_dollar_basis()` runs. Both deterministic and stochastic paths supported. |
| **Main chart** (`charts.py`) | Nominal figure serialized to JSON via `fig.to_plotly_json()`, stored as `<script>var NWN_NOMINAL_FIGURE = {...};</script>`. Lazy `Plotly.newPlot()` on first toggle — avoids Plotly's `display:none` 0×0 initialization bug. |
| **Subsidiary charts** (portfolio, liabilities, cash reserve) | Same lazy-init pattern but using script extraction: nominal `fig.to_html()` output has its `Plotly.newPlot()` script stripped and stored as a JS string variable, `eval()`'d on first toggle. Chart IDs suffixed with `-nominal` to avoid duplicate DOM IDs. |
| **KPI strip** | Dual `<span class='nwn-view-real'>` / `<span class='nwn-view-nominal'>` per monetary value. |
| **Data tables** (5 tables) | `_fmt()` extended with optional `nominal_val` → `data-nominal` attribute on each monetary `<td>`. Toggle JS swaps `innerHTML` ↔ `data-nominal`. Non-monetary cells (years, rates, flags) unchanged. |
| **Cash reserve summary** | Dual `<span>` for minimum cash values per phase. |
| **Tax cumulative summary** | Dual `<span>` for total taxes, federal total, state total. |
| **CSS** | Body-class-driven: `body.nwn-real .nwn-view-nominal { display: none }` etc. No JS iteration of individual elements — CSS cascade handles chart divs, KPI spans, badge text, and pill highlight. |
| **Zoom** | Clamping added to both charts; `_visibleNwnChartId()` helper routes zoom preset buttons to the active chart; x-axis range synced on toggle via save/restore. |

### Verified

- scrollHeight stable at 1664px (baseline, no iframe scrollbar regression)
- All 4 charts (main + 3 subsidiary) render 3 SVGs after toggle
- 999+ `data-nominal` cells across all tables
- localStorage persistence across reloads
- Zero console errors
- No toggle artifacts when `real_dollar_basis=false`

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

### Starlight User Guide Restoration (2026-07-14–15)

**Massive documentation overhaul** after the `docs/guide/` nested repo was accidentally deleted
and all source content was reconstructed from live rendered HTML.

**Corruption fixes:**
- 139 malformed headings across 22 files — Starlight screen-reader "Section titled …" text
  concatenated into markdown headings during HTML-to-markdown conversion
- 5 files with `<starlight-tabs>` component JavaScript injected as literal code blocks
  (`installation.mdx`, `quick-start.mdx`, `command-line-basics.mdx`, `running-the-web-ui.mdx`,
  `monarch-money.mdx`) — rewritten using proper MDX `<Tabs>/<TabItem>` components
- 4 broken image references with missing `](path)` on `manual-entry.mdx`, `projection.mdx`,
  `render-modes.mdx`, `account-types.mdx`
- 15+ flat key-value lists converted to proper Markdown tables across 10 pages
- `index.mdx` restored from default Starlight template ("Welcome to Starlight") to real NWN
  landing page (recovered from historic gh-pages commit `7a108fdc`)
- `projection.mdx` reconstructed from 7 lines to full content (KPI strip, chart controls,
  tabbed panels, year highlighting, data point semantics)
- `render-modes.mdx` expanded from Deterministic-only to full Historical + Monte Carlo +
  Success Metrics + Configuration + Choosing a Mode
- 2 dead Starlight default `example.md` pages removed

**Content additions:**
- New **Social Security Benefits** page (`key-concepts/social-security.mdx`) — SSA.gov
  walkthrough, age 62–70 benefit entry, model semantics, starter template reference
- `home-server.mdx` expanded with platform-specific Python server commands, IP-finding
  instructions, fixed "Run Alongside" section
- `installation.mdx` "Get the Code" rewritten with directory guidance, Git clone + ZIP
  download paths, platform-specific `cd` targets
- `monarch-money.mdx` "Automating Updates" expanded from 2 bullets to full platform tabs
  (cron job with actual syntax, Windows Task Scheduler with 10 numbered steps)
- `quick-start.mdx` list indentation fixed under Web UI section
- `license.mdx` section ordering (Security first, License last)

**Assets recovered:**
- 23 guide images (Git installer screenshots, projection screenshots, Manual Entry form,
  CSV import preview, Gantt chart, render mode examples) recovered from gh-pages branch
  into `docs/guide/public/`
- **NWN favicon** restored — chart sparkline SVG replaces Starlight default compass
- **ImagePreview lightbox** component (`src/components/ImagePreview.astro`) recreated
  and wired into 6 pages

**Docker deployment (v1.5.1 / v1.6.0):**
- `docker-compose.yml` and `nginx-default.conf` added to repo as sample Docker deployment
- Monarch MCP bind mounts documented with platform-specific Linux/Windows instructions
- Docker "All-in-One" section added to `home-server.mdx`
- Monarch MCP Docker mounts added to `docker-compose.yml` — container now reaches
  `/opt/monarch-mcp-server`, uv Python binary, and token directory

- **Badge cleanup:** Replaced CI and Docs badges (no pipeline/docs site yet) with last-commit and GPL license badges.
- **Banner image:** Projection chart screenshot added below the badge row.
- **"How It Started" rewrite** with personal backstory.
- **Donation link:** Buy Me a Coffee placeholder replaced with live `buymeacoffee.com/lemurtech` link.
- **Pre-rendered sample:** `docs/samples/sample-projection.html` committed for in-repo preview.
- **GitHub Pages:** Orphan `gh-pages` branch created with `index.html` landing page and sample projection. Serve from branch root. URL: `https://lemurtech.github.io/Net-Worth-Navigator/`

### Open Items

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
