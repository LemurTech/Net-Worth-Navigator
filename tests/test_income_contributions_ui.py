import asyncio
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import admin_app

from src.scenarios import ScenarioRef


def _patch_scenario(config_path):
    """Resolve every scenario lookup (config path, read-only guard, default
    fallback, backup dir) to a temp scenario file - hermetic in CI."""
    fake = ScenarioRef(
        slug="test", name="Test", description="", config_path=config_path, is_default=False,
    )
    return patch("admin_app._current_scenario", return_value=fake)


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

[simulation]
start_year = 2026
end_year = 2060

[assumptions]
stock_return = 0.07
bond_return = 0.03
inflation = 0.025

[spending]
retirement_annual = 60000

[person1]
name = "Alex"
dob = "1975-01-01"
annual_take_home = 62000
"""


def _fake_backup_and_write(config_path):
    def _write(doc, scenario_slug=None):
        config_path.write_text(doc.as_string(), encoding="utf-8")
        return config_path
    return _write


class QuickControlMapTests(unittest.TestCase):
    def test_roth_ownership_help_explains_the_fallback_and_account_override(self):
        template = (Path(__file__).resolve().parents[1] / "templates" / "setup_panel.html").read_text(encoding="utf-8")
        expected_help = (
            "Used when Roth accounts have no owner assignment: splits the pooled opening Roth balance between people "
            "and attributes shared Roth flows. Account-level owner assignments override this."
        )
        self.assertEqual(template.count(expected_help), 2)

    def test_percent_of_gross_controls_have_help_for_growth_and_rate_semantics(self):
        template = (Path(__file__).resolve().parents[1] / "templates" / "setup_panel.html").read_text(encoding="utf-8")
        for expected_help in (
            "Annual growth rate for gross income used in contribution math.",
            "Starting share of gross income contributed to the retirement plan.",
            "Annual increase in the contribution rate, measured in percentage points.",
        ):
            self.assertEqual(template.count(expected_help), 2)

    def test_income_contribution_fields_registered_for_both_persons(self):
        expected_suffixes_and_types = [
            ("annual_take_home", float),
            ("annual_take_home_real_raise", float),
            ("annual_take_home_is_net_of_retirement_contributions", bool),
            ("contribution_method", str),
            ("annual_401k_contribution", float),
            ("annual_401k_contribution_extra_increase", float),
            ("gross_income", float),
            ("gross_income_annual_increase_percent", float),
            ("retirement_contribution_percent", float),
            ("retirement_contribution_annual_increase_percent", float),
            ("retirement_contribution_max_percent", float),
            ("annual_401k_employer_match_mode", str),
            ("annual_401k_employer_match", float),
            ("annual_401k_employer_match_rate", float),
            ("annual_401k_employer_match_max_percent", float),
            ("annual_ira_contribution", float),
            ("annual_401k_contribution_bucket", str),
            ("annual_ira_contribution_bucket", str),
            ("rmd_trad_ira_share", float),
            ("roth_share", float),
        ]
        for person_key in ("person1", "person2"):
            for suffix, expected_type in expected_suffixes_and_types:
                field_name = f"{person_key}_{suffix}"
                self.assertIn(field_name, admin_app._QUICK_CONTROL_MAP)
                toml_path, actual_type = admin_app._QUICK_CONTROL_MAP[field_name]
                self.assertEqual(toml_path, f"{person_key}.{suffix}")
                self.assertIs(actual_type, expected_type)

    def test_401k_split_fields_map_to_nested_toml_path(self):
        self.assertEqual(
            admin_app._QUICK_CONTROL_MAP["person1_401k_split_trad_ira"],
            ("person1.annual_401k_contribution_split.trad_ira", float),
        )
        self.assertEqual(
            admin_app._QUICK_CONTROL_MAP["person2_401k_split_roth"],
            ("person2.annual_401k_contribution_split.roth", float),
        )


class SaveQuickControlsIncomeFieldsTests(unittest.TestCase):
    def test_single_household_ignores_person2_payload_without_creating_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(
                SAMPLE_TOML.replace('slug = "test"', 'slug = "test"\nhousehold_type = "single"'),
                encoding="utf-8",
            )

            body = {
                "household_type": "single",
                "person1_annual_take_home": 65000.0,
                "person2_name": "Dummy Person",
                "person2_annual_take_home": 50000.0,
                "person2_annual_take_home_is_net_of_retirement_contributions": False,
                "person2_contribution_method": "flat",
                "person2_birth_year": 1980,
            }
            with _patch_scenario(config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(_FakeRequest(json_body=body)))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["person1"]["annual_take_home"], 65000.0)
            self.assertNotIn("person2", parsed)

    def test_saves_dollar_percent_bool_and_select_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            body = {
                "person1_annual_take_home": 65000.0,
                "person1_annual_take_home_real_raise": 0.01,
                "person1_annual_take_home_is_net_of_retirement_contributions": True,
                "person1_contribution_method": "percent_of_gross",
                "person1_gross_income": 90000.0,
                "person1_retirement_contribution_percent": 0.20,
                "person1_retirement_contribution_max_percent": 0.30,
                "person1_annual_401k_employer_match_mode": "percent_of_gross",
                "person1_annual_401k_employer_match_rate": 1.0,
                "person1_annual_401k_contribution_bucket": "roth",
                "person1_401k_split_trad_ira": 0.70,
                "person1_401k_split_roth": 0.30,
                "person1_rmd_trad_ira_share": 1.0,
            }

            with _patch_scenario(config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(_FakeRequest(json_body=body)))

            result = json.loads(response.body)
            self.assertTrue(result["ok"])

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            person1 = parsed["person1"]
            self.assertEqual(person1["annual_take_home"], 65000.0)
            self.assertEqual(person1["annual_take_home_real_raise"], 0.01)
            self.assertIs(person1["annual_take_home_is_net_of_retirement_contributions"], True)
            self.assertEqual(person1["contribution_method"], "percent_of_gross")
            self.assertEqual(person1["gross_income"], 90000.0)
            self.assertEqual(person1["retirement_contribution_percent"], 0.20)
            self.assertEqual(person1["retirement_contribution_max_percent"], 0.30)
            self.assertEqual(person1["annual_401k_employer_match_mode"], "percent_of_gross")
            self.assertEqual(person1["annual_401k_employer_match_rate"], 1.0)
            self.assertEqual(person1["annual_401k_contribution_bucket"], "roth")
            self.assertEqual(person1["annual_401k_contribution_split"], {"trad_ira": 0.70, "roth": 0.30})
            self.assertEqual(person1["rmd_trad_ira_share"], 1.0)

    def test_unspecified_fields_are_left_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with _patch_scenario(config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(
                    _FakeRequest(json_body={"person1_gross_income": 100000.0})
                ))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            # Pre-existing field must survive untouched
            self.assertEqual(parsed["person1"]["annual_take_home"], 62000.0)
            self.assertEqual(parsed["person1"]["gross_income"], 100000.0)
