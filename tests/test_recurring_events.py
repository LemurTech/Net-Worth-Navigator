import unittest
from unittest.mock import patch

import pandas as pd

from src import charts, model, tables


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
                },
                {
                    "enabled": True,
                    "type": "Education",
                    "label": "Certification",
                    "person": "matthew",
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
            "matthew": {
                "name": "Person 1",
                "retirement_year": 2030,
                "annual_take_home": 0,
                "annual_401k_contribution": 0,
                "annual_ira_contribution": 0,
            },
            "weny": {
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
                    "person": "matthew",
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
        self.assertIn("🏖️ Vacation", by_year[2028].events_active)

        item_2026 = by_year[2026].event_items[0]
        self.assertEqual(item_2026["label"], "Vacation")
        self.assertEqual(item_2026["amount"], -10000)
        self.assertEqual(item_2026["expense_kind"], "discretionary")
        self.assertEqual(item_2026["event_type"], "Expense")

    def test_build_cashflow_table_splits_mandatory_and_discretionary_expenses(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "matthew_income": 0.0,
                "weny_income": 0.0,
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

    def test_build_kpi_summary_uses_first_retirement_year_and_compact_values(self):
        config = {
            "matthew": {"name": "Person 1", "dob": "1967-04-23"},
            "weny": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [
                {"enabled": True, "type": "Retire", "person": "weny", "year": 2037, "label": "Retirement (W)"},
                {"enabled": True, "type": "Retire", "person": "matthew", "year": 2035, "label": "Retirement (M)"},
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
            "matthew": {"name": "Person 1", "dob": "1967-04-23"},
            "weny": {"name": "Person 2", "dob": "1976-10-02"},
            "events": [
                {"enabled": True, "type": "Retire", "person": "matthew", "year": 2035, "label": "Retirement (M)"},
            ],
            "simulation": {"start_year": 2026, "end_year": 2063},
        }
        df = pd.DataFrame([
            {"year": 2026, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 305000.0, "survivor": False, "events_active": "", "matthew_income": 0.0, "weny_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": []},
            {"year": 2035, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 1040000.0, "survivor": False, "events_active": "🎉 Retirement (M)", "matthew_income": 0.0, "weny_income": 0.0,
             "freed_payments": 0.0, "annual_spend": 0.0, "annual_taxes": 0.0, "net_flow": 0.0, "event_items": []},
            {"year": 2063, "home_value": 0.0, "mortgage": 0.0, "home_equity": 0.0, "cash": 100.0, "taxable": 100.0, "trad_ira": 100.0, "roth": 100.0,
             "total_net_worth": 1610000.0, "survivor": False, "events_active": "", "matthew_income": 0.0, "weny_income": 0.0,
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
        self.assertLess(html.index("kpi-strip"), html.index('id="nwn-chart"'))


if __name__ == "__main__":
    unittest.main()
