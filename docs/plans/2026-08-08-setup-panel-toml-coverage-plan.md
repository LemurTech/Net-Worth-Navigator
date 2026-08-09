# Expose remaining TOML settings in the Setup Panel — staged plan

**Status (2026-08-08):** Stages 0–5 landed. Plan complete.

## Context

The Setup Panel (`templates/setup_panel.html` + `admin_app.py`) already covers scenario identity, household type, cash targets, four `[assumptions]` knobs, sim start/end year + value basis, state tax selection, withdrawal/surplus ordering, full account classification, synthetic starting balances, and full CRUD over `[[events]]`. Enough settings are now exposed that the raw-TOML fallback textarea has become the exception rather than the rule for common tuning — but a large, valuable slice of the config (most notably per-person income/contribution economics and the Social Security benefit-by-age table) is still raw-TOML-only. The user wants a full accounting of that remaining gap and a staged plan to close it, prioritizing the Social Security benefits table first.

This plan was built from three full-repo audits: (1) every TOML field the engine actually reads (grounded in `model.py`/`tax_model.py`/`validate_scenario`, not just sample files), (2) every field the Setup Panel currently exposes vs. raw-TOML-only, (3) the exact resolution/fallback logic for Social Security benefits. A fourth pass confirmed which existing UI/backend patterns are directly reusable.

Two decisions the user made up front:
- Fix all 4 incidental correctness bugs found during the audit as a prerequisite pass (Stage 0), before adding more UI on top of the same code paths.
- Build a small reusable conditional-visibility helper (Stage 2) rather than following the existing "show everything" precedent, since Stage 2 and Stage 5 both have many mode-dependent field groups.

## Reusable patterns confirmed (reuse these, don't reinvent)

1. **Scalar single-field writes** — `_QUICK_CONTROL_MAP` / `_QUICK_ARRAY_MAP` (`admin_app.py`) + `_resolve_toml_path()`, consumed inside `api_save_quick_controls` (`POST /api/save-quick-controls`). Adding any new scalar field (e.g. `taxes.rmd.enabled`, `spending.retirement_annual`) is a one-line map entry — the walk/create-table/set loop needs no changes.
2. **Dynamic key→number table writes** — the Property Values / Liability Balances pattern: JS `addPropertyRow()` + `collectSyntheticData()` serialize dynamic rows into a `{name: value}` dict; `api_save_synthetic_start` whole-table-replaces it via `tomlkit.table()`. Used for `person.social_security_benefits` in Stage 1 (see below) — copy the whole-table-replace approach, not `_resolve_toml_path` (which is for one static field, not a variable-cardinality map).
3. **Array-of-records CRUD** — the Events tab's add/update/delete/toggle endpoints plus `EVENT_FIELDS`-driven modal form. This is the right precedent for `[[liabilities]]` CRUD (Stage 3), since liabilities are also an array of typed records, not a flat map.
4. **Conditional field visibility — does not exist yet.** `EVENT_FIELDS` only swaps the whole field list when the outer event `type` changes; the one existing same-form mode toggle (`annual_401k_employer_match_mode`) shows flat- and percent-mode fields simultaneously with no show/hide wiring. Stage 2 introduces a small `data-visible-when="<mode-value>"` attribute + an `onchange` handler that toggles sibling field-wrapper `display`, reused again in Stage 5 for Monte Carlo failure-mode fields.

## Stage 0 — Prerequisite bug-fix pass (landed 2026-08-08)

- **`validate_scenario`'s stale field check**: fixed to check `person.get("retirement_contribution_percent")` instead of the never-populated `contribution_percent`. Previously this incorrectly failed validation for legitimately configured percent-of-gross-only people.
- **`enabled` default inconsistency**: aligned every call site (`model.py`'s main event filter, `_first_retirement_year`, plus `charts.py`, `sidecars.py`, `tables.py` display helpers) to default missing `enabled` to `True`, matching `_person_event_year` and the SS-benefit validation check. `admin_app.py` already used `True` everywhere.
- **`BuyHome.mortgage_rate` / `term_years`**: removed from the Events tab UI (model never read them — no mortgage amortization is modeled from BuyHome). Help text on Purchase Price now points users to add the loan as a Liability instead.
- **`Education.person`**: removed from the UI (model always treats Education as a household-wide expense regardless of value); help text on Annual Cost clarifies this.
- Regression tests: `tests/test_stage0_fixes.py`.

## Stage 1 — Social Security (landed 2026-08-08)

- **Benefits table editor**: age→monthly-$ dynamic row editor (reuse pattern #2) for `person1.social_security_benefits` / `person2.social_security_benefits`, in a new "Social Security" block in Metadata → People, next to Name/Birth Year. `GET /api/social-security` + `POST /api/save-social-security` (whole-table-replace per person, dropping non-positive/non-numeric entries, sorted by age).
- **Related scalar SS fields** (pattern #1, `_QUICK_CONTROL_MAP`): `person{1,2}.ss_start_age`, `survivor_ss_start_age`, `ss_monthly_benefit` (legacy flat fallback) — saved via the existing `save-quick-controls` flow alongside the rest of Metadata.
- **`saveEverything()`** now chains a Social Security save step between quick-controls and the accounts-mode save, best-effort (proceeds regardless of outcome, matching the existing non-blocking error handling on the accounts branches).
- **Surfaced already-plumbed live data**: `GET /api/events`'s `monthly_benefit` / `benefit_error` per SocialSecurity event now renders on the event card meta line (resolved $/mo, or a `⚠` + the specific missing-benefit message). Also fixed `apiPost()` globally to parse the JSON error body on non-2xx responses instead of discarding it for a generic "API POST returned 400" — this was silently swallowing the specific SS resolution error message (and any other endpoint's `{"error": "..."}` body) on every add/update-event failure across the whole Setup Panel, not just SS.
- Regression tests: `tests/test_social_security_ui.py`.

## Stage 2 — Person employment & contribution economics (landed 2026-08-08)

The single largest remaining gap, now closed. New "Income & Contributions" tab (after Social Security, before Accounts), with a section per person covering: `annual_take_home` + `annual_take_home_real_raise` + `annual_take_home_is_net_of_retirement_contributions`; `contribution_method` (flat/percent_of_gross) with mode-dependent field groups; employer match (`annual_401k_employer_match_mode` + flat/percent fields); `annual_ira_contribution`; bucket routing (`annual_401k_contribution_bucket`, `annual_ira_contribution_bucket`); the `annual_401k_contribution_split.trad_ira`/`.roth` override; and household ownership shares (`rmd_trad_ira_share`, `roth_share`).

Unlike Stage 1, this needed **no new backend endpoints** — every field here is a fixed per-person scalar (no variable-cardinality data like the SS benefits table), so it reuses `_QUICK_CONTROL_MAP`/`_resolve_toml_path` purely by adding ~40 generated map entries (`person{1,2}.<field>`), and reads/writes through the existing `save-quick-controls` flow. Loading happens via the existing raw-TOML regex-scraping system (`initQuickEdit()`) rather than a GET endpoint, extended with a **bounded per-person block extractor** — critical because a naive unbounded regex risks bleeding an optional field from one person's block into the other's if it's missing from the first. Percent-like fields (contribution %, raise %, match rate, ownership shares, split ratios) follow the existing "whole-number-in-UI, fraction-in-TOML" convention already used for `stock_return`/`bond_return`/`equity_allocation` (divide by 100 on save, multiply by 100 on load).

Built the conditional-visibility helper (pattern #4) as a generic `data-mode-target`/`data-mode-group`/`data-visible-when` mechanism (`applyModeGroup()`/`initModeToggles()`), reused for both `contribution_method` and `annual_401k_employer_match_mode` mode toggles in this stage, ready for Stage 5's Monte Carlo failure-mode fields.

## Stage 3 — Liabilities full CRUD (landed 2026-08-08)

Previously the UI only edited *starting balances* for liabilities already in raw TOML. Added a full "Liabilities" card-list + add/edit modal (mirroring the Events tab's CRUD pattern) in the Accounts tab, positioned above the existing balance-only fields and visible regardless of data-source mode (unlike the balance values, which are synthetic-mode-only) — `name`, `type` (mortgage/auto/other), `annual_rate`, `monthly_base`, `monthly_escrow`, `monthly_extra`, via `GET /api/liabilities` + `POST /api/add-liability` / `update-liability` / `delete-liability`.

The name-as-join-key constraint is handled explicitly: renaming a liability migrates its matching `synthetic_start.liability_balances` entry to the new name (`_rename_liability_balance`), and deleting one removes the matching balance entry too (`_remove_liability_balance`) — both verified with a live end-to-end test against a scratch scenario copy, not just unit-level mocks. Duplicate names are rejected on add/rename. After any CRUD action, the UI re-fetches both the liabilities list and the synthetic balance rows so nothing goes stale.

Deferred from Stage 1/2's original scope note (not requested and out of scope here): no attempt is made to update `SellHome.liability_names` event references when a liability is renamed/deleted — only the balance-entry join is kept in sync, matching the plan's original constraint description.

## Stage 4 — Household spending & tax policy baseline + remaining assumptions (landed 2026-08-08)

Added as a collapsed-by-default "Advanced: Spending, Taxes & Assumptions" section at the end of the Metadata tab, reusing the existing `.expander-toggle`/`.expander-content` pattern already used for the withdrawal-order chips (rather than inventing a new collapse mechanism) — since these fields have sensible defaults and are tuned far more rarely than Income/SS. Covers `[spending]` (`retirement_annual`, `survivor_percent_of_retirement`, `survivor_annual`, `spending_basis`), `[taxes]` (`enabled`, the three filing-status fields, `wage_tax_treatment`), `[taxes.rmd]` (`enabled`, `start_age`), and the remaining 9 `[assumptions]` knobs. All via pattern #1 (`_QUICK_CONTROL_MAP`), no new endpoints.

Important gotcha this stage had to solve: several of these field names are **reused verbatim inside `[[events]]` SpendingShift blocks** (`survivor_annual`, `survivor_percent_of_retirement`, `enabled`), and `[taxes]`/`[taxes.rmd]` both have their own `enabled` field. An unbounded regex search for these names risks silently reading (or, worse, the wrong write target) the wrong occurrence. Extended `initQuickEdit()`'s bounded-block extraction approach from Stage 2 (previously per-person) into a generic `sectionBlock(header)` helper that stops at the next `[section]` header, and verified directly via Node against a deliberately adversarial TOML snippet (a `[spending]` section followed by a same-named-field SpendingShift event, and `[taxes]` followed by `[taxes.rmd]`) that the correct value is picked up in both cases. The write side was already safe by construction — `_resolve_toml_path("taxes.enabled")` vs `("taxes.rmd.enabled")` naturally disambiguate via dotted-path navigation — confirmed with an end-to-end save test.

## Stage 5 — Simulation & Monte Carlo controls (landed 2026-08-08)

Added as a second collapsed-by-default expander in the Metadata tab ("Advanced: Simulation & Monte Carlo"), directly below Stage 4's "Advanced: Spending, Taxes & Assumptions" — factored the shared toggle wiring into a small `initExpanderToggle(toggleId, contentId, label)` helper rather than copy-pasting a third near-identical click handler.

- **`[simulation]`**: `render_modes` exposed as three checkboxes (Deterministic — always checked & disabled, since `normalized_render_modes()` always forces it on; Historical; Monte Carlo), saved via a new `_QUICK_ARRAY_MAP["render_modes"]` entry (pattern #2's array-write path, same mechanism as the withdrawal-order chip lists — just collected from checkbox state instead of chip order). Also `num_runs`, `seed` (optional — blank leaves existing/random), `portfolio_return_volatility` (%), and `historical_returns_path` via a new dropdown populated from a new `GET /api/return-sequences` endpoint (mirrors `GET /api/tax-states`, lists `config/return_sequences/*.csv` with row counts).
- **`[monte_carlo.success]`**: `failure_mode` dropdown (5 modes) driving the conditional-visibility helper from Stage 2 (pattern #4) to show only the relevant fields per mode — `minimum_spending_funded_ratio`/`failure_grace_period_months`/`allow_home_equity_for_spending`/`allow_debt_for_spending` for `spending_shortfall`/`preserve_home_equity`, `custom_failure_column`/`_operator`/`_threshold` for `custom`. The visibility helper (`applyModeGroup`) was generalized to accept a comma-separated `data-visible-when` list (e.g. `"spending_shortfall,preserve_home_equity"`) instead of a single exact-match value, since this is the first mode toggle where more than one dropdown value shares a field group — verified backward-compatible with Stage 2's single-value groups (comma-split of a one-item string is a no-op).
- All fields via pattern #1 (`_QUICK_CONTROL_MAP`) except `render_modes`; no collision risk found (`num_runs`/`seed`/`failure_mode`/etc. are not reused elsewhere in the schema), so no new bounded-extraction work was needed beyond reusing `sectionBlock('simulation')` / `sectionBlock('monte_carlo.success')` from Stage 4 — confirmed via an explicit regression test that `[simulation].mode` and `[data_source].mode` (both literally named `mode`) are untouched by a `[simulation]`-targeted save.
- Regression tests: `tests/test_simulation_montecarlo_ui.py`.

This was the last stage in the plan — full TOML coverage in the Setup Panel is now complete (raw-TOML editing remains available for the two explicitly-deferred items below).

## Explicitly deferred / out of scope

- **Tax bracket table editor** (editing `config/tax_tables/*.toml` bracket/deduction numbers inline): high complexity (nested per-filing-status bracket arrays, federal + state), low frequency of need since the state dropdown already covers the common path. Leave as raw-file-edit only unless specifically requested later.
- `[csv_source]` internals beyond what the CSV import flow already writes — already adequately covered.

## Verification (per stage)

- Unit tests: extend `tests/test_tax_model.py` / add new test modules following the existing pattern in `tests/test_social_security_resolution.py` for any new validation logic.
- Manual: after each stage, run `python run.py --offline --scenario sample-couples` (or the relevant sample) before and after editing the new fields via the Setup Panel, and diff the resulting TOML + rendered projection to confirm the UI writes the same shape the engine expects.
