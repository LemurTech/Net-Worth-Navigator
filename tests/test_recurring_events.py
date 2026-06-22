import unittest
from unittest.mock import patch

import pandas as pd

import run
from src import charts, model, monarch_bridge, tables


class RecurringEventsTests(unittest.TestCase):
    def test_resolve_runtime_config_expands_point_and_span_events(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2035},
            "events": [
                {
                    "enabled": True,
                    "type": "Expense",
                    "label": "Vacation",
                    "year": 2026,
                    "amount": -10000,
                    "expense_kind": "discretionary",
                    "repeat_every_years": 2,
                    "repeat_until_year": 2030,
                    "chart_first_occurrence_only": True,
                },
                {
                    "enabled": True,
                    "type": "Education",
                    "label": "Certification",
                    "person": "person1",
                    "start_year": 2027,
                    "end_year": 2028,
                    "annual_cost": 5000,
                    "repeat_every_years": 3,
                    "repeat_count": 2,
                },
            ],
        }

        resolved = model.resolve_runtime_config(config)
        events = resolved["events"]

        vacation_years = [
            event["year"]
            for event in events
            if event["label"] == "Vacation"
        ]
        self.assertEqual(vacation_years, [2026, 2028, 2030])

        vacation_chart_flags = [
            event.get("_show_chart_label")
            for event in events
            if event["label"] == "Vacation"
        ]
        self.assertEqual(vacation_chart_flags, [True, False, False])

        vacation_kinds = [
            event.get("expense_kind")
            for event in events
            if event["label"] == "Vacation"
        ]
        self.assertEqual(vacation_kinds, ["discretionary", "discretionary", "discretionary"])

        certification_spans = [
            (event["start_year"], event["end_year"])
            for event in events
            if event["label"] == "Certification"
        ]
        self.assertEqual(certification_spans, [(2027, 2028), (2030, 2031)])

    def test_run_projection_uses_retirement_and_discretionary_icons_and_item_metadata(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2028},
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 9999,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {
                "retirement_annual": 0,
                "survivor_annual": 0,
            },
            "events": [
                {
                    "enabled": True,
                    "type": "Retire",
                    "label": "Retirement (M)",
                    "person": "person1",
                    "year": 2026,
                },
                {
                    "enabled": True,
                    "type": "Expense",
                    "label": "Vacation",
                    "year": 2026,
                    "amount": -10000,
                    "expense_kind": "discretionary",
                    "repeat_every_years": 2,
                    "repeat_until_year": 2028,
                    "chart_first_occurrence_only": True,
                }
            ],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 50000.0},
                home_value=0.0,
                liability_balances={},
            )

        by_year = {int(row.year): row for row in df.itertuples()}
        self.assertIn("🎉 Retirement (M)", by_year[2026].events_active)
        self.assertIn("🏖️ Vacation", by_year[2026].events_active)
        self.assertNotIn("🏖️ Vacation", by_year[2028].events_active)

        item_2026 = by_year[2026].event_items[0]
        self.assertEqual(item_2026["label"], "Vacation")
        self.assertEqual(item_2026["amount"], -10000)
        self.assertEqual(item_2026["expense_kind"], "discretionary")
        self.assertEqual(item_2026["event_type"], "Expense")
        self.assertEqual(by_year[2028].event_items[0]["label"], "Vacation")

    def test_income_span_labels_each_active_year_by_default(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2028},
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 9999,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 9999,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {"retirement_annual": 0, "survivor_annual": 0},
            "events": [
                {
                    "enabled": True,
                    "type": "Income",
                    "label": "Consulting",
                    "year": 2026,
                    "end_year": 2028,
                    "amount": 1000,
                    "taxable": False,
                }
            ],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        by_year = {int(row.year): row for row in df.itertuples()}
        self.assertIn("💰 Consulting", by_year[2026].events_active)
        self.assertIn("💰 Consulting", by_year[2027].events_active)
        self.assertIn("💰 Consulting", by_year[2028].events_active)

    def test_income_recurrence_chart_first_occurrence_only_hides_later_occurrences(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2029},
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 9999,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 9999,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {"retirement_annual": 0, "survivor_annual": 0},
            "events": [
                {
                    "enabled": True,
                    "type": "Income",
                    "label": "Consulting",
                    "year": 2026,
                    "end_year": 2027,
                    "repeat_every_years": 2,
                    "repeat_count": 2,
                    "chart_first_occurrence_only": True,
                    "amount": 1000,
                    "taxable": False,
                }
            ],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        by_year = {int(row.year): row for row in df.itertuples()}
        self.assertIn("💰 Consulting", by_year[2026].events_active)
        self.assertIn("💰 Consulting", by_year[2027].events_active)
        self.assertNotIn("💰 Consulting", by_year[2028].events_active)
        self.assertNotIn("💰 Consulting", by_year[2029].events_active)

    def test_spending_shift_replace_updates_retirement_baseline(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2028},
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {
                "retirement_annual": 100,
                "survivor_percent_of_retirement": 0.5,
                "spending_basis": "nominal",
            },
            "events": [
                {
                    "enabled": True,
                    "type": "SpendingShift",
                    "label": "Move Abroad",
                    "year": 2027,
                    "mode": "replace",
                    "phase": "retirement_and_survivor",
                    "retirement_annual": 60,
                    "survivor_percent_of_retirement": 0.4,
                }
            ],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        by_year = {int(row.year): row for row in df.itertuples()}
        self.assertEqual(float(by_year[2026].annual_spend), 100.0)
        self.assertEqual(float(by_year[2027].annual_spend), 60.0)
        self.assertEqual(float(by_year[2028].annual_spend), 60.0)
        self.assertIn("🌍 Move Abroad", by_year[2027].events_active)

    def test_spending_shift_replace_updates_survivor_baseline(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2028},
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
            "person1": {
                "name": "Person 1",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "spending": {
                "retirement_annual": 100,
                "survivor_percent_of_retirement": 0.5,
                "spending_basis": "nominal",
            },
            "events": [
                {
                    "enabled": True,
                    "type": "EndOfPlan",
                    "label": "End of Plan (M)",
                    "person": "person1",
                    "year": 2026,
                },
                {
                    "enabled": True,
                    "type": "SpendingShift",
                    "label": "Move Abroad",
                    "year": 2027,
                    "mode": "replace",
                    "phase": "survivor",
                    "survivor_annual": 30,
                },
            ],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        by_year = {int(row.year): row for row in df.itertuples()}
        self.assertEqual(float(by_year[2026].annual_spend), 100.0)
        self.assertEqual(float(by_year[2027].annual_spend), 30.0)
        self.assertEqual(float(by_year[2028].annual_spend), 30.0)

    def test_resolve_runtime_config_syncs_end_of_plan_years_to_life_expectancy(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {"dob": "1967-04-23", "life_expectancy": 90},
            "person2": {"dob": "1976-10-02", "life_expectancy": 90},
            "events": [
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (M)", "person": "person1", "year": 2054},
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (W)", "person": "person2", "year": 2063},
            ],
        }

        resolved = model.resolve_runtime_config(config)
        years = {event["person"]: event["year"] for event in resolved["events"]}

        self.assertEqual(years["person1"], 2057)
        self.assertEqual(years["person2"], 2066)

    def test_resolve_runtime_config_synthesizes_retirement_from_person_settings(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {
                "retirement_year": 2035,
            },
            "person2": {
                "retirement_year": 2037,
            },
            "events": [],
        }

        resolved = model.resolve_runtime_config(config)
        retire_events = {
            event["person"]: event
            for event in resolved["events"]
            if event["type"] == "Retire"
        }

        self.assertEqual(retire_events["person1"]["year"], 2035)
        self.assertEqual(retire_events["person1"]["label"], "Retirement (P)")
        self.assertEqual(retire_events["person2"]["year"], 2037)
        self.assertEqual(retire_events["person2"]["label"], "Retirement (P)")

    def test_resolve_runtime_config_retire_keeps_legacy_label_and_enabled(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {
                "retirement_year": 2035,
            },
            "events": [
                {
                    "enabled": False,
                    "type": "Retire",
                    "label": "Retire (Person 1 legacy)",
                    "person": "person1",
                    "year": 2037,
                },
            ],
        }

        resolved = model.resolve_runtime_config(config)
        retire_event = next(e for e in resolved["events"] if e["type"] == "Retire")

        self.assertEqual(retire_event["year"], 2035)
        self.assertEqual(retire_event["label"], "Retire (Person 1 legacy)")
        self.assertFalse(retire_event["enabled"])

    def test_resolve_runtime_config_retire_falls_back_to_legacy_when_missing_person_year(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {},
            "events": [
                {
                    "enabled": True,
                    "type": "Retire",
                    "label": "Retirement (M)",
                    "person": "person1",
                    "year": 2037,
                },
            ],
        }

        resolved = model.resolve_runtime_config(config)
        retire_event = next(e for e in resolved["events"] if e["type"] == "Retire")

        self.assertEqual(retire_event["year"], 2037)

    def test_resolve_runtime_config_synthesizes_social_security_from_person_settings(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {
                "dob": "1967-04-23",
                "ss_start_age": 70,
                "social_security_benefits": {
                    "62": 1553,
                    "65": 2164,
                    "67": 2691,
                    "70": 3698,
                },
            },
            "person2": {
                "dob": "1976-10-02",
                "ss_start_age": 67,
                "social_security_benefits": {
                    "62": 700,
                    "67": 1000,
                    "70": 1400,
                },
            },
            "events": [],
        }

        resolved = model.resolve_runtime_config(config)
        ss_events = {
            event["person"]: event
            for event in resolved["events"]
            if event["type"] == "SocialSecurity"
        }

        self.assertEqual(ss_events["person1"]["year"], 2037)
        self.assertEqual(ss_events["person1"]["monthly_benefit"], 3698.0)
        self.assertEqual(ss_events["person1"]["label"], "SS Begins (P)")
        self.assertEqual(ss_events["person2"]["year"], 2043)
        self.assertEqual(ss_events["person2"]["monthly_benefit"], 1000.0)
        self.assertEqual(ss_events["person2"]["label"], "SS Begins (P)")

    def test_resolve_runtime_config_social_security_uses_legacy_fallback_when_schedule_missing(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {
                "dob": "1967-04-23",
                "ss_start_age": 70,
                "ss_monthly_benefit": 3698,
            },
            "events": [
                {"enabled": True, "type": "SocialSecurity", "label": "SS Begins (M)", "person": "person1", "year": 2034, "monthly_benefit": 2691},
            ],
        }

        resolved = model.resolve_runtime_config(config)
        ss_event = resolved["events"][0]

        self.assertEqual(ss_event["year"], 2037)
        self.assertEqual(ss_event["monthly_benefit"], 3698.0)

    def test_resolve_runtime_config_ss_keeps_legacy_taxability_metadata(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {
                "dob": "1967-04-23",
                "ss_start_age": 70,
                "social_security_benefits": {
                    "70": 3698,
                },
            },
            "events": [
                {
                    "enabled": False,
                    "type": "SocialSecurity",
                    "label": "SS (Person 1 legacy)",
                    "person": "person1",
                    "year": 2034,
                    "monthly_benefit": 2691,
                    "taxable_fraction": 0.5,
                },
            ],
        }

        resolved = model.resolve_runtime_config(config)
        ss_event = next(e for e in resolved["events"] if e["type"] == "SocialSecurity")

        self.assertEqual(ss_event["year"], 2037)
        self.assertEqual(ss_event["monthly_benefit"], 3698.0)
        self.assertEqual(ss_event["label"], "SS (Person 1 legacy)")
        self.assertEqual(ss_event["taxable_fraction"], 0.5)
        self.assertFalse(ss_event["enabled"])

    def test_home_value_uses_real_estate_appreciation_when_present(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2026},
            "assumptions": {
                "stock_return": 0.0,
                "bond_return": 0.0,
                "inflation": 0.03,
                "real_estate_appreciation": 0.05,
                "equity_allocation": 0.0,
                "effective_tax_rate_pre_retirement": 0.0,
                "effective_tax_rate_post_retirement": 0.0,
                "taxable_withdrawal_taxable_fraction": 0.0,
                "trad_ira_withdrawal_taxable_fraction": 0.0,
            },
            "person1": {"name": "Person 1", "retirement_year": 9999, "annual_take_home": 0, "annual_401k_contribution": 0, "annual_ira_contribution": 0},
            "person2": {"name": "Person 2", "retirement_year": 9999, "annual_take_home": 0, "annual_401k_contribution": 0, "annual_ira_contribution": 0},
            "spending": {"retirement_annual": 0, "survivor_annual": 0},
            "withdrawal_policy": {
                "accumulation_cash_target": 0.0,
                "retirement_cash_target": 0.0,
                "survivor_cash_target": 0.0,
                "accumulation_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "retirement_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "survivor_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
            },
            "events": [],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=100.0,
                liability_balances={},
                property_values={"Casa Lemuria": 100.0},
            )

        self.assertAlmostEqual(float(df.iloc[0]["home_value"]), 105.0, places=6)

    def test_home_value_falls_back_to_inflation_when_real_estate_appreciation_missing(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2026},
            "assumptions": {
                "stock_return": 0.0,
                "bond_return": 0.0,
                "inflation": 0.03,
                "equity_allocation": 0.0,
                "effective_tax_rate_pre_retirement": 0.0,
                "effective_tax_rate_post_retirement": 0.0,
                "taxable_withdrawal_taxable_fraction": 0.0,
                "trad_ira_withdrawal_taxable_fraction": 0.0,
            },
            "person1": {"name": "Person 1", "retirement_year": 9999, "annual_take_home": 0, "annual_401k_contribution": 0, "annual_ira_contribution": 0},
            "person2": {"name": "Person 2", "retirement_year": 9999, "annual_take_home": 0, "annual_401k_contribution": 0, "annual_ira_contribution": 0},
            "spending": {"retirement_annual": 0, "survivor_annual": 0},
            "withdrawal_policy": {
                "accumulation_cash_target": 0.0,
                "retirement_cash_target": 0.0,
                "survivor_cash_target": 0.0,
                "accumulation_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "retirement_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
                "survivor_withdrawal_order": ["cash_above_target", "taxable", "trad_ira", "roth", "cash_below_target"],
            },
            "events": [],
            "liabilities": [],
        }

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
                home_value=100.0,
                liability_balances={},
                property_values={"Casa Lemuria": 100.0},
            )

        self.assertAlmostEqual(float(df.iloc[0]["home_value"]), 103.0, places=6)

    def test_build_cashflow_table_splits_mandatory_and_discretionary_expenses(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "person1_income": 0.0,
                "person2_income": 0.0,
                "freed_payments": 0.0,
                "annual_spend": 0.0,
                "annual_taxes": 0.0,
                "net_flow": -15000.0,
                "event_items": [
                    {
                        "label": "Surgery",
                        "amount": -5000.0,
                        "expense_kind": "mandatory",
                        "event_type": "Expense",
                    },
                    {
                        "label": "Vacation",
                        "amount": -10000.0,
                        "expense_kind": "discretionary",
                        "event_type": "Expense",
                    },
                ],
            }
        ])

        html = tables.build_cashflow_table(df)

        self.assertIn("Mandatory event expenses", html)
        self.assertIn("Discretionary event expenses", html)
        self.assertIn("Surgery", html)
        self.assertIn("Vacation", html)

    def test_build_cashflow_table_shows_portfolio_funding_withdrawals(self):
        df = pd.DataFrame([
            {
                "year": 2035,
                "person1_income": 0.0,
                "person2_income": 0.0,
                "freed_payments": 0.0,
                "annual_spend": 95000.0,
                "annual_taxes": 5000.0,
                "net_flow": -100000.0,
                "withdrawal_cash": 20000.0,
                "withdrawal_taxable": 15000.0,
                "withdrawal_trad_ira": 65000.0,
                "withdrawal_roth": 0.0,
                "event_items": [],
            }
        ])

        html = tables.build_cashflow_table(df)

        self.assertIn("Portfolio Funding / Withdrawals", html)
        self.assertIn("Cash reserve drawdown", html)
        self.assertIn("Taxable withdrawals", html)
        self.assertIn("Traditional IRA / 401k withdrawals", html)
        self.assertIn("Total Portfolio Funding", html)

    def test_build_cashflow_table_uses_person_display_names(self):
        df = pd.DataFrame([
            {
                "year": 2030,
                "person1_income": 50000.0,
                "person2_income": 20000.0,
                "freed_payments": 0.0,
                "annual_spend": 0.0,
                "annual_taxes": 0.0,
                "net_flow": 70000.0,
                "event_items": [],
                "contribution_total": 9000.0,
                "contribution_trad_ira": 4000.0,
                "contribution_roth": 5000.0,
                "contribution_trad_ira_person1": 3000.0,
                "contribution_trad_ira_person2": 1000.0,
                "contribution_roth_person1": 2500.0,
                "contribution_roth_person2": 2500.0,
            }
        ])
        config = {
            "person1": {"name": "Person 1"},
            "person2": {"name": "Person 2"},
        }

        html = tables.build_cashflow_table(df, config=config)

        self.assertIn("Person 1 earned income", html)
        self.assertIn("Person 2 earned income", html)
        self.assertIn("Traditional IRA / 401k contributions — Person 1", html)
        self.assertIn("Traditional IRA / 401k contributions — Person 2", html)
        self.assertIn("Roth contributions — Person 1", html)
        self.assertIn("Roth contributions — Person 2", html)

    def test_build_accounts_table_shows_owner_split_rows_for_retirement_buckets(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "trad_ira": 300.0,
                "trad_ira_person1": 120.0,
                "trad_ira_person2": 180.0,
                "roth": 200.0,
                "roth_person1": 80.0,
                "roth_person2": 120.0,
                "taxable": 100.0,
                "cash": 50.0,
                "home_value": 0.0,
                "mortgage": 0.0,
                "home_equity": 0.0,
                "total_net_worth": 650.0,
            }
        ])
        config = {
            "person1": {"name": "Person 1"},
            "person2": {"name": "Person 2"},
        }

        html = tables.build_accounts_table(df, config=config)

        self.assertIn("Traditional IRA / 401k — Person 1", html)
        self.assertIn("Traditional IRA / 401k — Person 2", html)
        self.assertIn("Roth — Person 1", html)
        self.assertIn("Roth — Person 2", html)

    def test_build_portfolio_chart_shows_owner_split_traces_when_columns_present(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "taxable": 100.0,
                "trad_ira": 300.0,
                "trad_ira_person1": 120.0,
                "trad_ira_person2": 180.0,
                "roth": 200.0,
                "roth_person1": 80.0,
                "roth_person2": 120.0,
            },
            {
                "year": 2027,
                "taxable": 110.0,
                "trad_ira": 315.0,
                "trad_ira_person1": 126.0,
                "trad_ira_person2": 189.0,
                "roth": 210.0,
                "roth_person1": 84.0,
                "roth_person2": 126.0,
            },
        ])

        config = {
            "person1": {"name": "Person 1"},
            "person2": {"name": "Person 2"},
        }
        html = charts._build_portfolio_chart(df, config=config)

        self.assertIn("Traditional IRA \\u002f 401k \\u2014 Person 1", html)
        self.assertIn("Traditional IRA \\u002f 401k \\u2014 Person 2", html)
        self.assertIn("Roth \\u2014 Person 1", html)
        self.assertIn("Roth \\u2014 Person 2", html)

    def test_build_kpi_summary_uses_first_retirement_year_and_compact_values(self):
        config = {
            "person1": {"name": "Person 1", "dob": "1967-04-23"},
            "person2": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [
                {"enabled": True, "type": "Retire", "person": "person2", "year": 2037, "label": "Retirement (W)"},
                {"enabled": True, "type": "Retire", "person": "person1", "year": 2035, "label": "Retirement (M)"},
            ],
        }
        df = pd.DataFrame([
            {"year": 2026, "total_net_worth": 305000.0},
            {"year": 2035, "total_net_worth": 1040000.0},
            {"year": 2063, "total_net_worth": 1610000.0},
        ])

        html = charts._build_kpi_summary(config, df)

        self.assertIn("Net Worth (EOY)", html)
        self.assertIn("Net Worth at Retirement", html)
        self.assertIn("Retirement Age", html)
        self.assertIn("Net Worth at End", html)
        self.assertIn("$305K", html)
        self.assertIn("$1.04M", html)
        self.assertIn(">68<", html)
        self.assertIn("$1.61M", html)

    def test_build_chart_writes_kpi_strip_above_chart(self):
        config = {
            "display": {"projection_title": "Casa Lemuria"},
            "person1": {"name": "Person 1", "dob": "1967-04-23"},
            "person2": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [
                {"enabled": True, "type": "Retire", "person": "person1", "year": 2035, "label": "Retirement (M)"},
            ],
            "simulation": {"start_year": 2026, "end_year": 2063},
        }
        df = pd.DataFrame([
            {"year": 2026, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 305000.0, "survivor": False, "events_active": "", "person1_income": 0.0, "person2_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": []},
            {"year": 2035, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 1040000.0, "survivor": False, "events_active": "🎉 Retirement (M)", "person1_income": 0.0, "person2_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": []},
            {"year": 2063, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 1610000.0, "survivor": False, "events_active": "", "person1_income": 0.0, "person2_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": []},
        ])

        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    from pathlib import Path
                    out = Path("/tmp/nwn-kpi-test.html")
                    charts.build_chart(df, out)
                    html = out.read_text(encoding="utf-8")

        self.assertIn("kpi-strip", html)
        self.assertIn("Net Worth (EOY)", html)
        self.assertIn("Net Worth at Retirement", html)
        self.assertIn("Retirement Age", html)
        self.assertIn("Net Worth at End", html)
        self.assertIn(">Portfolio<", html)
        self.assertIn('id="nwn-portfolio"', html)
        self.assertLess(html.index("kpi-strip"), html.index('id="nwn-chart"'))

    def test_classify_accounts_honors_disabled_real_estate(self):
        config = {
            "accounts": {
                "disabled": ["Casa Lemuria"],
                "Casa Lemuria": "real_estate",
                "CO: Checking HHold (4412)": "cash",
                "Mortgage (5156)": "liability",
            },
            "liabilities": [{"name": "Mortgage (5156)"}],
        }
        raw = [
            {"name": "Casa Lemuria", "balance": 454500.0, "type": "Real Estate"},
            {"name": "CO: Checking HHold (4412)", "balance": 12000.0, "type": "Depository"},
            {"name": "Mortgage (5156)", "balance": -125355.55, "type": "Loan"},
        ]

        portfolio, extras = monarch_bridge.classify_accounts(raw, config)
        liabilities = monarch_bridge.extract_liability_balances(raw, config)

        self.assertEqual(portfolio["cash"], 12000.0)
        self.assertEqual(extras["home_value"], 0.0)
        self.assertEqual(liabilities, {"Mortgage (5156)": 125355.55})

    def test_offline_cache_with_raw_accounts_reclassifies_using_current_config(self):
        cached = {
            "timestamp": "2026-06-17T00:00:00",
            "portfolio": {"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0},
            "extras": {"home_value": 454500.0, "vehicles": 0.0, "other": 0.0},
            "liability_balances": {"Mortgage (5156)": 125355.55},
            "raw_accounts": [
                {"name": "Casa Lemuria", "balance": 454500.0, "type": "Real Estate"},
                {"name": "CO: Checking HHold (4412)", "balance": 12000.0, "type": "Depository"},
                {"name": "Mortgage (5156)", "balance": -125355.55, "type": "Loan"},
            ],
        }
        config = {
            "accounts": {
                "disabled": ["Casa Lemuria"],
                "Casa Lemuria": "real_estate",
                "CO: Checking HHold (4412)": "cash",
                "Mortgage (5156)": "liability",
            },
            "liabilities": [{"name": "Mortgage (5156)"}],
        }

        captured = {}

        def fake_run_projection(
            balances,
            home_value=0.0,
            liability_balances=None,
            property_values=None,
            config=None,
        ):
            captured["balances"] = balances
            captured["home_value"] = home_value
            captured["liability_balances"] = liability_balances
            captured["property_values"] = property_values
            return pd.DataFrame([
                {
                    "year": 2026,
                    "home_value": home_value,
                    "mortgage": liability_balances.get("Mortgage (5156)", 0.0),
                    "home_equity": home_value - liability_balances.get("Mortgage (5156)", 0.0),
                    "cash": balances.get("cash", 0.0),
                    "taxable": balances.get("taxable", 0.0),
                    "trad_ira": balances.get("trad_ira", 0.0),
                    "roth": balances.get("roth", 0.0),
                    "total_net_worth": sum(balances.values()) + home_value - liability_balances.get("Mortgage (5156)", 0.0),
                    "survivor": False,
                    "events_active": "",
                    "person1_income": 0.0,
                    "person2_income": 0.0,
                    "freed_payments": 0.0,
                    "annual_spend": 0.0,
                    "annual_taxes": 0.0,
                    "net_flow": 0.0,
                    "event_items": [],
                }
            ])

        with patch.object(run, "OFFLINE", True):
            with patch("run.load_cache", return_value=cached):
                with patch("run.build_chart"):
                    with patch("run.shutil.copy2"):
                        with patch("pathlib.Path.chmod"):
                            with patch("run.run_projection", side_effect=fake_run_projection):
                                with patch("src.monarch_bridge.load_config", return_value=config):
                                    run.main()

        self.assertEqual(captured["balances"]["cash"], 12000.0)
        self.assertEqual(captured["home_value"], 454500.0)
        self.assertEqual(captured["liability_balances"], {"Mortgage (5156)": 125355.55})
        self.assertEqual(captured["property_values"], {"Casa Lemuria": 454500.0})

    def test_xaxis_tick_spec_includes_age_labels(self):
        config = {
            "person1": {"dob": "1967-04-23"},
            "person2": {"dob": "1976-10-02"},
        }

        tickvals, ticktext = charts._xaxis_tick_spec(config, [2026, 2027, 2028, 2029])

        self.assertEqual(tickvals, [2026, 2028])
        self.assertEqual(ticktext, ["2026<br>(59/50)", "2028<br>(61/52)"])

    def test_build_figure_keeps_negative_cash_trace_visible(self):
        config = {
            "display": {"projection_title": "Negative Cash Test"},
            "person1": {"dob": "1967-04-23"},
            "person2": {"dob": "1976-10-02"},
        }
        df = pd.DataFrame([
            {
                "year": 2026,
                "home_equity": 0.0,
                "cash": -50.0,
                "taxable": 0.0,
                "trad_ira": 0.0,
                "roth": 0.0,
                "total_net_worth": -50.0,
                "survivor": False,
                "events_active": "",
            },
            {
                "year": 2027,
                "home_equity": 0.0,
                "cash": -25.0,
                "taxable": 0.0,
                "trad_ira": 0.0,
                "roth": 0.0,
                "total_net_worth": -25.0,
                "survivor": False,
                "events_active": "",
            },
        ])

        fig = charts._build_figure(df, config)
        trace_names = [trace.name for trace in fig.data]

        self.assertIn("Cash", trace_names)
        self.assertEqual(list(fig.layout.xaxis.ticktext), ["2026<br>(59/50)"])

    def test_wrap_event_annotation_groups_every_two_items(self):
        label = "💸 One, 💸 Two, 💸 Three, 💸 Four, 💸 Five"
        wrapped = charts._wrap_event_annotation(label, per_line=2)

        self.assertEqual(wrapped, "💸 One, 💸 Two<br>💸 Three, 💸 Four<br>💸 Five")

    def test_event_annotations_are_right_anchored_and_drop_into_chart_body(self):
        config = {
            "person1": {"dob": "1967-04-23"},
            "person2": {"dob": "1976-10-02"},
        }
        df = pd.DataFrame([
            {
                "year": 2026,
                "home_equity": 0.0,
                "cash": 100.0,
                "taxable": 0.0,
                "trad_ira": 0.0,
                "roth": 0.0,
                "total_net_worth": 100.0,
                "survivor": False,
                "events_active": "💸 One, 💸 Two, 💸 Three",
            }
        ])

        fig = charts._build_figure(df, config)
        annotation = fig.layout.annotations[0]

        self.assertEqual(annotation.align, "right")
        self.assertEqual(annotation.xanchor, "right")
        self.assertEqual(annotation.yanchor, "top")
        self.assertEqual(annotation.textangle, -90)
        self.assertEqual(annotation.text, "💸 One, 💸 Two<br>💸 Three")


if __name__ == "__main__":
    unittest.main()
