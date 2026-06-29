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
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "retirement_contribution_annual_increase_percent": 0.02,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # 2 years: 0.10 + 0.02×2 = 0.14, contrib = 100000 × 0.14 = 14000
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
        employee_total = breakdown["trad_ira"] + breakdown["roth"]
        assert employee_total == pytest.approx(19_000.0)
        assert (
            breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        ) == pytest.approx(50_000.0)


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


class TestEmployerMatchPercent:
    """Percentage-of-gross employer match computation."""

    def test_flat_match_default(self):
        """Flat-dollar employer match is the default behavior."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "annual_401k_employer_match": 5_000,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        assert breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"] == pytest.approx(5_000.0)

    def test_percent_match_basic(self):
        """50% match up to 6% of salary: employee contributes 10%, match = 100K × 6% × 50% = 3,000."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 0.50,
                "annual_401k_employer_match_max_percent": 0.06,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == pytest.approx(3_000.0)

    def test_percent_match_capped_by_employee_percent(self):
        """Employee contributes 4%, match max is 6%. Match = 100K × 4% × 50% = 2,000."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.04,
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 0.50,
                "annual_401k_employer_match_max_percent": 0.06,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == pytest.approx(2_000.0)

    def test_percent_match_with_gross_growth(self):
        """Gross income grows, match tracks grown income."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "gross_income_annual_increase_percent": 0.05,
                "retirement_contribution_percent": 0.10,
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 0.50,
                "annual_401k_employer_match_max_percent": 0.06,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Gross = 100K × 1.05² = 110,250. Match = 110,250 × 6% × 50% = 3,307.50
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == pytest.approx(3_307.50)

    def test_percent_match_routes_through_split(self):
        """Match respects the 401(k) contribution split."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "annual_401k_contribution_split": {"trad_ira": 0.60, "roth": 0.40},
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 1.00,
                "annual_401k_employer_match_max_percent": 0.06,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        # Match = 100K × 6% × 100% = 6,000. Split 60/40 = 3,600 / 2,400
        assert breakdown["employer_match_trad_ira"] == pytest.approx(3_600.0)
        assert breakdown["employer_match_roth"] == pytest.approx(2_400.0)

    def test_percent_match_zero_when_rate_zero(self):
        """No match when match rate is zero."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 0.0,
                "annual_401k_employer_match_max_percent": 0.06,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == 0.0

    def test_percent_match_zero_when_max_percent_zero(self):
        """No match when max matched percent is zero."""
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "contribution_method": "percent_of_gross",
                "gross_income": 100_000,
                "retirement_contribution_percent": 0.10,
                "annual_401k_employer_match_mode": "percent_of_gross",
                "annual_401k_employer_match_rate": 0.50,
                "annual_401k_employer_match_max_percent": 0.0,
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == 0.0


class TestContributionChangeDeltas:

    def test_401k_delta_increases_contribution(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_contribution_delta": 12_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "retirement_contribution_percent": 0.10,
             "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["employee_401k_uncapped"] == pytest.approx(22_000.0)

    def test_401k_delta_negative_decreases_contribution(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_contribution_delta": -3_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "retirement_contribution_percent": 0.10,
             "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["employee_401k_uncapped"] == pytest.approx(7_000.0)

    def test_401k_delta_respects_irs_cap(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_contribution_delta": 25_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "retirement_contribution_percent": 0.10,
             "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["employee_401k_capped"] == pytest.approx(23_500.0)

    def test_ira_delta(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_ira_contribution_delta": 2_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "retirement_contribution_percent": 0.10,
             "annual_ira_contribution": 3_600},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["roth"] == pytest.approx(5_600.0)

    def test_employer_match_delta(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_employer_match_delta": 2_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "retirement_contribution_percent": 0.10,
             "annual_401k_employer_match": 5_000, "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        total_match = breakdown["employer_match_trad_ira"] + breakdown["employer_match_roth"]
        assert total_match == pytest.approx(7_000.0)

    def test_delta_works_in_flat_mode(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_contribution_delta": 10_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "flat",
             "annual_401k_contribution": 20_000, "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["employee_401k_capped"] == pytest.approx(23_500.0)

    def test_delta_compounds_with_growth(self):
        events = [
            {"type": "ContributionChange", "year": 2028, "person": "person1",
             "annual_401k_contribution_delta": 12_000}
        ]
        breakdown = model._person_retirement_contribution_breakdown(
            {"_person_key": "person1", "contribution_method": "percent_of_gross",
             "gross_income": 100_000, "gross_income_annual_increase_percent": 0.05,
             "retirement_contribution_percent": 0.10, "dob": "1980-01-01"},
            year=2028, simulation_start_year=2026,
            assumptions={"inflation": 0.0}, events=events)
        assert breakdown["employee_401k_uncapped"] == pytest.approx(23_025.0)
