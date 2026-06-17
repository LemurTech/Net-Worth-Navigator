import unittest
from unittest.mock import patch

from src import model


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

        certification_spans = [
            (event["start_year"], event["end_year"])
            for event in events
            if event["label"] == "Certification"
        ]
        self.assertEqual(certification_spans, [(2027, 2028), (2030, 2031)])

    def test_run_projection_applies_recurring_expense_to_each_occurrence_year(self):
        config = {
            "simulation": {"start_year": 2026, "end_year": 2030},
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
                "retirement_year": 9999,
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
                    "type": "Expense",
                    "label": "Vacation",
                    "year": 2026,
                    "amount": -10000,
                    "repeat_every_years": 2,
                    "repeat_until_year": 2030,
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

        event_labels_by_year = {
            int(row.year): [label for label, _ in (row.event_items or [])]
            for row in df.itertuples()
        }

        self.assertEqual(event_labels_by_year[2026], ["Vacation"])
        self.assertEqual(event_labels_by_year[2027], [])
        self.assertEqual(event_labels_by_year[2028], ["Vacation"])
        self.assertEqual(event_labels_by_year[2029], [])
        self.assertEqual(event_labels_by_year[2030], ["Vacation"])


if __name__ == "__main__":
    unittest.main()
