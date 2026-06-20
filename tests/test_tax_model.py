import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

import pandas as pd

from src import model, charts, tables


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
                "social_security": {
                    "use_provisional_income": True,
                    "thresholds": {
                        "single": {"base": 25_000.0, "adjusted": 34_000.0},
                        "married_joint": {"base": 32_000.0, "adjusted": 44_000.0},
                        "head_of_household": {"base": 25_000.0, "adjusted": 34_000.0},
                    },
                },
                "state": {
                    "enabled": False,
                    "name": "oregon",
                    "standard_deduction": {
                        "single": 2_835.0,
                        "married_joint": 5_670.0,
                        "head_of_household": 4_560.0,
                    },
                },
            },
            "matthew": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0.0,
                "annual_take_home_real_raise": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_401k_contribution_extra_increase": 0.0,
                "annual_ira_contribution": 0.0,
            },
            "weny": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0.0,
                "annual_take_home_real_raise": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_401k_contribution_extra_increase": 0.0,
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
            }
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 0.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 0.0, places=2)

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

    def test_social_security_uses_provisional_income_thresholds(self):
        config = self._base_config()
        config["events"] = [
            {
                "enabled": True,
                "type": "SocialSecurity",
                "label": "SS Begins (M)",
                "person": "matthew",
                "year": 2026,
                "monthly_benefit": 2_000.0,
            },
            {
                "enabled": True,
                "type": "Income",
                "label": "Taxable side income",
                "year": 2026,
                "amount": 25_000.0,
                "taxable": True,
            },
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 37_000.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 7_399.0, places=2)

    def test_cashflow_table_relabels_modeled_tax_scope(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "matthew_income": 0.0,
                "weny_income": 0.0,
                "freed_payments": 0.0,
                "annual_spend": 0.0,
                "annual_taxes": 1250.0,
                "net_flow": -1250.0,
                "event_items": [],
            }
        ])
        html = tables.build_cashflow_table(df)
        self.assertIn("Modeled tax on retirement/event inflows", html)
        self.assertNotIn(">Estimated taxes<", html)

    def test_oregon_state_tax_uses_table_under_50k(self):
        config = self._base_config()
        config["assumptions"]["effective_tax_rate_pre_retirement"] = 0.0
        config["assumptions"]["effective_tax_rate_post_retirement"] = 0.0
        config["taxes"]["enabled"] = False
        config["taxes"]["state"]["enabled"] = True
        config["events"] = [
            {
                "enabled": True,
                "type": "Income",
                "label": "Taxable side income",
                "year": 2026,
                "amount": 10_000.0,
                "taxable": True,
            }
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 10_000.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 207.0, places=2)

    def test_oregon_state_tax_uses_chart_over_50k(self):
        config = self._base_config()
        config["assumptions"]["effective_tax_rate_pre_retirement"] = 0.0
        config["assumptions"]["effective_tax_rate_post_retirement"] = 0.0
        config["taxes"]["enabled"] = False
        config["taxes"]["state"]["enabled"] = True
        config["events"] = [
            {
                "enabled": True,
                "type": "Income",
                "label": "Taxable side income",
                "year": 2026,
                "amount": 65_670.0,
                "taxable": True,
            }
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["taxable_income"], 65_670.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 4_631.0, places=2)

    def test_rmd_forces_trad_withdrawal_and_taxable_income(self):
        config = self._base_config()
        config["matthew"]["dob"] = "1940-01-01"
        config["weny"]["dob"] = "1980-01-01"
        config["matthew"]["rmd_trad_ira_share"] = 1.0
        config["weny"]["rmd_trad_ira_share"] = 0.0
        config["taxes"]["rmd"] = {"enabled": True, "start_age": 73}

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 152.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["rmd_required"], 10.0, places=2)
        self.assertAlmostEqual(row["rmd_withdrawn"], 10.0, places=2)
        self.assertAlmostEqual(row["withdrawal_trad_ira"], 10.0, places=2)
        self.assertAlmostEqual(row["taxable_income"], 10.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 1.0, places=2)

    def test_rmd_does_not_add_extra_when_voluntary_trad_withdrawals_already_higher(self):
        config = self._base_config()
        config["matthew"]["dob"] = "1940-01-01"
        config["weny"]["dob"] = "1980-01-01"
        config["matthew"]["rmd_trad_ira_share"] = 1.0
        config["weny"]["rmd_trad_ira_share"] = 0.0
        config["taxes"]["enabled"] = False
        config["taxes"]["rmd"] = {"enabled": True, "start_age": 73}
        config["assumptions"]["effective_tax_rate_post_retirement"] = 0.0
        config["assumptions"]["trad_ira_withdrawal_taxable_fraction"] = 0.0
        config["spending"]["retirement_annual"] = 30.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 100.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["rmd_required"], 6.58, places=2)
        self.assertAlmostEqual(row["rmd_withdrawn"], 6.58, places=2)
        self.assertAlmostEqual(row["withdrawal_cash"], 6.58, places=2)
        self.assertAlmostEqual(row["withdrawal_trad_ira"], 23.42, places=2)
        self.assertAlmostEqual(row["withdrawal_cash"] + row["withdrawal_trad_ira"], 30.0, places=2)
        self.assertAlmostEqual(row["trad_ira"], 76.58, places=2)

    def test_build_chart_includes_tax_semantics_note(self):
        config = {
            "display": {"projection_title": "Casa Lemuria"},
            "matthew": {"name": "Person 1", "dob": "1967-04-23"},
            "weny": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [],
            "simulation": {"start_year": 2026, "end_year": 2026},
        }
        df = pd.DataFrame([
            {"year": 2026, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0,
             "total_net_worth": 100.0, "survivor": False, "events_active": "", "matthew_income": 0.0, "weny_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": [], "taxable_income": 0.0},
        ])

        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / "nwn-tax-note-test.html"
                        charts.build_chart(df, out)
                        html = out.read_text(encoding="utf-8")

        self.assertIn("Employment income is currently modeled as net cash", html)
        self.assertIn("taxes shown here cover modeled taxable retirement/event inflows", html)


if __name__ == "__main__":
    unittest.main()
