# Expose remaining TOML settings in the Setup Panel — staged plan

**Status (2026-08-08):** Stages 0, 1, and 2 landed. Stages 3–5 still pending, in priority order below.

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

## Stage 3 — Liabilities full CRUD

Currently the UI only edits *starting balances* for liabilities that already exist in raw TOML (`synthetic_start.liability_balances`, auto-detected read-only names). Add real add/edit/delete for `[[liabilities]]` records (`name`, `type` [mortgage/auto/other], `annual_rate`, `monthly_base`, `monthly_escrow`, `monthly_extra`), reusing pattern #3 (Events-style CRUD + modal form) since this is also an array of typed records. New endpoints: `add-liability` / `update-liability` / `delete-liability`.

Constraint to handle explicitly: a liability's `name` is the join key against `synthetic_start.liability_balances` (synthetic mode) and against Monarch/CSV account names (live mode) — renaming or deleting a liability must keep the balance-entry UI in sync rather than leaving an orphaned balance row.

## Stage 4 — Household spending & tax policy baseline + remaining assumptions

All scalar fields via pattern #1:
- `[spending]`: `retirement_annual`, `survivor_percent_of_retirement` (or `survivor_annual`), `spending_basis`.
- `[taxes]`: `enabled`, `pre_retirement_filing_status`, `retirement_filing_status`, `survivor_filing_status`, `wage_tax_treatment`.
- `[taxes.rmd]`: `enabled`, `start_age` (skip the per-age `factors.<age>` override table — advanced/rare, leave raw-TOML-only).
- Remaining `[assumptions]` knobs: `cash_return`, `real_estate_appreciation`, `real_estate_sale_fee_rate`, `effective_tax_rate_pre_retirement`, `effective_tax_rate_post_retirement`, `taxable_withdrawal_taxable_fraction`, `trad_ira_withdrawal_taxable_fraction`, `initial_taxable_cost_basis_fraction`, `initial_roth_contribution_basis_fraction`.

Present the assumptions/tax-policy additions as a clearly-labeled "Advanced" section in Metadata (collapsed by default) so the primary form doesn't balloon — these mostly have sensible defaults and are tuned rarely.

## Stage 5 — Simulation & Monte Carlo controls

- `[simulation]`: `render_modes` (checkboxes: deterministic/historical/monte_carlo), `num_runs`, `seed`, `portfolio_return_volatility`, `historical_returns_path` (dropdown populated from `config/return_sequences/*.csv`, needs a small new listing endpoint mirroring `GET /api/tax-states`).
- `[monte_carlo.success]`: `failure_mode` dropdown (5 modes) driving the conditional-visibility helper (pattern #4, reused from Stage 2) to show only the relevant fields per mode — `minimum_spending_funded_ratio`/`allow_home_equity_for_spending`/`allow_debt_for_spending`/`failure_grace_period_months` for `spending_shortfall`/`preserve_home_equity`, `custom_failure_column`/`_operator`/`_threshold` for `custom`.

Lowest priority of the "regular" stages — these are tuned far less often than income/spending/SS settings.

## Explicitly deferred / out of scope

- **Tax bracket table editor** (editing `config/tax_tables/*.toml` bracket/deduction numbers inline): high complexity (nested per-filing-status bracket arrays, federal + state), low frequency of need since the state dropdown already covers the common path. Leave as raw-file-edit only unless specifically requested later.
- `[csv_source]` internals beyond what the CSV import flow already writes — already adequately covered.

## Verification (per stage)

- Unit tests: extend `tests/test_tax_model.py` / add new test modules following the existing pattern in `tests/test_social_security_resolution.py` for any new validation logic.
- Manual: after each stage, run `python run.py --offline --scenario sample-couples` (or the relevant sample) before and after editing the new fields via the Setup Panel, and diff the resulting TOML + rendered projection to confirm the UI writes the same shape the engine expects.
