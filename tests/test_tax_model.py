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
                "initial_taxable_cost_basis_fraction": 0.5,
                "initial_roth_contribution_basis_fraction": 1.0,
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0.0,
                "annual_take_home_real_raise": 0.0,
                "annual_401k_contribution": 0.0,
                "annual_401k_contribution_extra_increase": 0.0,
                "annual_ira_contribution": 0.0,
            },
            "person2": {
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
                "person": "person1",
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
        self.assertAlmostEqual(row["other_taxable_income"], 36.25, delta=0.02)
        self.assertAlmostEqual(row["federal_taxable_after_deduction"], 36.25, delta=0.02)
        self.assertAlmostEqual(row["annual_taxes"], 6.25, delta=0.02)
        self.assertAlmostEqual(row["federal_effective_rate"], 6.25 / 36.25, delta=0.0001)
        self.assertAlmostEqual(row["trad_ira"], 63.75, delta=0.02)

    def test_taxable_withdrawals_tax_only_realized_gain_portion(self):
        config = self._base_config()
        config["taxes"]["enabled"] = False
        config["assumptions"]["effective_tax_rate_post_retirement"] = 0.0
        config["assumptions"]["initial_taxable_cost_basis_fraction"] = 0.8
        config["spending"]["retirement_annual"] = 50.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 100.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["withdrawal_taxable"], 50.0, places=2)
        self.assertAlmostEqual(row["withdrawal_taxable_income"], 10.0, places=2)
        self.assertAlmostEqual(row["taxable_withdrawal_basis_portion"], 40.0, places=2)
        self.assertAlmostEqual(row["taxable_withdrawal_gain_portion"], 10.0, places=2)
        self.assertAlmostEqual(row["taxable"], 50.0, places=2)
        self.assertAlmostEqual(row["taxable_cost_basis"], 40.0, places=2)
        self.assertAlmostEqual(row["taxable_unrealized_gain"], 10.0, places=2)

    def test_roth_withdrawals_deplete_contribution_basis_before_earnings(self):
        config = self._base_config()
        config["taxes"]["enabled"] = False
        config["assumptions"]["effective_tax_rate_post_retirement"] = 0.0
        config["assumptions"]["initial_roth_contribution_basis_fraction"] = 0.6
        config["spending"]["retirement_annual"] = 50.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 100.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertAlmostEqual(row["withdrawal_roth"], 50.0, places=2)
        self.assertAlmostEqual(row["roth_withdrawal_basis_portion"], 30.0, places=2)
        self.assertAlmostEqual(row["roth_withdrawal_earnings_portion"], 20.0, places=2)
        self.assertAlmostEqual(row["roth"], 50.0, places=2)
        self.assertAlmostEqual(row["roth_contribution_basis"], 30.0, places=2)
        self.assertAlmostEqual(row["roth_earnings"], 20.0, places=2)

    def test_social_security_uses_provisional_income_thresholds(self):
        config = self._base_config()
        config["events"] = [
            {
                "enabled": True,
                "type": "SocialSecurity",
                "label": "SS Begins (M)",
                "person": "person1",
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
        self.assertAlmostEqual(row["taxable_social_security_income"], 12_000.0, places=2)
        self.assertAlmostEqual(row["social_security_taxable_fraction"], 0.5, places=4)
        self.assertAlmostEqual(row["social_security_provisional_income"], 37_000.0, places=2)
        self.assertAlmostEqual(row["annual_taxes"], 7_399.0, places=2)

    def test_cashflow_table_relabels_modeled_tax_scope(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "person1_income": 0.0,
                "person2_income": 0.0,
                "freed_payments": 0.0,
                "annual_spend": 0.0,
                "annual_taxes": 1250.0,
                "annual_federal_taxes": 1000.0,
                "annual_state_taxes": 250.0,
                "net_flow": -1250.0,
                "event_items": [],
            }
        ])
        html = tables.build_cashflow_table(df)
        self.assertIn("Federal ordinary-income tax", html)
        self.assertIn("State income tax", html)
        self.assertIn("Modeled tax on retirement/event inflows", html)
        self.assertNotIn(">Estimated taxes<", html)

    def test_tax_table_surfaces_yearly_tax_audit_components(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "tax_phase": "retirement",
                "tax_mode": "brackets",
                "tax_filing_status": "married_joint",
                "state_tax_name": "oregon",
                "state_tax_filing_status": "married_joint",
                "taxable_income": 50000.0,
                "taxable_wage_income": 0.0,
                "non_ss_taxable_income": 35000.0,
                "withdrawal_taxable_income": 10000.0,
                "taxable_withdrawal_basis_portion": 15000.0,
                "taxable_withdrawal_gain_portion": 10000.0,
                "roth_withdrawal_basis_portion": 4000.0,
                "roth_withdrawal_earnings_portion": 1000.0,
                "other_taxable_income": 35000.0,
                "social_security_provisional_income": 47000.0,
                "taxable_social_security_income": 5000.0,
                "social_security_taxable_fraction": 0.5,
                "federal_standard_deduction": 30000.0,
                "federal_taxable_after_deduction": 20000.0,
                "annual_federal_taxes": 2200.0,
                "federal_effective_rate": 0.11,
                "state_standard_deduction": 5670.0,
                "state_taxable_before_deduction": 50000.0,
                "state_taxable_income": 44330.0,
                "annual_state_taxes": 1800.0,
                "state_effective_rate": 0.0406,
                "annual_taxes": 4000.0,
            }
        ])
        html = tables.build_tax_table(df)
        self.assertIn("Tax Item", html)
        self.assertIn("Taxable Income Components", html)
        self.assertIn("Taxable withdrawal realized gains", html)
        self.assertIn("Roth withdrawal earnings", html)
        self.assertIn("Social Security taxable fraction", html)
        self.assertIn("Federal taxable after deduction", html)
        self.assertIn("State taxable before deduction", html)
        self.assertIn("Total modeled taxes", html)
        self.assertIn("married_joint", html)
        self.assertIn("50%", html)
        self.assertIn("11%", html)

    def test_build_chart_includes_tax_tab(self):
        config = {
            "display": {"projection_title": "Casa Lemuria"},
            "person1": {"name": "Person 1", "dob": "1967-04-23"},
            "person2": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [],
            "simulation": {"start_year": 2026, "end_year": 2026},
        }
        df = pd.DataFrame([
            {
                "year": 2026,
                "home_value": 0.0,
                "mortgage": 0.0,
                "home_equity": 0.0,
                "cash": 100.0,
                "taxable": 0.0,
                "trad_ira": 0.0,
                "roth": 0.0,
                "total_net_worth": 100.0,
                "survivor": False,
                "events_active": "",
                "person1_income": 0.0,
                "person2_income": 0.0,
                "freed_payments": 0.0,
                "annual_spend": 0.0,
                "annual_taxes": 0.0,
                "annual_federal_taxes": 0.0,
                "annual_state_taxes": 0.0,
                "net_flow": 0.0,
                "event_items": [],
                "taxable_income": 0.0,
                "tax_phase": "retirement",
                "tax_mode": "brackets",
                "tax_filing_status": "married_joint",
            },
        ])

        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / "nwn-tax-tab-test.html"
                        charts.build_chart(df, out)
                        html = out.read_text(encoding="utf-8")

        self.assertIn("btn-tax", html)
        self.assertIn("panel-tax", html)
        self.assertIn(">Tax</button>", html)
        self.assertIn(">Definitions</a>", html)

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
        config["person1"]["dob"] = "1940-01-01"
        config["person2"]["dob"] = "1980-01-01"
        config["person1"]["rmd_trad_ira_share"] = 1.0
        config["person2"]["rmd_trad_ira_share"] = 0.0
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
        config["person1"]["dob"] = "1940-01-01"
        config["person2"]["dob"] = "1980-01-01"
        config["person1"]["rmd_trad_ira_share"] = 1.0
        config["person2"]["rmd_trad_ira_share"] = 0.0
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
            "person1": {"name": "Person 1", "dob": "1967-04-23"},
            "person2": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [],
            "simulation": {"start_year": 2026, "end_year": 2026},
        }
        df = pd.DataFrame([
            {"year": 2026, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0,
             "total_net_worth": 100.0, "survivor": False, "events_active": "", "person1_income": 0.0, "person2_income": 0.0,
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
