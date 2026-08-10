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

[simulation]
start_year = 2026
end_year = 2060

[assumptions]
stock_return = 0.07
bond_return = 0.03
inflation = 0.025

[spending]
retirement_annual = 60000
spending_basis = "real"

[taxes]
enabled = true
table_set = "2025_us_federal_oregon"
pre_retirement_filing_status = "married_joint"

[taxes.rmd]
enabled = true
start_age = 73

[person1]
name = "Alex"
dob = "1975-01-01"
annual_take_home = 62000

[[events]]
enabled = true
type = "SpendingShift"
label = "Downsize"
start_year = 2040
mode = "replace"
survivor_annual = 45000
"""


def _fake_backup_and_write(config_path):
    def _write(doc, scenario_slug=None):
        config_path.write_text(doc.as_string(), encoding="utf-8")
        return config_path
    return _write


class QuickControlMapTests(unittest.TestCase):
    def test_cash_target_help_defines_phases_and_marks_survivor_as_couple_only(self):
        template = (Path(__file__).resolve().parents[1] / "templates" / "setup_panel.html").read_text(encoding="utf-8")
        self.assertIn('id="cash-survivor-field"', template)
        self.assertIn('class="inline-field person2-toggle-section"', template)
        self.assertIn('class="synth-hint" style="max-width:none;margin-top:8px">Accumulation applies', template)
        self.assertIn(
            "Accumulation applies while either partner is still working. Retirement applies once both partners are retired. "
            "Survivor applies after one partner dies; it is ignored for a single-person household and is hidden above.",
            template,
        )

    def test_advanced_settings_fields_registered(self):
        expected = {
            "spending_retirement_annual": ("spending.retirement_annual", float),
            "spending_survivor_percent": ("spending.survivor_percent_of_retirement", float),
            "spending_survivor_annual": ("spending.survivor_annual", float),
            "spending_basis": ("spending.spending_basis", str),
            "taxes_enabled_flag": ("taxes.enabled", bool),
            "taxes_pre_retirement_filing_status": ("taxes.pre_retirement_filing_status", str),
            "taxes_retirement_filing_status": ("taxes.retirement_filing_status", str),
            "taxes_survivor_filing_status": ("taxes.survivor_filing_status", str),
            "taxes_wage_tax_treatment": ("taxes.wage_tax_treatment", str),
            "rmd_enabled_flag": ("taxes.rmd.enabled", bool),
            "rmd_start_age": ("taxes.rmd.start_age", int),
            "assump_cash_return": ("assumptions.cash_return", float),
            "assump_real_estate_appreciation": ("assumptions.real_estate_appreciation", float),
            "assump_real_estate_sale_fee_rate": ("assumptions.real_estate_sale_fee_rate", float),
            "assump_effective_tax_rate_pre_retirement": ("assumptions.effective_tax_rate_pre_retirement", float),
            "assump_effective_tax_rate_post_retirement": ("assumptions.effective_tax_rate_post_retirement", float),
            "assump_taxable_withdrawal_taxable_fraction": ("assumptions.taxable_withdrawal_taxable_fraction", float),
            "assump_trad_ira_withdrawal_taxable_fraction": ("assumptions.trad_ira_withdrawal_taxable_fraction", float),
            "assump_initial_taxable_cost_basis_fraction": ("assumptions.initial_taxable_cost_basis_fraction", float),
            "assump_initial_roth_contribution_basis_fraction": ("assumptions.initial_roth_contribution_basis_fraction", float),
        }
        for field_name, spec in expected.items():
            self.assertEqual(admin_app._QUICK_CONTROL_MAP[field_name], spec)


class SaveQuickControlsAdvancedFieldsTests(unittest.TestCase):
    def test_single_household_ignores_survivor_cash_target(self):
        single_toml = SAMPLE_TOML.replace('slug = "test"', 'slug = "test"\nhousehold_type = "single"')
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(single_toml, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(_FakeRequest(json_body={
                    "cash_target_accumulation": 25000.0,
                    "cash_target_survivor": 10000.0,
                })))

            self.assertTrue(json.loads(response.body)["ok"])
            policy = tomllib.loads(config_path.read_text(encoding="utf-8"))["withdrawal_policy"]
            self.assertEqual(policy["accumulation_cash_target"], 25000.0)
            self.assertNotIn("survivor_cash_target", policy)

    def test_saves_taxes_rmd_spending_and_assumptions_without_cross_contamination(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            body = {
                "spending_retirement_annual": 65000.0,
                "spending_survivor_percent": 0.75,
                "taxes_enabled_flag": False,
                "taxes_retirement_filing_status": "single",
                "rmd_enabled_flag": True,
                "rmd_start_age": 75,
                "assump_cash_return": 0.02,
                "assump_taxable_withdrawal_taxable_fraction": 0.60,
            }

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_quick_controls(_FakeRequest(json_body=body)))

            result = json.loads(response.body)
            self.assertTrue(result["ok"])

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["spending"]["retirement_annual"], 65000.0)
            self.assertEqual(parsed["spending"]["survivor_percent_of_retirement"], 0.75)
            # [taxes].enabled must be updated, not [taxes.rmd].enabled or the
            # SpendingShift event's own enabled flag -- this is the collision
            # the bounded section/person extraction exists to avoid.
            self.assertIs(parsed["taxes"]["enabled"], False)
            self.assertEqual(parsed["taxes"]["retirement_filing_status"], "single")
            self.assertIs(parsed["taxes"]["rmd"]["enabled"], True)
            self.assertEqual(parsed["taxes"]["rmd"]["start_age"], 75)
            self.assertEqual(parsed["assumptions"]["cash_return"], 0.02)
            self.assertEqual(parsed["assumptions"]["taxable_withdrawal_taxable_fraction"], 0.60)
            # The SpendingShift event's own survivor_annual/enabled must be untouched.
            spending_shift = parsed["events"][0]
            self.assertEqual(spending_shift["survivor_annual"], 45000)
            self.assertIs(spending_shift["enabled"], True)
