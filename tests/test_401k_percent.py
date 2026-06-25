"""Tests for percentage-of-gross-income 401(k) contribution model."""
import pytest
from src import model


class Test401kPercentContribution:
    """Percentage-based 401(k) contribution computation."""

    def test_basic_percent_of_gross(self):
        """Contribution = gross × percent, no growth or escalation."""
        contrib = model._project_person_401k_percent(
            {
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.12,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == pytest.approx(12_000.0)

    def test_gross_income_grows_annually(self):
        """Gross income compounds at GrossIncomeAnnualIncreasePercent."""
        contrib = model._project_person_401k_percent(
            {
                "GrossIncome": 100_000,
                "GrossIncomeAnnualIncreasePercent": 0.05,
                "RetirementContributionPercent": 0.10,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Gross = 100000 × 1.05² = 110250, contrib = 110250 × 0.10 = 11025
        assert contrib == pytest.approx(11_025.0)

    def test_contribution_percent_escalates_annually(self):
        """Contribution percentage increases by escalation each year."""
        contrib = model._project_person_401k_percent(
            {
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.10,
                "RetirementContributionAnnualIncreasePercent": 0.02,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # 2 years: 0.10 + 0.02×2 = 0.14, contrib = 100000 × 0.14 = 14000
        assert contrib == pytest.approx(14_000.0)

    def test_contribution_percent_capped_at_max(self):
        """Escalation stops at RetirementContributionMaxPercent."""
        contrib = model._project_person_401k_percent(
            {
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.10,
                "RetirementContributionAnnualIncreasePercent": 0.05,
                "RetirementContributionMaxPercent": 0.12,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Escalation would be 0.10 + 0.05×2 = 0.20, capped at 0.12
        assert contrib == pytest.approx(12_000.0)

    def test_zero_when_no_gross_income(self):
        """Returns 0 when GrossIncome is missing or zero."""
        contrib = model._project_person_401k_percent(
            {"RetirementContributionPercent": 0.10},
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert contrib == 0.0

    def test_zero_when_no_contribution_percent(self):
        """Returns 0 when RetirementContributionPercent is missing or zero."""
        contrib = model._project_person_401k_percent(
            {"GrossIncome": 100_000},
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
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.15,
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
                "GrossIncome": 500_000,
                "RetirementContributionPercent": 0.50,
                "dob": "1980-01-01",
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
                "GrossIncome": 500_000,
                "RetirementContributionPercent": 0.50,
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
        employee_total = breakdown["trad_ira"] + breakdown["roth"]
        assert employee_total == pytest.approx(19_000.0)
        assert (
            breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        ) == pytest.approx(50_000.0)


class TestContributionChangePercent:
    """ContributionChange event with percent-mode fields."""

    def test_contribution_change_overrides_gross_income(self):
        """ContributionChange can override GrossIncome mid-scenario."""
        events = [
            {
                "type": "ContributionChange",
                "year": 2028,
                "person": "person1",
                "GrossIncome": 120_000,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "percent_of_gross",
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.10,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
            events=events,
        )
        assert breakdown["trad_ira"] == pytest.approx(12_000.0)

    def test_contribution_change_overrides_contribution_percent(self):
        """ContributionChange can override RetirementContributionPercent."""
        events = [
            {
                "type": "ContributionChange",
                "year": 2028,
                "person": "person1",
                "RetirementContributionPercent": 0.20,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "percent_of_gross",
                "GrossIncome": 100_000,
                "RetirementContributionPercent": 0.10,
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
                "RetirementContributionPercent": 0.20,
            }
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "_person_key": "person1",
                "contribution_method": "flat",
                "annual_401k_contribution": 24_225,
                "dob": "1980-01-01",  # 48 years old in 2028, under catch-up age → $23,500 limit
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
            events=events,
        )
        # Flat mode still works, capped at IRS employee limit (younger than 50, no catch-up)
        assert breakdown["employee_401k_capped"] == pytest.approx(23_500.0)


class TestResolveContributionMethod:
    """Method resolution helper."""

    def test_explicit_flat(self):
        assert model._resolve_contribution_method({"contribution_method": "flat"}) == "flat"

    def test_explicit_percent(self):
        assert (
            model._resolve_contribution_method({"contribution_method": "percent_of_gross"})
            == "percent_of_gross"
        )

    def test_default_is_flat(self):
        assert model._resolve_contribution_method({}) == "flat"

    def test_invalid_falls_back_to_flat(self):
        assert model._resolve_contribution_method({"contribution_method": "garbage"}) == "flat"
