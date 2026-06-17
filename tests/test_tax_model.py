import unittest
from unittest.mock import patch

from src import model


class TaxModelTests(unittest.TestCase):
    def _base_config(self):
        return {
            "simulation": {"start_year": 2026, "end_year": 2026},
            "assumptions": {
                "stock_return": 0.0,
                "bond_return": 0.0,
                "inflation": 0.0,
                "equity_allocation": 0.0,
                "effective_tax_rate_pre_retirement": 0.22,
                "effective_tax_rate_post_retirement": 0.15,
                "taxable_withdrawal_taxable_fraction": 0.50,
                "trad_ira_withdrawal_taxable_fraction": 1.0,
            },
            "taxes": {
                "enabled": True,
                "pre_retirement_filing_status": "married_joint",
                "retirement_filing_status": "married_joint",
                "survivor_filing_status": "single",
                "standard_deduction": {
                    "single": 0.0,
                    "married_joint": 0.0,
                    "head_of_household": 0.0,
                },
                "brackets": {
                    "single": [
                        {"up_to": 10.0, "rate": 0.10},
                        {"rate": 0.20},
                    ],
                    "married_joint": [
                        {"up_to": 10.0, "rate": 0.10},
                        {"rate": 0.20},
                    ],
                    "head_of_household": [
                        {"up_to": 10.0, "rate": 0.10},
                        {"rate": 0.20},
                    ],
                },
            },
            "matthew": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_ira_contribution": 0.0,
            },
            "weny": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_ira_contribution": 0.0,
            },
            "spending": {
                "retirement_annual": 0.0,
                "survivor_annual": 0.0,
            },
            "withdrawal_policy": {
                "accumulation_cash_target": 0.0,
                "retirement_cash_target": 0.0,
                "survivor_cash_target": 0.0,
                "accumulation_withdrawal_order": [
                    "cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"
                ],
                "retirement_withdrawal_order": [
                    "cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"
                ],
                "survivor_withdrawal_order": [
                    "cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"
                ],
            },
            "events": [],
            "liabilities": [],
        }

    def test_progressive_tax_respects_standard_deduction_and_brackets(self):
        tax = model.calculate_progressive_tax(
            taxable_income=50_000.0,
            standard_deduction=30_000.0,
            brackets=[
                {"up_to": 20_000.0, "rate": 0.10},
                {"up_to": 50_000.0, "rate": 0.20},
                {"rate": 0.30},
            ],
        )
        self.assertEqual(tax, 2_000.0)

    def test_run_projection_uses_bracket_tax_for_social_security(self):
        config = self._base_config()
        config["events"] = [
            {
                "enabled": True,
                "type": "SocialSecurity",
                "label": "SS Begins (M)",
                "person": "matthew",
                "year": 2026,
                "monthly_benefit": 2.0,
                "taxable_fraction": 0.50,
            }
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 12.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 1.4, places=2)

    def test_run_projection_uses_bracket_tax_for_trad_ira_withdrawals(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 30.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 100.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 36.25, delta=0.02)
        self.assertAlmostEqual(row["annual_taxes"], 6.25, delta=0.02)
        self.assertAlmostEqual(row["trad_ira"], 63.75, delta=0.02)


if __name__ == "__main__":
    unittest.main()
