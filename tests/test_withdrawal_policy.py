import unittest
from unittest.mock import patch

from src import model


class WithdrawalPolicyTests(unittest.TestCase):
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
            "matthew": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "weny": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {
                "retirement_annual": 0,
                "survivor_annual": 0,
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
            "events": [
                {"enabled": True, "type": "Retire", "label": "Retirement (M)", "person": "matthew", "year": 2026},
                {"enabled": True, "type": "Retire", "label": "Retirement (W)", "person": "weny", "year": 2026},
            ],
            "liabilities": [],
        }

    def test_retirement_deficit_preserves_cash_target_before_tapping_taxable(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 40.0
        config["withdrawal_policy"]["retirement_cash_target"] = 80.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 100.0, "taxable": 50.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 80.0)
        self.assertEqual(row["taxable"], 30.0)

    def test_retirement_withdrawal_order_can_prioritize_trad_ira_before_taxable(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 60.0
        config["withdrawal_policy"]["retirement_withdrawal_order"] = [
            "cash_above_target", "trad_ira", "taxable", "roth", "cash_below_target"
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 50.0, "trad_ira": 50.0, "roth": 50.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["trad_ira"], 0.0)
        self.assertEqual(row["taxable"], 40.0)
        self.assertEqual(row["roth"], 50.0)

    def test_surplus_refills_cash_target_before_investing_remainder(self):
        config = self._base_config()
        config["withdrawal_policy"]["retirement_cash_target"] = 50.0
        config["events"].append(
            {
                "enabled": True,
                "type": "Income",
                "label": "Side Income",
                "year": 2026,
                "amount": 40.0,
                "taxable": False,
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 20.0, "taxable": 80.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 50.0)
        self.assertEqual(row["taxable"], 90.0)


if __name__ == "__main__":
    unittest.main()
