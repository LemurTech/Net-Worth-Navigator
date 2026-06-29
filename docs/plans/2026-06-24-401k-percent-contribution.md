# 401(k) Percentage-of-Gross-Income Contribution Model — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add an optional percentage-of-gross-income 401(k) contribution method alongside the existing flat-dollar method, with auto-escalation, a percentage cap, and ContributionChange event support. Migrate `default.toml` to the new model as a validation test.

**Architecture:** Add a `contribution_method` toggle (`"flat"` | `"percent_of_gross"`) per person. In percentage mode, contributions are computed from `gross_income` × `retirement_contribution_percent`, with `gross_income` growing annually at `gross_income_annual_increase_percent` and the contribution percentage escalating annually by `retirement_contribution_annual_increase_percent` up to `retirement_contribution_max_percent`. The ContributionChange event gains corresponding percent-based override fields. The IRS total limit (employee + employer, $69,000 for 2025) is enforced on top of the existing employee deferral limit.

**Tech Stack:** Python 3.14, TOML config, pytest, Plotly (no change to chart layer).

---

## Task 1: Add new config fields and defaults to model.py

**Objective:** Define the new per-person config fields and their default-fill behavior so the model can reference them without crashing on existing scenarios.

**Files:**
- Modify: `src/model.py`

**Step 1: Add new field defaults to `_person_retirement_contribution_breakdown()`**

The function at line 1369 reads from `person` dict. We need to add default-fallthrough for the new fields so existing scenarios (which lack them) continue to work.

Insert after the `_apply_contribution_changes` call (line 1393), before the `raw_401k` computation (line 1395), add a helper that normalizes the contribution method:

```python
def _resolve_contribution_method(person: dict) -> str:
    """Return the active contribution method for this person: 'flat' or 'percent_of_gross'."""
    method = str(person.get("contribution_method", "flat")).strip().lower()
    return method if method in ("flat", "percent_of_gross") else "flat"
```

In `_person_retirement_contribution_breakdown()`, after line 1393 (the `_apply_contribution_changes` call), add:

```python
    method = _resolve_contribution_method(person)
```

**Step 2: Add the new `_project_person_401k_percent()` function**

Insert after `_project_person_401k_contribution()` (after line 1243):

```python
def _project_person_401k_percent(
    person: dict,
    *,
    year: int,
    simulation_start_year: int,
    assumptions: dict,
) -> float:
    """Return grown annual 401(k) contribution based on percentage of gross income.
    
    Gross income grows annually at gross_income_annual_increase_percent.
    The contribution percentage escalates annually by
    retirement_contribution_annual_increase_percent up to retirement_contribution_max_percent.
    """
    try:
        gross_income = float(person.get("gross_income", 0.0))
    except (TypeError, ValueError):
        return 0.0
    
    try:
        gross_increase = float(person.get("gross_income_annual_increase_percent", 0.0))
    except (TypeError, ValueError):
        gross_increase = 0.0
    
    try:
        contrib_pct = float(person.get("retirement_contribution_percent", 0.0))
    except (TypeError, ValueError):
        return 0.0
    
    try:
        contrib_escalation = float(person.get("retirement_contribution_annual_increase_percent", 0.0))
    except (TypeError, ValueError):
        contrib_escalation = 0.0
    
    try:
        contrib_max = float(person.get("retirement_contribution_max_percent", 1.0))
    except (TypeError, ValueError):
        contrib_max = 1.0
    
    years_elapsed = max(0, int(year) - int(simulation_start_year))
    
    # Grow gross income
    grown_income = gross_income * ((1.0 + gross_increase) ** years_elapsed)
    
    # Escalate contribution percentage, capped at max
    escalated_pct = min(contrib_pct + contrib_escalation * years_elapsed, contrib_max)
    
    return grown_income * max(0.0, escalated_pct)
```

**Step 3: Add IRS total limit constant**

After the existing IRS constants (line 1252), add:

```python
_IRS_401K_TOTAL_LIMIT = 69_000       # 2025 combined employee + employer limit
```

**Step 4: Route between flat and percentage methods in `_person_retirement_contribution_breakdown()`**

Replace lines 1395-1403 (the `raw_401k` computation and cap enforcement block) with:

```python
    if method == "percent_of_gross":
        raw_401k = _project_person_401k_percent(
            person,
            year=year,
            simulation_start_year=simulation_start_year,
            assumptions=assumptions,
        )
    else:
        raw_401k = _project_person_401k_contribution(
            person,
            year=year,
            simulation_start_year=simulation_start_year,
            assumptions=assumptions,
        )
    
    irs_employee_limit = _irs_401k_limit(person, year)
    annual_401k = min(max(0.0, raw_401k), irs_employee_limit)
```

**Step 5: Add IRS total limit enforcement**

After the employer match computation (after line 1444), add total limit enforcement. The total (employee + employer match) cannot exceed `_IRS_401K_TOTAL_LIMIT`. If it does, scale the employee contribution down:

```python
    # ── IRS total limit (employee + employer) ─────────────────────────────────
    total_employee = breakdown["trad_ira"] + breakdown["roth"]
    total_match = match_breakdown["trad_ira"] + match_breakdown["roth"]
    total_combined = total_employee + total_match
    if total_combined > _IRS_401K_TOTAL_LIMIT > 0:
        # Scale down employee contribution to fit under total limit
        allowed_employee = max(0.0, _IRS_401K_TOTAL_LIMIT - total_match)
        if total_employee > 0:
            scale = allowed_employee / total_employee
            for bucket in ("trad_ira", "roth"):
                breakdown[bucket] *= scale
```

**Verification:** Run `pytest tests/ -q` — all 101 existing tests must still pass (no behavior change for flat-dollar mode).

---

## Task 2: Add IRS total limit to breakdown return dict

**Objective:** Include the total limit in the return dict so the Cash Flow table can warn when it's exceeded.

**Files:**
- Modify: `src/model.py`

**Step 1: Add `irs_total_limit` to the return dict**

In `_person_retirement_contribution_breakdown()`, add to the return dict (around line 1454):

```python
    return {
        "trad_ira": breakdown["trad_ira"],
        "roth": breakdown["roth"],
        "employer_match_trad_ira": match_breakdown["trad_ira"],
        "employer_match_roth": match_breakdown["roth"],
        "employee_401k_uncapped": max(0.0, raw_401k),
        "employee_401k_capped": annual_401k,
        "irs_401k_limit": irs_employee_limit,
        "irs_total_limit": _IRS_401K_TOTAL_LIMIT,
        "employee_over_total_limit": max(0.0, total_combined - _IRS_401K_TOTAL_LIMIT) if total_combined > _IRS_401K_TOTAL_LIMIT else 0.0,
    }
```

**Verification:** `pytest tests/ -q` — all tests pass.

---

## Task 3: Extend ContributionChange event for percentage mode

**Objective:** Allow ContributionChange events to override percentage-based contribution fields when the person is in `percent_of_gross` mode.

**Files:**
- Modify: `src/model.py`

**Step 1: Update `_apply_contribution_changes()` to support percent-based fields**

In `_apply_contribution_changes()` (line 1317), add the new fields to the override loop. After the existing `for field in (...)` block (line 1350), add:

```python
        for field in (
            "gross_income",
            "gross_income_annual_increase_percent",
            "retirement_contribution_percent",
            "retirement_contribution_annual_increase_percent",
            "retirement_contribution_max_percent",
        ):
            if field in event:
                try:
                    overrides[field] = float(event[field])
                except (TypeError, ValueError):
                    pass
```

**Step 2: Update the docstring**

Update the docstring at line 1318 to list the new fields:

```python
    """Return a copy of person with ContributionChange overrides applied.
    ...
    Supported override fields (all optional per event):
      annual_401k_contribution
      annual_ira_contribution
      annual_401k_employer_match
      gross_income
      gross_income_annual_increase_percent
      retirement_contribution_percent
      retirement_contribution_annual_increase_percent
      retirement_contribution_max_percent
    """
```

**Verification:** `pytest tests/ -q` — all tests pass.

---

## Task 4: Update definitions page for new fields

**Objective:** Document the new config fields and ContributionChange event fields in the definitions page.

**Files:**
- Modify: `src/definitions_page.py`

**Step 1: Add new per-person field definitions**

After the `annual_401k_contribution_bucket` entry (around line 194), add:

```python
            {
                "key": "[personX].contribution_method",
                "summary": "401(k) contribution method: `flat` (default) or `percent_of_gross`. "
                           "In `percent_of_gross` mode, contributions are computed from gross_income × retirement_contribution_percent.",
            },
            {
                "key": "[personX].gross_income",
                "summary": "Gross annual income used for percentage-based 401(k) contribution computation. "
                           "Only used when `contribution_method = \"percent_of_gross\"`.",
            },
            {
                "key": "[personX].gross_income_annual_increase_percent",
                "summary": "Combined annual gross income increase (COLA + performance + merit) as a decimal. "
                           "Example: 0.05 = 5% annual increase.",
            },
            {
                "key": "[personX].retirement_contribution_percent",
                "summary": "401(k) contribution as a percentage of gross income. "
                           "Example: 0.12 = 12% of gross.",
            },
            {
                "key": "[personX].retirement_contribution_annual_increase_percent",
                "summary": "Annual percentage-point increase in 401(k) contribution rate (auto-escalation). "
                           "Example: 0.02 = increase contribution rate by 2 percentage points each year.",
            },
            {
                "key": "[personX].retirement_contribution_max_percent",
                "summary": "Maximum contribution percentage cap. "
                           "The contribution rate stops escalating once it reaches this value. "
                           "Example: 0.18 = never exceed 18% of gross income.",
            },
```

**Step 2: Update ContributionChange event definition**

After the existing ContributionChange entry (around line 440), update the options list:

```python
                "options": [
                    "Required: `year`, `person` (`person1` or `person2`)",
                    "Optional: `annual_401k_contribution` — new absolute dollar amount",
                    "Optional: `annual_ira_contribution` — new absolute dollar amount",
                    "Optional: `annual_401k_employer_match` — new employer match dollar amount",
                    "Optional: `gross_income` — new gross income for percentage-based contributions",
                    "Optional: `gross_income_annual_increase_percent` — new gross income increase rate",
                    "Optional: `retirement_contribution_percent` — new contribution percentage",
                    "Optional: `retirement_contribution_annual_increase_percent` — new escalation rate",
                    "Optional: `retirement_contribution_max_percent` — new percentage cap",
                    "Multiple events for the same person are applied in year order; later years win",
                ],
```

**Verification:** `pytest tests/ -q` — all tests pass.

---

## Task 5: Update Scenario Parameters display for new fields

**Objective:** Show the new fields in the Scenario Parameters tab so Person 1 can audit percentage-mode settings.

**Files:**
- Modify: `src/tables.py`

**Step 1: Add new fields to `build_scenario_parameters_summary()` person cards**

In the person card loop (around line 693), after the existing `_diff_row` calls for the person, add:

```python
            _diff_row(
                "Contribution method",
                person.get("contribution_method", "flat"),
                baseline_person.get("contribution_method", "flat"),
                _fmt_text,
            ),
            _diff_row(
                "Gross income",
                person.get("gross_income"),
                baseline_person.get("gross_income"),
                _fmt_currency,
            ),
            _diff_row(
                "Gross income annual increase",
                person.get("gross_income_annual_increase_percent"),
                baseline_person.get("gross_income_annual_increase_percent"),
                _fmt_percent,
            ),
            _diff_row(
                "Retirement contribution percent",
                person.get("retirement_contribution_percent"),
                baseline_person.get("retirement_contribution_percent"),
                _fmt_percent,
            ),
            _diff_row(
                "Retirement contribution escalation",
                person.get("retirement_contribution_annual_increase_percent"),
                baseline_person.get("retirement_contribution_annual_increase_percent"),
                _fmt_percent,
            ),
            _diff_row(
                "Retirement contribution max percent",
                person.get("retirement_contribution_max_percent"),
                baseline_person.get("retirement_contribution_max_percent"),
                _fmt_percent,
            ),
```

**Verification:** `pytest tests/ -q` — all tests pass.

---

## Task 6: Write tests for percentage-based contribution model

**Objective:** Test the new percentage computation, growth, escalation, cap, IRS total limit, and ContributionChange interaction.

**Files:**
- Create: `tests/test_401k_percent.py`

**Step 1: Write test file**

```python
"""Tests for percentage-of-gross-income 401(k) contribution model."""
import pytest
from src import model


class Test401kPercentContribution:
    """Percentage-based 401(k) contribution computation."""

    def test_basic_percent_of_gross(self):
        """Contribution = gross × percent, no growth or escalation."""
        contrib = model._project_person_401k_percent(
            {
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.12,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == pytest.approx(12_000.0)

    def test_gross_income_grows_annually(self):
        """Gross income compounds at gross_income_annual_increase_percent."""
        contrib = model._project_person_401k_percent(
            {
                "gross_income": 100_000,
                "gross_income_annual_increase_percent": 0.05,
                "retirement_contribution_percent": 0.10,
            },
            year=2028,  # 2 years after start
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Gross = 100000 × 1.05² = 110250, contrib = 110250 × 0.10 = 11025
        assert contrib == pytest.approx(11_025.0)

    def test_contribution_percent_escalates_annually(self):
        """Contribution percentage increases by escalation each year."""
        contrib = model._project_person_401k_percent(
            {
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "retirement_contribution_annual_increase_percent": 0.02,
            },
            year=2028,  # 2 years: 0.10 + 0.02×2 = 0.14
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == pytest.approx(14_000.0)

    def test_contribution_percent_capped_at_max(self):
        """Escalation stops at retirement_contribution_max_percent."""
        contrib = model._project_person_401k_percent(
            {
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "retirement_contribution_annual_increase_percent": 0.05,
                "retirement_contribution_max_percent": 0.12,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Escalation would be 0.10 + 0.05×2 = 0.20, capped at 0.12
        assert contrib == pytest.approx(12_000.0)

    def test_zero_when_no_gross_income(self):
        """Returns 0 when gross_income is missing or zero."""
        contrib = model._project_person_401k_percent(
            {"retirement_contribution_percent": 0.10},
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == 0.0

    def test_zero_when_no_contribution_percent(self):
        """Returns 0 when retirement_contribution_percent is missing or zero."""
        contrib = model._project_person_401k_percent(
            {"gross_income": 100_000},
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == 0.0


class Test401kPercentBreakdown:
    """Percentage mode integration with _person_retirement_contribution_breakdown."""

    def test_percent_mode_routes_correctly(self):
        """When contribution_method='percent_of_gross', uses percentage math."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.15,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert breakdown["trad_ira"] == pytest.approx(15_000.0)
        assert breakdown["roth"] == 0.0
        assert breakdown["employee_401k_uncapped"] == pytest.approx(15_000.0)

    def test_flat_mode_still_works(self):
        """Flat-dollar mode is unaffected by percent-model changes."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "flat",
                "annual_401k_contribution": 20_000,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert breakdown["trad_ira"] == pytest.approx(20_000.0)

    def test_default_method_is_flat(self):
        """When contribution_method is omitted, flat-dollar mode is used."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "annual_401k_contribution": 20_000,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert breakdown["trad_ira"] == pytest.approx(20_000.0)

    def test_irs_employee_limit_enforced_in_percent_mode(self):
        """Employee deferral cap still applies in percentage mode."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 500_000,
                "retirement_contribution_percent": 0.50,
                "dob": "1980-01-01",  # under 50
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # 50% of 500K = 250K, capped at $23,500
        assert breakdown["employee_401k_capped"] == pytest.approx(23_500.0)
        assert breakdown["irs_401k_limit"] == pytest.approx(23_500.0)

    def test_irs_total_limit_enforced_with_employer_match(self):
        """Employee + employer match cannot exceed $69,000 total limit."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 500_000,
                "retirement_contribution_percent": 0.50,
                "annual_401k_employer_match": 50_000,
                "dob": "1980-01-01",
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Employee raw: 250K, capped at $23,500 (employee deferral)
        # Employer: 50,000
        # Total: 73,500 > 69,000 → scale employee down
        # Allowed employee: 69,000 - 50,000 = 19,000
        assert breakdown["trad_ira"] + breakdown["roth"] == pytest.approx(19_000.0)
        assert breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"] == pytest.approx(50_000.0)


class TestContributionChangePercent:
    """ContributionChange event with percent-mode fields."""

    def test_contribution_change_overrides_gross_income(self):
        """ContributionChange can override gross_income mid-scenario."""
        events = [
            {
                "type": "ContributionChange",
                "year": 2028,
                "person": "person1",
                "gross_income": 120_000,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
            events=events,
        )
        assert breakdown["trad_ira"] == pytest.approx(12_000.0)

    def test_contribution_change_overrides_contribution_percent(self):
        """ContributionChange can override retirement_contribution_percent."""
        events = [
            {
                "type": "ContributionChange",
                "year": 2028,
                "person": "person1",
                "retirement_contribution_percent": 0.20,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
            events=events,
        )
        assert breakdown["trad_ira"] == pytest.approx(20_000.0)

    def test_contribution_change_does_not_affect_flat_mode(self):
        """Percent-mode overrides are ignored when in flat-dollar mode."""
        events = [
            {
                "type": "ContributionChange",
                "year": 2028,
                "person": "person1",
                "retirement_contribution_percent": 0.20,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "flat",
                "annual_401k_contribution": 24_225,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
            events=events,
        )
        assert breakdown["trad_ira"] == pytest.approx(23_500.0)  # capped at IRS limit


class TestResolveContributionMethod:
    """Method resolution helper."""

    def test_explicit_flat(self):
        assert model._resolve_contribution_method({"contribution_method": "flat"}) == "flat"

    def test_explicit_percent(self):
        assert model._resolve_contribution_method({"contribution_method": "percent_of_gross"}) == "percent_of_gross"

    def test_default_is_flat(self):
        assert model._resolve_contribution_method({}) == "flat"

    def test_invalid_falls_back_to_flat(self):
        assert model._resolve_contribution_method({"contribution_method": "garbage"}) == "flat"
```

**Step 2: Run tests to verify failures**

Run: `pytest tests/test_401k_percent.py -v`
Expected: Some tests fail because the new functions don't exist yet.

**Step 3: Implement the functions**

Create `_resolve_contribution_method()` and `_project_person_401k_percent()` in `src/model.py` (as described in Task 1 steps 1-2).

**Step 4: Run tests to verify pass**

Run: `pytest tests/test_401k_percent.py -v`
Expected: All tests pass.

**Step 5: Run full test suite**

Run: `pytest tests/ -q`
Expected: All tests pass (new + existing).

**Step 6: Commit**

```bash
git add tests/test_401k_percent.py src/model.py src/tables.py src/definitions_page.py
git commit -m "feat(401k): add percentage-of-gross-income contribution model

Add optional contribution_method toggle per person: flat (default) or
percent_of_gross. In percent mode, contributions are computed from
gross_income x retirement_contribution_percent, with annual gross income
growth and contribution percentage auto-escalation capped at a
configurable max.

- New _project_person_401k_percent() function
- New _resolve_contribution_method() helper
- IRS total limit ($69,000) enforcement for employee + employer
- ContributionChange event extended with percent-based override fields
- Scenario Parameters and definitions page updated
- 15 new tests covering all paths"
```

---

## Task 7: Migrate default.toml to percentage mode

**Objective:** Convert Person 1's `scenarios/default.toml` from flat-dollar to percentage-of-gross-income 401(k) contributions as a validation test.

**Files:**
- Modify: `scenarios/default.toml`

**Step 1: Determine current values**

Current config (from `default.toml`):
```toml
[person1]
annual_take_home = 74958
annual_take_home_real_raise = 0.02
annual_401k_contribution = 24225
annual_401k_contribution_extra_increase = 0.00
annual_401k_employer_match = 5688

[person2]
annual_take_home = 28512
annual_401k_contribution = 0
annual_401k_employer_match = 0
```

**Step 2: Compute equivalent percentage values**

For person1 (Person 1):
- Gross income estimate: We need to reverse-engineer. `annual_take_home` is net cash. With `annual_take_home_is_net_of_retirement_contributions = true`, the 401(k) contribution was already deducted. So Gross ≈ take_home + 401k_contribution + taxes + other deductions.
- Approximate: $74,958 take-home + $24,225 401(k) = $99,183. Applying a rough 20% effective tax/benefit rate gives ~$124,000 gross.
- This is inherently approximate. The percentage model doesn't depend on getting the exact gross right — it's a planning parameter. Person 1 can tune it.
- Use `gross_income = 100000` as a round number to start, producing a similar contribution level.
- 401(k) contribution: $24,225 / $100,000 = 24.225% → `retirement_contribution_percent = 0.24225`
- No escalation currently: `retirement_contribution_annual_increase_percent = 0.0`
- Cap: just above current rate: `retirement_contribution_max_percent = 0.30`
- Gross income increase: inflation (0.03) + real raise (0.02) = 0.05 → `gross_income_annual_increase_percent = 0.05`

For person2 (Person 2):
- `annual_401k_contribution = 0` — no 401(k) contributions. Keep in flat mode or set to 0%.
- Keep `contribution_method = "flat"` with `annual_401k_contribution = 0` since she doesn't contribute.

**Step 3: Edit `scenarios/default.toml`**

Replace the person1 contribution section:

```toml
[person1]
# Income
contribution_method = "percent_of_gross"
gross_income = 100000    # gross annual income (used for contribution math only)
gross_income_annual_increase_percent = 0.05  # combined COLA + performance (3% inflation + 2% real raise)
annual_take_home = 74958           # net-cash wage input (unchanged)
annual_take_home_is_net_of_retirement_contributions = true
annual_take_home_real_raise = 0.02  # real raise above inflation; total growth ~= (1+inflation)*(1+real_raise)-1

# Retirement contributions (annual) — percentage of gross income
retirement_contribution_percent = 0.24225  # 24.225% of gross income
retirement_contribution_annual_increase_percent = 0.00  # no auto-escalation
retirement_contribution_max_percent = 0.30  # never exceed 30% of gross
annual_401k_employer_match = 5688   # Person 1's annual employer 401(k) match
annual_ira_contribution  = 0

# Keep the split and bucket overrides unchanged
[person1.annual_401k_contribution_split]
trad_ira = 0.95
roth = 0.05
```

Remove the now-unused fields:
```toml
# REMOVE: annual_401k_contribution = 24225
# REMOVE: annual_401k_contribution_extra_increase = 0.00
```

**Step 4: Run offline render to verify**

Run: `.venv/bin/python run.py --offline --scenario default`
Expected: Projection renders successfully. The contribution amounts should be approximately the same as before (~$24,225 in year 1).

**Step 5: Verify Cash Flow table**

Check the generated HTML for the Cash Flow table to confirm:
- `Traditional IRA / 401k contributions — Person 1` shows approximately the same values
- No IRS cap warnings appear (since the contribution is below the employee limit)

**Step 6: Run full test suite**

Run: `pytest tests/ -q`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add scenarios/default.toml
git commit -m "feat(default): migrate Person 1 to percentage-of-gross 401(k) contributions

Switch person1 (Person 1) from flat-dollar to percent_of_gross mode.
gross_income = $100,000, retirement_contribution_percent = 24.225%,
with 5% annual gross income increase and 0% auto-escalation.
Equivalent contribution amount is approximately unchanged from the
prior $24,225 flat-dollar amount."
```

---

## Task 8: Update IRS cap warning in Cash Flow table for total limit

**Objective:** Extend the existing IRS cap warning in `build_cashflow_table()` to also flag total-limit breaches.

**Files:**
- Modify: `src/tables.py`

**Step 1: Add total-limit warning rows**

After the existing employee-limit warning block (around line 1165), add a similar warning for total-limit breaches. Check if the projection DataFrame has `employee_over_total_limit` columns:

```python
    # IRS total limit warnings
    total_over_p1 = col("person1_over_total_limit") if "person1_over_total_limit" in df.columns else []
    total_over_p2 = col("person2_over_total_limit") if "person2_over_total_limit" in df.columns else []
    total_over_years_p1 = [years[i] for i, v in enumerate(total_over_p1) if v]
    total_over_years_p2 = [years[i] for i, v in enumerate(total_over_p2) if v]
    if total_over_years_p1 or total_over_years_p2:
        names_flagged = []
        if total_over_years_p1:
            names_flagged.append(f"{person1_name} ({', '.join(str(y) for y in total_over_years_p1[:3])}{'…' if len(total_over_years_p1) > 3 else ''})")
        if total_over_years_p2:
            names_flagged.append(f"{person2_name} ({', '.join(str(y) for y in total_over_years_p2[:3])}{'…' if len(total_over_years_p2) > 3 else ''})")
        warning_msg = "⚠ IRS total contribution limit exceeded — employee contribution scaled down: " + "; ".join(names_flagged)
        rows.append(
            f"<tr class='section'><th colspan='100' style='color:#fbbf24;background:rgba(251,191,36,0.08);font-weight:500;font-size:12px'>{warning_msg}</th></tr>"
        )
```

**Step 2: Add total-limit columns to the projection DataFrame**

In `model.py`, in the row-building dict (around line 3479), add:

```python
            "person1_over_total_limit": person1_contrib_buckets.get("employee_over_total_limit", 0.0),
            "person2_over_total_limit": person2_contrib_buckets.get("employee_over_total_limit", 0.0),
```

**Verification:** `pytest tests/ -q` — all tests pass.

---

## Task 9: Final validation — full render and compare

**Objective:** Confirm the percentage model produces equivalent results to the flat-dollar model for `default.toml`, and the scenario still renders correctly.

**Files:**
- No changes — validation only.

**Step 1: Run full offline render**

```bash
cd /home/lemurtech/Net-Worth-Navigator
.venv/bin/python run.py --offline
```

**Step 2: Compare sidecar outputs**

Run the scenario shell and check the Compare page to confirm `default` scenario values are similar to the pre-migration state.

**Step 3: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

**Step 4: Commit final validation**

```bash
git add -A
git commit -m "chore: final validation after 401(k) percent-model migration"
```

---

## Summary of All Changes

| File | Change |
|---|---|
| `src/model.py` | +`_resolve_contribution_method()`, +`_project_person_401k_percent()`, routing in `_person_retirement_contribution_breakdown()`, IRS total limit, ContributionChange percent fields, +`_IRS_401K_TOTAL_LIMIT`, total-limit columns in row dict |
| `src/tables.py` | New fields in Scenario Parameters, total-limit warning in Cash Flow table |
| `src/definitions_page.py` | New field definitions, updated ContributionChange docs |
| `tests/test_401k_percent.py` | New: 15 tests covering all paths |
| `scenarios/default.toml` | person1 migrated to `percent_of_gross` mode |

**Estimated new test count:** 101 existing + 15 new = 116 tests.