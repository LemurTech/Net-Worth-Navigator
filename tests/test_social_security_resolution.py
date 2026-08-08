import unittest
from unittest.mock import patch

from src import model


class ResolveSocialSecurityMonthlyBenefitTests(unittest.TestCase):
    """Unit tests for model.resolve_social_security_monthly_benefit — the live
    benefit-table lookup that replaced trusting a stored `monthly_benefit`
    value on SocialSecurity events."""

    def test_exact_age_match_from_benefit_table(self):
        person = {
            "dob": "1967-04-23",
            "social_security_benefits": {"67": 2691, "70": 3698},
        }
        event = {"type": "SocialSecurity", "person": "person1", "year": 2034}  # age 67

        benefit = model.resolve_social_security_monthly_benefit(person, "person1", event)

        self.assertEqual(benefit, 2691)

    def test_age_derived_from_year_minus_birth_year_when_no_explicit_age(self):
        person = {
            "dob": "1972-03-15",
            "social_security_benefits": {"67": 2020},
        }
        # No ss_start_age, no event["age"] — only year, matching how a hand-authored
        # scenario like sample.toml's single-person plan is structured.
        event = {"type": "SocialSecurity", "person": "person1", "year": 2039}  # 2039 - 1972 = 67

        benefit = model.resolve_social_security_monthly_benefit(person, "person1", event)

        self.assertEqual(benefit, 2020)

    def test_person_ss_start_age_takes_precedence_over_derived_age(self):
        person = {
            "dob": "1967-04-23",
            "ss_start_age": 70,
            "social_security_benefits": {"67": 2691, "70": 3698},
        }
        # Event year would derive to age 67, but the cached ss_start_age (70) wins.
        event = {"type": "SocialSecurity", "person": "person1", "year": 2034}

        benefit = model.resolve_social_security_monthly_benefit(person, "person1", event)

        self.assertEqual(benefit, 3698)

    def test_explicit_event_age_takes_precedence_over_everything(self):
        person = {
            "dob": "1967-04-23",
            "ss_start_age": 70,
            "social_security_benefits": {"62": 1553, "70": 3698},
        }
        event = {"type": "SocialSecurity", "person": "person1", "year": 2034, "age": 62}

        benefit = model.resolve_social_security_monthly_benefit(person, "person1", event)

        self.assertEqual(benefit, 1553)

    def test_legacy_ss_monthly_benefit_scalar_fallback_when_table_missing(self):
        person = {"dob": "1967-04-23", "ss_monthly_benefit": 2500}
        event = {"type": "SocialSecurity", "person": "person1", "year": 2037, "age": 70}

        benefit = model.resolve_social_security_monthly_benefit(person, "person1", event)

        self.assertEqual(benefit, 2500)

    def test_raises_when_benefit_table_missing_entirely(self):
        person = {"dob": "1967-04-23"}
        event = {"type": "SocialSecurity", "person": "person1", "year": 2037, "age": 70}

        with self.assertRaises(ValueError):
            model.resolve_social_security_monthly_benefit(person, "person1", event)

    def test_raises_when_benefit_table_missing_age_entry(self):
        person = {
            "dob": "1967-04-23",
            "social_security_benefits": {"62": 1553, "65": 2164},
        }
        event = {"type": "SocialSecurity", "person": "person1", "year": 2037, "age": 70}

        with self.assertRaises(ValueError):
            model.resolve_social_security_monthly_benefit(person, "person1", event)

    def test_raises_when_age_cannot_be_determined(self):
        # No event age, no person.ss_start_age, no dob to derive from year.
        person = {"social_security_benefits": {"67": 2691}}
        event = {"type": "SocialSecurity", "person": "person1", "year": 2034}

        with self.assertRaises(ValueError):
            model.resolve_social_security_monthly_benefit(person, "person1", event)


class RunProjectionSocialSecurityLiveDerivationTests(unittest.TestCase):
    """Integration-level: run_projection must derive SS income from the
    benefit table every year, not from a stored monthly_benefit snapshot."""

    def _base_config(self):
        return {
            "simulation": {"start_year": 2026, "end_year": 2026},
            "assumptions": {
                "stock_return": 0.0,
                "bond_return": 0.0,
                "inflation": 0.0,
                "equity_allocation": 0.0,
                "effective_tax_rate_pre_retirement": 0.0,
                "effective_tax_rate_post_retirement": 0.0,
                "taxable_withdrawal_taxable_fraction": 0.0,
                "trad_ira_withdrawal_taxable_fraction": 0.0,
            },
            "taxes": {"enabled": False},
            "person1": {
                "name": "Person 1",
                "dob": "1959-01-01",
                "retirement_year": 2020,
                "annual_take_home": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_ira_contribution": 0.0,
                "social_security_benefits": {"67": 2500},
            },
            "spending": {"retirement_annual": 0.0, "spending_basis": "nominal"},
            "withdrawal_policy": {
                "accumulation_cash_target": 0.0,
                "retirement_cash_target": 0.0,
                "survivor_cash_target": 0.0,
                "accumulation_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "retirement_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "survivor_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
            },
            "liabilities": [],
        }

    def test_income_derives_from_benefit_table_not_a_stored_value(self):
        config = self._base_config()
        # year=2026, dob=1959 -> derived age 67 -> table says 2500/mo -> 30,000/yr.
        config["events"] = [
            {
                "enabled": True,
                "type": "SocialSecurity",
                "label": "SS Begins (M)",
                "person": "person1",
                "year": 2026,
            }
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        self.assertAlmostEqual(float(df.iloc[0]["person1_income"]), 30_000.0, places=2)

    def test_income_reflects_updated_benefit_table_without_touching_the_event(self):
        # Same event both times — only the benefit table changes. If anything
        # were still reading a stored monthly_benefit off the event, this
        # would not move.
        config = self._base_config()
        config["events"] = [
            {"enabled": True, "type": "SocialSecurity", "label": "SS Begins (M)", "person": "person1", "year": 2026}
        ]

        with patch("src.model.load_config", return_value=config):
            df_before = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        config["person1"]["social_security_benefits"]["67"] = 3000

        with patch("src.model.load_config", return_value=config):
            df_after = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        self.assertAlmostEqual(float(df_before.iloc[0]["person1_income"]), 30_000.0, places=2)
        self.assertAlmostEqual(float(df_after.iloc[0]["person1_income"]), 36_000.0, places=2)

    def test_run_projection_raises_when_benefit_cannot_be_resolved(self):
        config = self._base_config()
        del config["person1"]["social_security_benefits"]
        config["events"] = [
            {"enabled": True, "type": "SocialSecurity", "label": "SS Begins (M)", "person": "person1", "year": 2026}
        ]

        with patch("src.model.load_config", return_value=config):
            with self.assertRaises(ValueError):
                model.run_projection(
                    balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                    home_value=0.0,
                    liability_balances={},
                )


class ValidateScenarioSocialSecurityTests(unittest.TestCase):
    """validate_scenario() must catch an unresolvable SS benefit up front,
    for hand-edited TOML that never goes through the Setup Panel UI."""

    def _base_config(self):
        return {
            "scenario": {"name": "Test", "slug": "test"},
            "simulation": {"start_year": 2026, "end_year": 2060},
            "assumptions": {"stock_return": 0.07, "bond_return": 0.04, "inflation": 0.03},
            "spending": {"retirement_annual": 50000},
            "person1": {
                "name": "Person 1",
                "dob": "1959-01-01",
            },
            "events": [
                {"enabled": True, "type": "EndOfPlan", "person": "person1", "year": 2049},
                {"enabled": True, "type": "SocialSecurity", "label": "SS Begins (M)", "person": "person1", "year": 2026},
            ],
        }

    def test_valid_when_benefit_table_covers_the_resolved_age(self):
        config = self._base_config()
        config["person1"]["social_security_benefits"] = {"67": 2500}

        is_valid, errors = model.validate_scenario(config)

        ss_errors = [e for e in errors if "Social Security" in e]
        self.assertEqual(ss_errors, [])

    def test_invalid_when_benefit_table_is_missing(self):
        config = self._base_config()

        is_valid, errors = model.validate_scenario(config)

        self.assertFalse(is_valid)
        self.assertTrue(any("Social Security" in e for e in errors))

    def test_invalid_when_benefit_table_lacks_the_resolved_age(self):
        config = self._base_config()
        config["person1"]["social_security_benefits"] = {"62": 1800}

        is_valid, errors = model.validate_scenario(config)

        self.assertFalse(is_valid)
        self.assertTrue(any("Social Security" in e for e in errors))

    def test_disabled_social_security_event_is_not_validated(self):
        config = self._base_config()
        config["events"][1]["enabled"] = False
        # No benefit table at all — would fail if the disabled event were checked.

        is_valid, errors = model.validate_scenario(config)

        ss_errors = [e for e in errors if "Social Security" in e]
        self.assertEqual(ss_errors, [])


if __name__ == "__main__":
    unittest.main()
