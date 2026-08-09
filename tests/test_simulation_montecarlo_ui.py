import asyncio
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import admin_app


class _FakeRequest:
    """Minimal stand-in for starlette.Request -- admin_app's handlers only
    touch .query_params.get(...) and (for POST) await .json()."""

    def __init__(self, query_params=None, json_body=None):
        self.query_params = query_params or {}
        self._json_body = json_body

    async def json(self):
        return self._json_body


SAMPLE_TOML = """[scenario]
name = "Test"
slug = "test"

[data_source]
mode = "synthetic"

[simulation]
start_year = 2026
end_year = 2060
render_modes = ["deterministic"]
mode = "deterministic"

[monte_carlo.success]
failure_mode = "liquid_depletion"
minimum_spending_funded_ratio = 1.0
allow_home_equity_for_spending = false
allow_debt_for_spending = false
failure_grace_period_months = 0

[person1]
name = "Alex"
dob = "1975-01-01"
"""


def _fake_backup_and_write(config_path):
    def _write(doc, scenario_slug=None):
        config_path.write_text(doc.as_string(), encoding="utf-8")
        return config_path
    return _write


class QuickControlMapTests(unittest.TestCase):
    def test_simulation_and_monte_carlo_fields_registered(self):
        expected = {
            "sim_num_runs": ("simulation.num_runs", int),
            "sim_seed": ("simulation.seed", int),
            "sim_portfolio_return_volatility": ("simulation.portfolio_return_volatility", float),
            "sim_historical_returns_path": ("simulation.historical_returns_path", str),
            "mc_failure_mode": ("monte_carlo.success.failure_mode", str),
            "mc_minimum_spending_funded_ratio": ("monte_carlo.success.minimum_spending_funded_ratio", float),
            "mc_allow_home_equity_for_spending": ("monte_carlo.success.allow_home_equity_for_spending", bool),
            "mc_allow_debt_for_spending": ("monte_carlo.success.allow_debt_for_spending", bool),
            "mc_failure_grace_period_months": ("monte_carlo.success.failure_grace_period_months", float),
            "mc_custom_failure_column": ("monte_carlo.success.custom_failure_column", str),
            "mc_custom_failure_operator": ("monte_carlo.success.custom_failure_operator", str),
            "mc_custom_failure_threshold": ("monte_carlo.success.custom_failure_threshold", float),
        }
        for field_name, spec in expected.items():
            self.assertEqual(admin_app._QUICK_CONTROL_MAP[field_name], spec)

    def test_render_modes_registered_as_array_field(self):
        self.assertEqual(admin_app._QUICK_ARRAY_MAP["render_modes"], "simulation.render_modes")


class SaveQuickControlsSimulationFieldsTests(unittest.TestCase):
    def test_saves_simulation_and_monte_carlo_settings_without_cross_contamination(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            body = {
                "render_modes": ["deterministic", "historical", "monte_carlo"],
                "sim_num_runs": 500,
                "sim_seed": 42,
                "sim_portfolio_return_volatility": 0.18,
                "sim_historical_returns_path": "config/return_sequences/us_balanced_returns.csv",
                "mc_failure_mode": "spending_shortfall",
                "mc_minimum_spending_funded_ratio": 0.90,
                "mc_allow_home_equity_for_spending": True,
                "mc_failure_grace_period_months": 6,
            }

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(_FakeRequest(json_body=body)))

            result = json.loads(response.body)
            self.assertTrue(result["ok"])

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["simulation"]["render_modes"], ["deterministic", "historical", "monte_carlo"])
            self.assertEqual(parsed["simulation"]["num_runs"], 500)
            self.assertEqual(parsed["simulation"]["seed"], 42)
            self.assertEqual(parsed["simulation"]["portfolio_return_volatility"], 0.18)
            self.assertEqual(
                parsed["simulation"]["historical_returns_path"],
                "config/return_sequences/us_balanced_returns.csv",
            )
            # [simulation].mode (the compatibility single-run field, overridden
            # per render pass by run.py) must be untouched by this save --
            # nothing in the UI writes it directly.
            self.assertEqual(parsed["simulation"]["mode"], "deterministic")
            # [data_source].mode must be untouched -- a bare "mode" lookup
            # bounded incorrectly could bleed across sections.
            self.assertEqual(parsed["data_source"]["mode"], "synthetic")

            self.assertEqual(parsed["monte_carlo"]["success"]["failure_mode"], "spending_shortfall")
            self.assertEqual(parsed["monte_carlo"]["success"]["minimum_spending_funded_ratio"], 0.90)
            self.assertIs(parsed["monte_carlo"]["success"]["allow_home_equity_for_spending"], True)
            self.assertEqual(parsed["monte_carlo"]["success"]["failure_grace_period_months"], 6.0)
            # allow_debt_for_spending was not in this request body -- must be
            # left at its prior value, not clobbered to a default.
            self.assertIs(parsed["monte_carlo"]["success"]["allow_debt_for_spending"], False)


class ReturnSequencesEndpointTests(unittest.TestCase):
    def test_lists_bundled_historical_return_sequence_csvs(self):
        response = asyncio.run(admin_app.api_return_sequences())
        result = json.loads(response.body)
        self.assertTrue(result["ok"])
        paths = [s["path"] for s in result["sequences"]]
        self.assertIn("config/return_sequences/us_balanced_returns.csv", paths)
        entry = next(s for s in result["sequences"] if s["path"] == "config/return_sequences/us_balanced_returns.csv")
        self.assertGreater(entry["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
