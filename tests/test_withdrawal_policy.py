import unittest
from unittest.mock import patch

from src import model


class WithdrawalPolicyTests(unittest.TestCase):
    def _base_config(self):
        return {
            "simulation": {"start_year": 2026, "end_year": 2026},
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
                "annual_take_home_real_raise": 0.0,
                "annual_401k_contribution": 0,
                "annual_401k_contribution_extra_increase": 0.0,
                "annual_ira_contribution": 0,
            },
            "person2": {
                "name": "Person 2",
                "retirement_year": 2026,
                "annual_take_home": 0,
                "annual_take_home_real_raise": 0.0,
                "annual_401k_contribution": 0,
                "annual_401k_contribution_extra_increase": 0.0,
                "annual_ira_contribution": 0,
            },
            "spending": {
                "retirement_annual": 0,
                "survivor_percent_of_retirement": 0.0,
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
            "events": [
                {"enabled": True, "type": "Retire", "label": "Retirement (M)", "person": "person1", "year": 2026},
                {"enabled": True, "type": "Retire", "label": "Retirement (W)", "person": "person2", "year": 2026},
            ],
            "liabilities": [],
        }

    def test_retirement_deficit_preserves_cash_target_before_tapping_taxable(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 40.0
        config["withdrawal_policy"]["retirement_cash_target"] = 80.0

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 100.0, "taxable": 50.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 80.0)
        self.assertEqual(row["taxable"], 30.0)

    def test_retirement_withdrawal_order_can_prioritize_trad_ira_before_taxable(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 60.0
        config["withdrawal_policy"]["retirement_withdrawal_order"] = [
            "cash_above_target", "trad_ira", "taxable", "roth", "cash_below_target"
        ]

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 50.0, "trad_ira": 50.0, "roth": 50.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["trad_ira"], 0.0)
        self.assertEqual(row["taxable"], 40.0)
        self.assertEqual(row["roth"], 50.0)
        self.assertEqual(row["withdrawal_trad_ira"], 50.0)
        self.assertEqual(row["withdrawal_taxable"], 10.0)
        self.assertEqual(row["withdrawal_cash"], 0.0)

    def test_accumulation_expense_can_draw_from_cash_reserve_before_roth(self):
        config = self._base_config()
        config["person1"]["retirement_year"] = 2100
        config["person2"]["retirement_year"] = 2100
        config["withdrawal_policy"]["accumulation_cash_target"] = 64.0
        config["events"].append(
            {
                "enabled": True,
                "type": "Expense",
                "label": "Surgery",
                "year": 2026,
                "amount": -18.0,
                "expense_kind": "mandatory",
                "funding": "cash_reserve_first",
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 50.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 100.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 32.0)
        self.assertEqual(row["roth"], 100.0)
        self.assertEqual(row["withdrawal_cash"], 18.0)
        self.assertEqual(row["withdrawal_roth"], 0.0)

    def test_accumulation_expense_without_reserve_override_still_preserves_cash_target(self):
        config = self._base_config()
        config["person1"]["retirement_year"] = 2100
        config["person2"]["retirement_year"] = 2100
        config["withdrawal_policy"]["accumulation_cash_target"] = 64.0
        config["events"].append(
            {
                "enabled": True,
                "type": "Expense",
                "label": "Surgery",
                "year": 2026,
                "amount": -18.0,
                "expense_kind": "mandatory",
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 50.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 100.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 50.0)
        self.assertEqual(row["roth"], 82.0)
        self.assertEqual(row["withdrawal_cash"], 0.0)
        self.assertEqual(row["withdrawal_roth"], 18.0)

    def test_surplus_refills_cash_target_before_investing_remainder(self):
        config = self._base_config()
        config["withdrawal_policy"]["retirement_cash_target"] = 50.0
        config["events"].append(
            {
                "enabled": True,
                "type": "Income",
                "label": "Side Income",
                "year": 2026,
                "amount": 40.0,
                "taxable": False,
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 20.0, "taxable": 80.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 50.0)
        # Surplus above cash target goes to the first bucket in the default
        # surplus_order: roth
        self.assertEqual(row["roth"], 10.0)
        self.assertEqual(row["taxable"], 80.0)

    def test_surplus_sweeps_cash_above_target_back_into_investments(self):
        portfolio = {"cash": 120.0, "taxable": 80.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=10.0,
            cash_target=50.0,
            surplus_order=["taxable", "roth", "trad_ira"],
        )

        self.assertEqual(portfolio["cash"], 50.0)
        self.assertEqual(portfolio["taxable"], 160.0)

    def test_surplus_sweep_runs_even_with_zero_new_surplus(self):
        portfolio = {"cash": 120.0, "taxable": 80.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=0.0,
            cash_target=50.0,
            surplus_order=["taxable", "roth", "trad_ira"],
        )

        self.assertEqual(portfolio["cash"], 50.0)
        self.assertEqual(portfolio["taxable"], 150.0)

    def test_surplus_sweep_respects_protected_cash_floor(self):
        portfolio = {"cash": 170.0, "taxable": 80.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=0.0,
            cash_target=50.0,
            protected_cash=100.0,
            surplus_order=["taxable", "roth", "trad_ira"],
        )

        self.assertEqual(portfolio["cash"], 150.0)
        self.assertEqual(portfolio["taxable"], 100.0)

    def test_surplus_fallback_prefers_configured_surplus_order_over_reversed_withdrawal_order(self):
        portfolio = {"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=100.0,
            cash_target=0.0,
            surplus_order=["taxable", "roth", "trad_ira"],
        )

        self.assertEqual(portfolio["taxable"], 100.0)
        self.assertEqual(portfolio["cash"], 0.0)
        self.assertEqual(portfolio["roth"], 0.0)
        self.assertEqual(portfolio["trad_ira"], 0.0)

    def test_surplus_default_order_routes_to_roth_when_no_explicit_order(self):
        """With no configured surplus_order, the default ["roth", "taxable"] applies."""
        portfolio = {"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=100.0,
            cash_target=0.0,
        )

        self.assertEqual(portfolio["roth"], 100.0)
        self.assertEqual(portfolio["cash"], 0.0)
        self.assertEqual(portfolio["taxable"], 0.0)
        self.assertEqual(portfolio["trad_ira"], 0.0)

    def test_surplus_fallback_skips_excluded_bucket_and_uses_next_surplus_order_choice(self):
        portfolio = {"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0}

        model._apply_surplus_with_reserve_target(
            portfolio,
            surplus=100.0,
            cash_target=0.0,
            excluded_categories={"trad_ira"},
            surplus_order=["taxable", "roth", "trad_ira"],
        )

        self.assertEqual(portfolio["taxable"], 100.0)
        self.assertEqual(portfolio["cash"], 0.0)
        self.assertEqual(portfolio["roth"], 0.0)
        self.assertEqual(portfolio["trad_ira"], 0.0)

    def test_survivor_cash_target_defaults_from_percent_of_retirement_spend(self):
        config = self._base_config()
        config["spending"]["retirement_annual"] = 100000
        config["spending"]["survivor_percent_of_retirement"] = 0.65
        config["withdrawal_policy"].pop("survivor_cash_target")

        policy = model.resolve_withdrawal_policy(config, {"cash": 1000.0})

        self.assertEqual(policy["survivor_cash_target"], 65000.0)

    def test_take_home_growth_compounds_inflation_and_real_raise(self):
        rate = model._person_income_growth_rate(
            {"annual_take_home_real_raise": 0.02},
            {"inflation": 0.03},
        )
        self.assertAlmostEqual(rate, 0.0506, places=6)

        income = model._project_person_take_home(
            {"annual_take_home": 1000.0, "annual_take_home_real_raise": 0.02},
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.03},
        )
        self.assertAlmostEqual(income, 1103.76036, places=5)

    def test_401k_growth_compounds_income_growth_and_extra_increase(self):
        contribution = model._project_person_401k_contribution(
            {
                "annual_401k_contribution": 100.0,
                "annual_take_home_real_raise": 0.02,
                "annual_401k_contribution_extra_increase": 0.02,
            },
            year=2028,
            simulation_start_year=2026,
            assumptions={"inflation": 0.03},
        )
        self.assertAlmostEqual(contribution, 114.8352278544, places=5)

    def test_401k_split_routes_total_contribution_between_trad_and_roth(self):
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "annual_401k_contribution": 100.0,
                "annual_401k_contribution_split": {
                    "trad_ira": 31,
                    "roth": 69,
                },
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )

        self.assertAlmostEqual(breakdown["trad_ira"], 31.0)
        self.assertAlmostEqual(breakdown["roth"], 69.0)

    def test_401k_bucket_override_remains_fallback_when_no_split_is_configured(self):
        breakdown = model._person_retirement_contribution_breakdown(
            {
                "annual_401k_contribution": 100.0,
                "annual_401k_contribution_bucket": "roth",
            },
            year=2026,
            simulation_start_year=2026,
            assumptions={"inflation": 0.0},
        )

        self.assertAlmostEqual(breakdown["trad_ira"], 0.0)
        self.assertAlmostEqual(breakdown["roth"], 100.0)

    def test_take_home_net_of_retirement_contrib_does_not_reduce_implied_spending(self):
        config = self._base_config()
        config["person1"]["retirement_year"] = 2100
        config["person2"]["retirement_year"] = 2100
        config["person1"]["annual_take_home"] = 100.0
        config["person1"]["annual_ira_contribution"] = 10.0
        config["person1"]["annual_take_home_is_net_of_retirement_contributions"] = True

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
            )

        row = df.iloc[0]
        self.assertEqual(row["annual_spend"], 100.0)
        self.assertEqual(row["contribution_roth"], 10.0)
        self.assertEqual(row["roth"], 10.0)

    def test_sell_home_event_converts_equity_to_cash_and_clears_mortgage(self):
        config = self._base_config()
        config["liabilities"] = [
            {
                "name": "Mortgage",
                "annual_rate": 0.0,
                "monthly_base": 0.0,
                "monthly_extra": 0.0,
                "type": "mortgage",
            }
        ]
        config["events"].append(
            {
                "enabled": True,
                "type": "SellHome",
                "label": "Sell Casa Lemuria",
                "year": 2026,
                "property": "Casa Lemuria",
                "liability_names": ["Mortgage"],
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=500_000.0,
                liability_balances={"Mortgage": 300_000.0},
                property_values={"Casa Lemuria": 500_000.0},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 170_000.0)
        self.assertEqual(row["mortgage"], 0.0)
        self.assertEqual(row["home_value"], 0.0)
        self.assertEqual(row["home_equity"], 0.0)
        self.assertEqual(row["total_net_worth"], 170_000.0)
        self.assertEqual(row["event_items"][0]["event_type"], "SellHome")
        self.assertEqual(row["event_items"][0]["amount"], 170_000.0)
        self.assertIn("🏡 Sell Casa Lemuria", row["events_active"])

    def test_sell_home_proceeds_stay_in_cash_instead_of_auto_investing(self):
        config = self._base_config()
        config["liabilities"] = [
            {
                "name": "Mortgage",
                "annual_rate": 0.0,
                "monthly_base": 0.0,
                "monthly_extra": 0.0,
                "type": "mortgage",
            }
        ]
        config["events"].append(
            {
                "enabled": True,
                "type": "SellHome",
                "label": "Sell Casa Lemuria",
                "year": 2026,
                "property": "Casa Lemuria",
                "liability_names": ["Mortgage"],
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 100.0, "roth": 0.0},
                home_value=500_000.0,
                liability_balances={"Mortgage": 300_000.0},
                property_values={"Casa Lemuria": 500_000.0},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 170_000.0)
        self.assertEqual(row["trad_ira"], 100.0)

    def test_sell_home_can_reinvest_all_proceeds_into_taxable(self):
        config = self._base_config()
        config["liabilities"] = [
            {
                "name": "Mortgage",
                "annual_rate": 0.0,
                "monthly_base": 0.0,
                "monthly_extra": 0.0,
                "type": "mortgage",
            }
        ]
        config["events"].append(
            {
                "enabled": True,
                "type": "SellHome",
                "label": "Sell Casa Lemuria",
                "year": 2026,
                "property": "Casa Lemuria",
                "liability_names": ["Mortgage"],
                "reinvest_to": "taxable",
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 100.0, "roth": 0.0},
                home_value=500_000.0,
                liability_balances={"Mortgage": 300_000.0},
                property_values={"Casa Lemuria": 500_000.0},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 0.0)
        self.assertEqual(row["taxable"], 170_000.0)
        self.assertEqual(row["trad_ira"], 100.0)

    def test_sell_home_can_reinvest_partial_proceeds_into_taxable(self):
        config = self._base_config()
        config["liabilities"] = [
            {
                "name": "Mortgage",
                "annual_rate": 0.0,
                "monthly_base": 0.0,
                "monthly_extra": 0.0,
                "type": "mortgage",
            }
        ]
        config["events"].append(
            {
                "enabled": True,
                "type": "SellHome",
                "label": "Sell Casa Lemuria",
                "year": 2026,
                "property": "Casa Lemuria",
                "liability_names": ["Mortgage"],
                "reinvest_to": "taxable",
                "reinvest_fraction": 0.25,
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 0.0, "taxable": 0.0, "trad_ira": 100.0, "roth": 0.0},
                home_value=500_000.0,
                liability_balances={"Mortgage": 300_000.0},
                property_values={"Casa Lemuria": 500_000.0},
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 127_500.0)
        self.assertEqual(row["taxable"], 42_500.0)
        self.assertEqual(row["trad_ira"], 100.0)

    def test_buy_home_adds_tracked_property_to_home_value(self):
        config = self._base_config()
        config["assumptions"]["real_estate_appreciation"] = 0.0
        config["events"].append(
            {
                "enabled": True,
                "type": "BuyHome",
                "label": "Indonesia Home Purchase",
                "property": "Indonesia House",
                "year": 2026,
                "price": 350_000.0,
                "down_payment": 100_000.0,
            }
        )

        with patch("src.model.load_config", return_value=config):
            df = model.run_projection(
                balances={"cash": 500_000.0, "taxable": 0.0, "trad_ira": 0.0, "roth": 0.0},
                home_value=0.0,
                liability_balances={},
                property_values=None,
            )

        row = df.iloc[0]
        self.assertEqual(row["cash"], 0.0)
        # Surplus from the down-payment net proceeds routes to the first
        # surplus_order bucket (roth by default), not taxable.
        self.assertEqual(row["roth"], 400_000.0)
        self.assertEqual(row["taxable"], 0.0)
        self.assertEqual(row["home_value"], 350_000.0)
        self.assertEqual(row["home_equity"], 350_000.0)
        self.assertEqual(row["total_net_worth"], 750_000.0)
        self.assertEqual(row["event_items"][0]["event_type"], "BuyHome")
        self.assertEqual(row["event_items"][0]["amount"], -100_000.0)
        self.assertIn("🏠 Indonesia Home Purchase", row["events_active"])


if __name__ == "__main__":
    unittest.main()
