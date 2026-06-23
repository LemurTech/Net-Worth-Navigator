import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import charts, model, tables


class SimulationModeTests(unittest.TestCase):
    def _base_config(self, mode="deterministic"):
        return {
            "simulation": {
                "start_year": 2026,
                "end_year": 2028,
                "mode": mode,
                "num_runs": 12,
                "seed": 12345,
                "portfolio_return_volatility": 0.10,
            },
            "monte_carlo": {
                "success": {
                    "failure_mode": "liquid_depletion",
                    "minimum_spending_funded_ratio": 1.0,
                    "allow_home_equity_for_spending": False,
                    "allow_debt_for_spending": False,
                    "failure_grace_period_months": 0,
                }
            },
            "assumptions": {
                "stock_return": 0.07,
                "bond_return": 0.03,
                "equity_allocation": 0.60,
                "inflation": 0.02,
                "cash_return": 0.01,
                "effective_tax_rate_pre_retirement": 0.0,
                "effective_tax_rate_post_retirement": 0.0,
                "taxable_withdrawal_taxable_fraction": 0.5,
                "trad_ira_withdrawal_taxable_fraction": 1.0,
            },
            "spending": {
                "retirement_annual": 10.0,
                "survivor_percent_of_retirement": 0.70,
                "spending_basis": "nominal",
            },
            "withdrawal_policy": {},
            "taxes": {"enabled": False},
            "liabilities": [],
            "events": [
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (M)", "person": "person1", "year": 2060},
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (W)", "person": "person2", "year": 2062},
                {"enabled": True, "type": "Retire", "label": "Retirement (M)", "person": "person1", "year": 2027},
            ],
            "person1": {
                "name": "Person 1",
                "dob": "1967-04-23",
                "life_expectancy": 93,
                "retirement_year": 2027,
                "annual_take_home": 0.0,
                "ss_start_age": 70,
            },
            "person2": {
                "name": "Person 2",
                "dob": "1976-10-02",
                "life_expectancy": 86,
                "retirement_year": 2028,
                "annual_take_home": 0.0,
                "ss_start_age": 70,
            },
        }

    def test_run_projection_result_monte_carlo_returns_band_data(self):
        config = self._base_config(mode="monte_carlo")
        result = model.run_projection_result(
            balances={"cash": 500.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        self.assertEqual(result.mode, "monte_carlo")
        self.assertEqual(result.run_count, 12)
        self.assertEqual(result.display_path_kind, "median")
        self.assertIsNotNone(result.band_df)
        self.assertIsNotNone(result.outcomes_df)
        self.assertIn("total_net_worth_p10", result.band_df.columns)
        self.assertIn("success_through_year_rate", result.outcomes_df.columns)
        self.assertIn("current_failure_trigger_rate", result.outcomes_df.columns)
        self.assertIn("temporary_pressure_rate", result.outcomes_df.columns)
        self.assertIn("success_rate", result.summary)
        self.assertEqual(result.summary["failure_mode"], "liquid_depletion")
        self.assertIn("probability_of_success", result.summary)
        self.assertIn("probability_of_spending_shortfall", result.summary)
        self.assertIn("probability_of_liquid_depletion", result.summary)
        self.assertIn("probability_of_net_worth_below_zero", result.summary)
        self.assertIn("probability_of_home_equity_required", result.summary)
        self.assertIn("median_terminal_net_worth", result.summary)
        self.assertIn("median_terminal_liquid_net_worth", result.summary)
        self.assertIn("worst_decile_terminal_net_worth", result.summary)
        self.assertIn("first_failure_period_distribution", result.summary)

    def test_build_chart_renders_monte_carlo_copy(self):
        config = self._base_config(mode="monte_carlo")
        result = model.run_projection_result(
            balances={"cash": 500.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "projection.html"
            charts.build_chart(result, out, config=config)
            html = out.read_text(encoding="utf-8")

        self.assertIn("Probability of Success", html)
        self.assertIn("Probability of Spending Shortfall", html)
        self.assertIn("Worst-Decile Terminal Net Worth", html)
        self.assertIn("P10-P90 range", html)
        self.assertIn("Simulation results", html)
        self.assertIn("Outcome Timing", html)
        self.assertIn("Success through year", html)
        self.assertIn("Temporary pressure only", html)
        self.assertIn("Projected Investment Portfolio Range", html)

    def test_scenario_parameters_include_simulation_controls(self):
        config = self._base_config(mode="monte_carlo")
        result = model.run_projection_result(
            balances={"cash": 500.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        html = tables.build_scenario_parameters_summary(
            config,
            projection_df=result.yearly_df,
            projection_result=result,
        )
        self.assertIn("Simulation mode", html)
        self.assertIn("Simulation runs", html)
        self.assertIn("Portfolio return volatility", html)
        self.assertIn("Simulation results", html)
        self.assertIn("Stochastic success rules", html)
        self.assertIn("Probability of Liquid Depletion", html)
        self.assertIn("Probability of Home Equity Required", html)
        self.assertIn("First failure period distribution", html)

    def test_spending_shortfall_failure_mode_is_configurable(self):
        config = self._base_config(mode="monte_carlo")
        config["spending"]["retirement_annual"] = 5_000.0
        config["spending"]["pre_retirement_spending"] = 5_000.0
        config["monte_carlo"]["success"]["failure_mode"] = "spending_shortfall"
        result = model.run_projection_result(
            balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        self.assertEqual(result.summary["success_rate"], 0.0)
        self.assertEqual(result.summary["first_failure_year_p50"], 2026)
        self.assertEqual(result.summary["probability_of_spending_shortfall"], 1.0)

    def test_home_equity_required_probability_uses_spending_rescue_semantics(self):
        config = self._base_config(mode="monte_carlo")
        config["simulation"]["num_runs"] = 4
        config["simulation"]["portfolio_return_volatility"] = 0.0
        config["spending"]["retirement_annual"] = 100.0
        config["spending"]["pre_retirement_spending"] = 100.0
        result = model.run_projection_result(
            balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=250.0,
            liability_balances={},
            config=config,
        )

        self.assertEqual(result.summary["probability_of_home_equity_required"], 1.0)
        self.assertEqual(result.summary["probability_of_spending_shortfall"], 1.0)

    def test_spending_shortfall_grace_distinguishes_pressure_from_actual_failure(self):
        config = self._base_config(mode="monte_carlo")
        config["simulation"]["num_runs"] = 4
        config["simulation"]["portfolio_return_volatility"] = 0.0
        config["spending"]["retirement_annual"] = 100.0
        config["spending"]["pre_retirement_spending"] = 100.0
        config["monte_carlo"]["success"]["failure_mode"] = "spending_shortfall"
        config["monte_carlo"]["success"]["failure_grace_period_months"] = 6
        result = model.run_projection_result(
            balances={"cash": 60.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        outcomes = result.outcomes_df.set_index("year")
        self.assertEqual(result.summary["first_failure_year_p50"], 2027)
        self.assertGreater(outcomes.loc[2026, "current_failure_trigger_rate"], 0.0)
        self.assertGreater(outcomes.loc[2026, "temporary_pressure_rate"], 0.0)
        self.assertEqual(outcomes.loc[2026, "first_failure_in_year_rate"], 0.0)
        self.assertEqual(outcomes.loc[2027, "temporary_pressure_rate"], 0.0)
        self.assertGreater(outcomes.loc[2027, "first_failure_in_year_rate"], 0.0)

    def test_historical_mode_uses_rolling_windows_from_csv(self):
        config = self._base_config(mode="historical")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "returns.csv"
            pd.DataFrame(
                [
                    {"year": 2000, "return": 0.10},
                    {"year": 2001, "return": -0.05},
                    {"year": 2002, "return": 0.08},
                    {"year": 2003, "return": 0.04},
                    {"year": 2004, "return": 0.12},
                ]
            ).to_csv(csv_path, index=False)
            config["simulation"]["historical_returns_path"] = str(csv_path)
            result = model.run_projection_result(
                balances={"cash": 500.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
                config=config,
            )

        self.assertEqual(result.mode, "historical")
        self.assertEqual(result.run_count, 3)
        self.assertEqual(result.summary["run_labels"], ["2000-2002", "2001-2003", "2002-2004"])
        self.assertIn("total_net_worth_p50", result.band_df.columns)

    def test_historical_mode_accepts_bundled_dataset_path(self):
        config = self._base_config(mode="historical")
        config["simulation"]["historical_returns_path"] = "config/return_sequences/us_balanced_returns.csv"
        result = model.run_projection_result(
            balances={"cash": 500.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
            home_value=0.0,
            liability_balances={},
            config=config,
        )

        self.assertEqual(result.mode, "historical")
        self.assertGreater(result.run_count, 1)
        self.assertEqual(result.summary["run_labels"][0], "1970-1972")


if __name__ == "__main__":
    unittest.main()
