import unittest

from src.tables import build_assumptions_summary


class AssumptionsSummaryTests(unittest.TestCase):
    def test_build_assumptions_summary_renders_current_config_inputs(self):
        config = {
            "matthew": {
                "name": "Person 1",
                "dob": "1967-04-23",
                "life_expectancy": 90,
                "retirement_year": 2034,
                "ss_start_age": 70,
            },
            "weny": {
                "name": "Person 2",
                "dob": "1976-10-02",
                "life_expectancy": 90,
                "retirement_year": 2040,
                "ss_start_age": 67,
            },
            "assumptions": {
                "stock_return": 0.07,
                "bond_return": 0.04,
                "inflation": 0.03,
                "real_estate_appreciation": 0.03,
                "equity_allocation": 0.70,
                "real_estate_sale_fee_rate": 0.06,
            },
            "spending": {
                "retirement_annual": 100000,
                "survivor_annual": 70000,
            },
            "withdrawal_policy": {
                "accumulation_cash_target": 64000,
                "retirement_cash_target": 95000,
                "survivor_cash_target": 66500,
            },
        }

        html = build_assumptions_summary(config)

        self.assertIn("Current planning assumptions", html)
        self.assertIn("Person 1", html)
        self.assertIn("Person 2", html)
        self.assertIn("1967-04-23", html)
        self.assertIn("90 (→ 2057)", html)
        self.assertIn("67 (→ 2034)", html)
        self.assertIn("70 (→ 2037)", html)
        self.assertIn("7%", html)
        self.assertIn("4%", html)
        self.assertIn("3%", html)
        self.assertIn("70%", html)
        self.assertIn("6%", html)
        self.assertIn("$100,000", html)
        self.assertIn("$70,000", html)
        self.assertIn("$64,000", html)
        self.assertIn("$95,000", html)
        self.assertIn("$66,500", html)


if __name__ == "__main__":
    unittest.main()
