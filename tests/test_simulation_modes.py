import tempfile
import unittest
from pathlib import Path

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
        self.assertIn("total_net_worth_p10", result.band_df.columns)
        self.assertIn("success_rate", result.summary)

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

        self.assertIn("Monte Carlo Success Rate", html)
        self.assertIn("P10-P90 range", html)
        self.assertIn("Simulation results", html)
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


if __name__ == "__main__":
    unittest.main()
