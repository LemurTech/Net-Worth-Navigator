# Active Context — Net Worth Navigator

**Last updated:** 2026-08-09
**Status:** v2.0 — Event-driven timeline. Phase 3c complete: edit, delete, sort.
           TOML cleanup complete: comment stripping, blank-line normalization, migration script.
           Social Security benefit resolution now live/derived, not stored. Dead synthesis code removed.

---

## Current Work

### Couple person sections and percentage display (2026-08-09)

- The Setup Panel now gives each person's Income & Contributions and Social Security sections a visible divider above and below its header. The shared percent-display helper rounds before assigning inputs, preventing binary floating-point artifacts such as `3.5000000000000004` for a TOML value of `0.035`.

### Projection table-header scroll artifact (2026-08-09)

- Removed the dynamic, solid `box-shadow` used to fill the pinned first header cell while horizontally scrolling tables. It was visibly rendered as a dark rectangle that moved across the year headers; the opaque header background and existing z-index now cover the cell without the artifact.

### Single-professional sample life events (2026-08-09)

- Enriched `sample.toml` with the recurring costs that begin after its Town Home mortgage payoff (property tax and homeowners insurance), two Medicare-era health-coverage cost bands, and a bounded parent-care/death sequence with estate costs and a tax-free small inheritance. The mortgage payoff model places the transition after 2049; local deterministic, historical, and Monte Carlo projections completed successfully.

### Couples sample life events (2026-08-09)

- Enriched `sample-couples.toml` with post-mortgage property tax and homeowners-insurance costs, plus four non-overlapping health-coverage periods: Alex's first retirement year, joint Medicare coverage, later-life joint coverage, and Sam's survivor coverage. Parent care is explicitly bounded through 2055 and followed by estate costs and a tax-free small inheritance in 2056. The Home Mortgage pays off in 2049; validation and local deterministic, historical, and Monte Carlo projections completed successfully.

### Sample scenarios are read-only in Setup Panel (2026-08-09)

- Any scenario whose slug begins with `sample` is now protected from Setup Panel writes. Save attempts show one toast directing the user to clone first; API and raw-TOML/render write paths independently return a 403, so the restriction cannot be bypassed from the browser.

### Single-household Person 2 write guard (2026-08-09)

- Setup Panel save payloads now omit Person 2 fields for a single household. The quick-controls and Social Security endpoints also enforce that boundary server-side, preventing a hidden UI field or crafted request from creating a dummy `[person2]` table. Changing a household from couple to single preserves existing Person 2 data rather than deleting it implicitly.

### Roth ownership-share help text (2026-08-09)

- Added in-context explanation for `personX.roth_share`: it is the fallback split for pooled Roth opening balances and unnamed shared Roth flows; account-level Roth owner assignments take precedence.

### Percent-of-gross contribution help text (2026-08-09)

- Added help for gross-income growth, starting contribution rate, and annual contribution-rate increases in both Person 1 and Person 2 percent-of-gross controls. The UI now explicitly distinguishes percentage growth from percentage-point rate increases.

### Cash-target phase guidance (2026-08-09)

- Added an explanation of accumulation, retirement, and survivor cash-target phases with standard help-text top spacing. Survivor cash targets are hidden in single-person scenarios and omitted from their save payloads; the backend ignores a crafted survivor target for those households.

### Survivor Social Security controls (2026-08-09)

- Survivor Claiming Age is now couple-only, matching survivor cash targets. Single-person saves omit the field and the server ignores a crafted value.

### Sample rendering without edits (2026-08-09)

- Sample scenarios remain read-only but can now render from their on-disk TOML. Setup Panel render actions bypass saving/backups for samples, while ordinary save controls remain blocked.

### Setup Panel — post-plan polish and bug fixes (2026-08-08)

Follow-up pass after the staged TOML-coverage plan (below) landed, based on user review of the new Advanced sections:

- **Layout fixes**: `.synth-hint` help text now has proper top margin (the shared class had a negative margin meant for a different context); Withdrawal/Surplus Priority merged into one "Advanced: Withdrawal & Surplus Priorities" panel with uniform styling across all six phase groups (previously Retirement had no border while Accumulation/Survivor did); Wage Treatment only offers "Net Cash" (the only implemented mode); checkboxes are all box-left/label-right via a shared `.checkbox-field` class; new `.inline-row-fluid`/`.inline-row-fixed` CSS helpers replace fixed-width inputs sitting under much wider labels (fixed-width avoids a flexbox quirk where a lone item on a wrapped line stretches to fill it).
- **Household type bug**: the JS defaulted to `hhType = 'couple'` whenever `household_type` wasn't explicitly set in the TOML, instead of inferring from `[person2]` presence like the engine's `_resolve_household_type()` in `model.py` — this misdetected `sample.toml` (a single-person scenario with no explicit `household_type`) as "Couple." Fixed to mirror the engine's actual inference rule exactly; verified via Node against real scenario files plus an adversarial case (explicit `household_type` shouldn't be overridden by a stray commented-out `[person2]` mention).
- **Start Year / End Year clarity**: added help text explaining that Start Year auto-advances to match the account data's as-of date (live Monarch sync, offline cache, or CSV import — not Synthetic) via `simulation.clamp_start_year` (default `true`), and exposed that as a new "Auto-Advance to Data Date" checkbox (`_QUICK_CONTROL_MAP` entry) rather than leaving it raw-TOML-only. End Year is a fixed, manually-set projection cutoff — not auto-derived from lifespan — so added a computed hint showing each person's implied end-of-plan year (from the v2 `EndOfPlan` event if present, else `life_expectancy` + birth year) to give the user something concrete to aim for.

### Setup Panel — Expose Remaining TOML Settings (staged, complete)

Comprehensive audit found a large slice of scenario TOML (per-person income/contribution economics, the Social Security benefit-by-age table, RMD/filing-status settings, Monte Carlo failure-mode config, liability definitions) was still raw-TOML-only in the Setup Panel. Staged rollout plan at `docs/plans/2026-08-08-setup-panel-toml-coverage-plan.md` — all 6 stages (0-5) now landed; full TOML coverage achieved except the two explicitly-deferred items (tax bracket table editor, `[csv_source]` internals).

- **Stage 0 (landed):** Fixed 4 incidental bugs found during the audit — a stale `contribution_percent` validation check (real field is `retirement_contribution_percent`), inconsistent `event.enabled` default across `model.py`/`charts.py`/`sidecars.py`/`tables.py` (now `True` everywhere), removed the dead `BuyHome.mortgage_rate`/`term_years` UI fields (never read by the model), removed `Education.person` from the UI (model always treats it as household-wide).
- **Stage 1 (landed):** New Social Security benefits-table editor (age→monthly $, per person) in its own "Social Security" tab. Also fixed `apiPost()` to surface the actual JSON error message on failed requests instead of a generic "API POST returned 400" — this was silently swallowing specific error messages (like unresolvable SS benefits) across the whole Setup Panel. (Originally placed inside Metadata; moved to its own tab after a broken `<input>` tag — missing closing `>` from an earlier edit — corrupted the DOM nesting and jumbled the layout. Fixed and relocated same day.)
- **Stage 2 (landed):** New "Income & Contributions" tab (after Social Security, before Accounts) covering all per-person employment/contribution economics — take-home pay, contribution method (flat vs. percent-of-gross) with mode-dependent field groups, employer match, IRA routing, 401(k) bucket split override, and household ownership shares. No new backend endpoints needed (all fixed scalars via `_QUICK_CONTROL_MAP`); introduced a bounded per-person regex block extractor in `initQuickEdit()` and a reusable `data-mode-group` conditional-visibility JS helper.
- **Stage 3 (landed):** Full `[[liabilities]]` CRUD (card-list + add/edit modal, mirroring the Events tab pattern) in the Accounts tab, above the existing balance-only fields. `GET /api/liabilities` + add/update/delete endpoints. Renaming or deleting a liability keeps `synthetic_start.liability_balances` in sync (migrates or removes the matching balance entry) rather than leaving it orphaned — verified live against a scratch scenario, not just mocks.
- **Stage 4 (landed):** Collapsed-by-default "Advanced" section at the end of Metadata covering `[spending]` baseline, `[taxes]` filing statuses/enabled/wage treatment, `[taxes.rmd]`, and the remaining 9 `[assumptions]` knobs. Reused the existing `.expander-toggle` pattern rather than inventing a new one. Generalized Stage 2's per-person bounded-block regex extraction into a `sectionBlock()` helper, needed because several field names (`enabled`, `survivor_annual`, `survivor_percent_of_retirement`) are reused inside `[[events]]` SpendingShift blocks and `[taxes.rmd]` — verified the collision avoidance directly via Node against an adversarial TOML snippet.
- **Stage 5 (landed):** Second collapsed "Advanced: Simulation & Monte Carlo" section, below Stage 4's. `[simulation].render_modes` as checkboxes (new `_QUICK_ARRAY_MAP` entry, Deterministic always forced on), `num_runs`/`seed`/`portfolio_return_volatility`/`historical_returns_path` (new dropdown fed by new `GET /api/return-sequences`, mirroring `GET /api/tax-states`). `[monte_carlo.success].failure_mode` dropdown drives Stage 2's conditional-visibility helper to show only the relevant fields per failure mode — generalized `applyModeGroup()` to accept a comma-separated `data-visible-when` list, since this is the first mode toggle with more than one value sharing a field group. No collisions found for these field names, so load/save reuse Stage 4's `sectionBlock()`/`_QUICK_CONTROL_MAP` patterns directly with no new extraction work.

### Social Security Live Benefit Derivation (landed 2026-08-08)

`SocialSecurity` events no longer carry a stored `monthly_benefit` — it's resolved fresh on every read via `resolve_social_security_monthly_benefit()` in `model.py`, from `[personX].social_security_benefits` at the claiming age (derived from the event's `year` and `dob`, or a cached `ss_start_age`). `validate_scenario()` now catches an unresolvable benefit (missing table, missing age entry) as a scenario error instead of letting it silently zero out SS income at projection time. See `docs/plans/2026-08-08-social-security-live-benefit-derivation.md`.

As part of the same pass, the dead synthesis code left behind by the v2.0 refactor below (`_resolve_retirement_events`, `_synthesize_retire_event`, `_resolve_social_security_events`, `_synthesize_social_security_event`, `_person_event_age`, plus three now-orphaned helpers) was deleted from `model.py` — none of it had been reachable from `resolve_runtime_config()` since 2026-08-07.

### v2.0 Event-Driven Timeline (landed 2026-08-07)

`retirement_year`, `ss_start_age`, and `life_expectancy` moved from person config into `[[events]]` blocks. Events tab is now the single place for all timeline decisions.

- **Model:** `_person_event_year()`/`_person_event_age()` helpers. Income zeroing, NewJob guard, validation, contribution processing, and Gantt chart all read events instead of person config.
- **Migration:** `scripts/migrate_v2.py --strip-comments` for production files, no flag for sample files. Sorts events by `(disabled, year, type)`. Strips all comments from production files (header + events). Preserves documentation comments in sample files. Blank-line normalization between all TOML sections.
- **Validation:** `retirement_year` and `life_expectancy` removed from `required_person_fields`. Contribution processing uses event-based retirement check with v1 `person.get()` fallback.

### Phase 3c — Edit, Delete, Sort (landed 2026-08-07)

- **Sort dropdown:** Chronological (default) and By Type modes. Disabled events always at bottom. `localStorage` persistence.
- **Edit:** Edit button on each card opens pre-populated form. `POST /api/update-event`.
- **Delete:** × button with confirm dialog. `POST /api/delete-event`.

### TOML Cleanup Pipeline (landed 2026-08-07)

- **Migration script:** `--strip-comments` flag for production files. Strips all `#` lines (full + inline) from header and events. Reference mode preserves documentation for sample files.
- **Blank-line normalization:** `_normalize_toml_blank_lines` in both the migration script and API. Adds blank lines between ALL TOML sections, not just `[[events]]`.
- **Release notes:** `⚠️ Breaking Change` section in the v2 plan documents the comment-stripping behavior and migration instructions.

**Next:** Phase 3d validation endpoint. Working on `dev` branch.

*(SS benefit live derivation and sample-file documentation enhancement — both listed here previously — landed 2026-08-08.)*

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

## Features Under Consideration

### Feature gaps

- `resolve_state_tax_system()` in `src/tax_model.py` — Maryland's county-level income tax (1.75%-3.2%) is not modeled. State-only brackets provide a useful approximation.
- Validation hardening (Phase 3 from state tax plan): `validate_scenario()` should fail on unknown/misspelled state names instead of silently producing $0.
- No-verification flag on several states' bracket data — should verify against official DOR sources.

### Streamlining candidates

- **`[simulation].clamp_start_year`** — The opt-out exists in code (`default: true`) but is undocumented in user-facing README by design. There's no clear use case for disabling it. Consider removing the option entirely in a future version if no one asks for it.

### Confirmation needed

- Confirm survivor spending percentage (currently 70% of retirement spending).
- Confirm Person 2 SS estimate ($1,200/mo) once SSA.gov is available.
- Validate `[withdrawal_policy]` cash targets match intent: Accumulation $40K, Retirement $50K, Survivor $30K.

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
- **`output/` is gitignored.** Generated HTML and sidecar data not tracked.
- **`POST /api/save-classification` replaces entire `[accounts]` section.** Send ALL accounts.
- **`table_set` in `_QUICK_CONTROL_MAP`** writes to `[taxes].table_set`. Selector defaults to None if no `table_set` is set.
- **Maryland county tax** is not modeled. State-only brackets approximate state liability.
- **Montana and Alabama tax Social Security** (`tax_social_security = true` in TOML).
