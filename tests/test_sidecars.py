import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.model import ProjectionResult
from src.sidecars import write_sidecars
from src.scenarios import ScenarioRef


class SidecarTests(unittest.TestCase):
    def test_write_sidecars_outputs_normalized_bundle(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "net_worth": 100.0,
                "home_value": 500.0,
                "mortgage": 300.0,
                "home_equity": 200.0,
                "total_net_worth": 300.0,
                "person1_income": 10.0,
                "person2_income": 20.0,
                "taxable_income": 5.0,
                "tax_phase": "retirement",
                "tax_mode": "brackets",
                "tax_filing_status": "married_joint",
                "taxable_wage_income": 0.0,
                "non_ss_taxable_income": 5.0,
                "withdrawal_taxable_income": 0.0,
                "other_taxable_income": 5.0,
                "taxable_social_security_income": 0.0,
                "social_security_taxable_fraction": 0.0,
                "social_security_provisional_income": 5.0,
                "annual_taxes": 1.0,
                "annual_federal_taxes": 1.0,
                "annual_state_taxes": 0.0,
                "federal_standard_deduction": 0.0,
                "federal_taxable_after_deduction": 5.0,
                "federal_effective_rate": 0.2,
                "state_tax_enabled": False,
                "state_tax_name": "",
                "state_tax_filing_status": "",
                "state_standard_deduction": 0.0,
                "state_taxable_before_deduction": 5.0,
                "state_taxable_income": 0.0,
                "state_effective_rate": 0.0,
                "state_social_security_taxed": False,
                "annual_spend": 15.0,
                "freed_payments": 0.0,
                "net_flow": 14.0,
                "survivor": False,
                "event_items": [
                    {
                        "label": "Sell Casa Lemuria",
                        "amount": 170000.0,
                        "event_type": "SellHome",
                    },
                    {
                        "label": "Vacation",
                        "amount": -5000.0,
                        "event_type": "Expense",
                        "expense_kind": "discretionary",
                    },
                ],
                "events_active": "🏡 Sell Casa Lemuria, 🏖️ Vacation",
                "taxable": 170000.0,
                "trad_ira": 100.0,
                "roth": 0.0,
                "cash": 0.0,
            }
        ])
        config = {
            "simulation": {"start_year": 2026, "end_year": 2066},
            "person1": {"name": "Person 1", "dob": "1967-04-23", "life_expectancy": 90, "retirement_year": 2035, "annual_take_home": 0.0},
            "person2": {"name": "Person 2", "dob": "1976-10-02", "life_expectancy": 90, "retirement_year": 2035, "annual_take_home": 0.0},
            "assumptions": {"real_estate_sale_fee_rate": 0.06},
            "withdrawal_policy": {},
            "events": [
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (M)", "person": "person1", "year": 2054},
                {"enabled": True, "type": "EndOfPlan", "label": "End of Plan (W)", "person": "person2", "year": 2063},
                {"enabled": True, "type": "SellHome", "label": "Sell Casa Lemuria", "year": 2049, "property": "Casa Lemuria", "reinvest_to": "taxable"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            sidecar_dir = Path(tmp) / "sidecars"
            scenario = ScenarioRef(
                slug="default",
                name="Default Plan",
                description="Baseline scenario",
                config_path=Path(tmp) / "config.toml",
                is_default=True,
            )
            paths = write_sidecars(
                output_dir=sidecar_dir,
                df=df,
                config=config,
                scenario=scenario,
                mode="offline",
                cache_timestamp="2026-06-18T00:00:00",
                portfolio={"taxable": 0.0, "trad_ira": 100.0, "roth": 0.0, "cash": 0.0},
                extras={"home_value": 500.0, "vehicles": 0.0, "other": 0.0},
                liability_balances={"Mortgage": 300.0},
                property_values={"Casa Lemuria": 500.0},
                raw_accounts=[{"name": "Casa Lemuria", "balance": 500.0, "type": "real_estate"}],
            )

            for path in paths.values():
                self.assertTrue(path.exists())

            projection_csv = sidecar_dir / "projection_yearly.csv"
            projection_df = pd.read_csv(projection_csv)
            self.assertNotIn("event_items", projection_df.columns)
            self.assertIn("events_active", projection_df.columns)
            self.assertEqual(float(projection_df.iloc[0]["taxable"]), 170000.0)

            event_flows_csv = sidecar_dir / "event_flows.csv"
            event_flows_df = pd.read_csv(event_flows_csv)
            self.assertEqual(len(event_flows_df), 2)
            self.assertEqual(set(event_flows_df["label"].tolist()), {"Sell Casa Lemuria", "Vacation"})

            tax_breakdown_csv = sidecar_dir / "tax_breakdown_yearly.csv"
            tax_breakdown_df = pd.read_csv(tax_breakdown_csv)
            self.assertIn("tax_phase", tax_breakdown_df.columns)
            self.assertIn("annual_federal_taxes", tax_breakdown_df.columns)
            self.assertIn("federal_taxable_after_deduction", tax_breakdown_df.columns)
            self.assertIn("social_security_taxable_fraction", tax_breakdown_df.columns)
            self.assertEqual(str(tax_breakdown_df.iloc[0]["tax_mode"]), "brackets")

            manifest = json.loads((sidecar_dir / "scenario_manifest.json").read_text())
            self.assertEqual(manifest["mode"], "offline")
            self.assertEqual(manifest["scenario"]["slug"], "default")
            self.assertEqual(manifest["resolved_end_of_plan_years"]["person1"], 2057)
            self.assertEqual(manifest["resolved_end_of_plan_years"]["person2"], 2066)
            self.assertEqual(manifest["projection_summary"]["row_count"], 1)
            self.assertEqual(manifest["simulation"]["result_mode"], "deterministic")
            self.assertEqual(manifest["sidecars"]["tax_breakdown_yearly_csv"], "tax_breakdown_yearly.csv")

            accounts = json.loads((sidecar_dir / "accounts_snapshot.json").read_text())
            self.assertEqual(accounts["property_values"]["Casa Lemuria"], 500.0)
            self.assertEqual(accounts["liability_balances"]["Mortgage"], 300.0)

            summary = json.loads((sidecar_dir / "simulation_summary.json").read_text())
            self.assertEqual(summary, {})

    def test_write_sidecars_outputs_monte_carlo_bundle(self):
        df = pd.DataFrame([
            {
                "year": 2026,
                "net_worth": 100.0,
                "home_value": 0.0,
                "mortgage": 0.0,
                "home_equity": 0.0,
                "total_net_worth": 100.0,
                "person1_income": 0.0,
                "person2_income": 0.0,
                "taxable_income": 0.0,
                "tax_phase": "retirement",
                "tax_mode": "brackets",
                "tax_filing_status": "married_joint",
                "taxable_wage_income": 0.0,
                "non_ss_taxable_income": 0.0,
                "withdrawal_taxable_income": 0.0,
                "other_taxable_income": 0.0,
                "taxable_social_security_income": 0.0,
                "social_security_taxable_fraction": 0.0,
                "social_security_provisional_income": 0.0,
                "annual_taxes": 0.0,
                "annual_federal_taxes": 0.0,
                "annual_state_taxes": 0.0,
                "federal_standard_deduction": 0.0,
                "federal_taxable_after_deduction": 0.0,
                "federal_effective_rate": 0.0,
                "state_tax_enabled": False,
                "state_tax_name": "",
                "state_tax_filing_status": "",
                "state_standard_deduction": 0.0,
                "state_taxable_before_deduction": 0.0,
                "state_taxable_income": 0.0,
                "state_effective_rate": 0.0,
                "state_social_security_taxed": False,
                "annual_spend": 0.0,
                "freed_payments": 0.0,
                "net_flow": 0.0,
                "survivor": False,
                "event_items": [],
                "events_active": "",
                "taxable": 0.0,
                "trad_ira": 100.0,
                "roth": 0.0,
                "cash": 0.0,
            }
        ])
        band_df = pd.DataFrame([
            {
                "year": 2026,
                "total_net_worth_p10": 80.0,
                "total_net_worth_p25": 90.0,
                "total_net_worth_p50": 100.0,
                "total_net_worth_p75": 115.0,
                "total_net_worth_p90": 130.0,
                "net_worth_p10": 80.0,
                "net_worth_p25": 90.0,
                "net_worth_p50": 100.0,
                "net_worth_p75": 115.0,
                "net_worth_p90": 130.0,
            }
        ])
        projection_result = ProjectionResult(
            mode="monte_carlo",
            yearly_df=df,
            band_df=band_df,
            summary={"mode": "monte_carlo", "run_count": 25, "success_rate": 0.88},
            simulation={"mode": "monte_carlo", "num_runs": 25, "seed": 123},
            run_count=25,
            display_path_kind="median",
        )
        config = {
            "simulation": {"start_year": 2026, "end_year": 2026, "mode": "monte_carlo", "num_runs": 25, "seed": 123},
            "person1": {"name": "Person 1", "dob": "1967-04-23", "life_expectancy": 90, "retirement_year": 2035, "annual_take_home": 0.0},
            "person2": {"name": "Person 2", "dob": "1976-10-02", "life_expectancy": 90, "retirement_year": 2035, "annual_take_home": 0.0},
            "assumptions": {},
            "withdrawal_policy": {},
            "events": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            sidecar_dir = Path(tmp) / "sidecars"
            scenario = ScenarioRef(
                slug="default",
                name="Default Plan",
                description="Baseline scenario",
                config_path=Path(tmp) / "config.toml",
                is_default=True,
            )
            paths = write_sidecars(
                output_dir=sidecar_dir,
                projection_result=projection_result,
                config=config,
                scenario=scenario,
                mode="offline",
                cache_timestamp=None,
                portfolio={"taxable": 0.0, "trad_ira": 100.0, "roth": 0.0, "cash": 0.0},
                extras={"home_value": 0.0, "vehicles": 0.0, "other": 0.0},
                liability_balances={},
                property_values={},
                raw_accounts=[],
            )

            self.assertIn("projection_bands_yearly_csv", paths)
            self.assertTrue((sidecar_dir / "projection_bands_yearly.csv").exists())
            manifest = json.loads((sidecar_dir / "scenario_manifest.json").read_text())
            self.assertEqual(manifest["simulation"]["result_mode"], "monte_carlo")
            self.assertEqual(manifest["simulation"]["run_count"], 25)


if __name__ == "__main__":
    unittest.main()
