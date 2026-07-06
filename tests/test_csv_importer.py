"""Tests for src.csv_importer — CSV parsing, merge, and build-starting-inputs."""

import tempfile
import unittest
from pathlib import Path

from src.csv_importer import (
    accounts_from_csv,
    build_csv_starting_inputs,
    merge_accounts,
    parse_csv,
)


def _write_csv(lines: list[str]) -> str:
    """Write CSV lines to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8")
    for line in lines:
        tmp.write(line + "\n")
    tmp.close()
    return tmp.name


class ParseCsvTests(unittest.TestCase):
    """parse_csv() — column detection, date parsing, grouping, edge cases."""

    def test_basic_monarch_format(self):
        lines = [
            "Date,Balance,Account",
            '2026-01-05,5432.10,"Checking - Joint"',
            '2026-01-05,12345.67,"Savings - Joint"',
            '2026-01-05,55000.00,"Vanguard Roth IRA"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 3)

        by_name = {e["name"]: e for e in result}
        self.assertAlmostEqual(by_name["Checking - Joint"]["balance"], 5432.10)
        self.assertEqual(by_name["Checking - Joint"]["date"], "2026-01-05")

    def test_latest_date_per_account(self):
        """Multiple rows for the same account — keep the latest date's balance."""
        lines = [
            "Date,Balance,Account",
            '2026-01-01,1000.00,"Checking"',
            '2026-03-15,1500.00,"Checking"',
            '2026-06-01,1200.00,"Checking"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["balance"], 1200.00)
        self.assertEqual(result[0]["date"], "2026-06-01")

    def test_negative_balance_preserved(self):
        """Debts/credit cards come through as negative values, matching Monarch API."""
        lines = [
            "Date,Balance,Account",
            '2026-01-05,-2500.00,"Capital One Card"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["balance"], -2500.00)

    def test_multiple_date_formats(self):
        lines = [
            "Date,Balance,Account",
            '01/15/2026,3000.00,"Checking"',
            '2026/06/01,4000.00,"Savings"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 2)

    def test_empty_csv_raises(self):
        path = _write_csv(["Date,Balance,Account"])
        with self.assertRaises(ValueError) as ctx:
            parse_csv(path)
        self.assertIn("No parseable account", str(ctx.exception))

    def test_no_data_rows_raises(self):
        path = _write_csv([
            "Date,Balance,Account",
            ",,",
        ])
        with self.assertRaises(ValueError) as ctx:
            parse_csv(path)
        self.assertIn("No parseable account", str(ctx.exception))

    def test_missing_columns_raises(self):
        path = _write_csv(["Name,Value"])
        with self.assertRaises(ValueError) as ctx:
            parse_csv(path)
        self.assertIn("must have columns", str(ctx.exception))

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_csv("/nonexistent/path.csv")

    def test_utf8_bom_stripped(self):
        """UTF-8 BOM prefix on the first line should be handled."""
        lines = [
            '\ufeffDate,Balance,Account',
            '2026-01-05,100.00,"Acct"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 1)

    def test_deterministic_sorting(self):
        """Results sorted alphabetically by account name."""
        lines = [
            "Date,Balance,Account",
            '2026-01-05,300.00,"Zed"',
            '2026-01-05,100.00,"Alpha"',
            '2026-01-05,200.00,"Beta"',
        ]
        path = _write_csv(lines)
        result = parse_csv(path)
        names = [e["name"] for e in result]
        self.assertEqual(names, ["Alpha", "Beta", "Zed"])

    def test_large_csv(self):
        """Should handle hundreds of rows without issue."""
        lines = ["Date,Balance,Account"]
        for i in range(500):
            lines.append(f'2026-01-01,{i * 100}.00,"Account {i % 10}"')
        path = _write_csv(lines)
        result = parse_csv(path)
        self.assertEqual(len(result), 10)
        # Account 0 gets rows 0, 10, 20...500 — row 490 is last (value 49000)
        acct0 = next(e for e in result if e["name"] == "Account 0")
        self.assertAlmostEqual(acct0["balance"], 49000.00)


class AccountsFromCsvTests(unittest.TestCase):
    """accounts_from_csv() convenience wrapper."""

    def test_basic(self):
        lines = [
            "Date,Balance,Account",
            '2026-01-05,5432.10,"Checking"',
            '2026-01-05,12345.00,"Savings"',
        ]
        result = accounts_from_csv(_write_csv(lines))
        self.assertEqual(result, {"Checking": 5432.10, "Savings": 12345.00})


class MergeAccountsTests(unittest.TestCase):
    """merge_accounts() — new, updated, removed detection."""

    def test_all_updated(self):
        old = {"Checking": 1000.0, "Savings": 5000.0}
        new = [
            {"name": "Checking", "balance": 1200.0, "date": "2026-06-01"},
            {"name": "Savings", "balance": 5500.0, "date": "2026-06-01"},
        ]
        cls = {"Checking": "cash", "Savings": "cash"}
        result = merge_accounts(old, new, cls)
        self.assertEqual(len(result["updated"]), 2)
        self.assertEqual(len(result["new"]), 0)
        self.assertEqual(len(result["maybe_removed"]), 0)

    def test_new_and_updated(self):
        old = {"Checking": 1000.0}
        new = [
            {"name": "Checking", "balance": 1200.0, "date": "2026-06-01"},
            {"name": "New Account", "balance": 500.0, "date": "2026-06-01"},
        ]
        cls = {"Checking": "cash"}
        result = merge_accounts(old, new, cls)
        self.assertEqual(len(result["updated"]), 1)
        self.assertEqual(len(result["new"]), 1)
        self.assertEqual(result["new"][0]["name"], "New Account")
        self.assertIsNone(result["new"][0]["category"])

    def test_removed_detected(self):
        old = {"Checking": 1000.0, "Closed Account": 0.0}
        new = [
            {"name": "Checking", "balance": 1200.0, "date": "2026-06-01"},
        ]
        cls = {"Checking": "cash", "Closed Account": "ignore"}
        result = merge_accounts(old, new, cls)
        self.assertEqual(len(result["maybe_removed"]), 1)
        self.assertEqual(result["maybe_removed"][0]["name"], "Closed Account")
        self.assertEqual(result["maybe_removed"][0]["category"], "ignore")

    def test_same_accounts_no_changes(self):
        old = {"Checking": 1000.0, "Savings": 5000.0}
        new = [
            {"name": "Checking", "balance": 1000.0, "date": "2026-06-01"},
            {"name": "Savings", "balance": 5000.0, "date": "2026-06-01"},
        ]
        cls = {"Checking": "cash", "Savings": "cash"}
        result = merge_accounts(old, new, cls)
        self.assertEqual(len(result["updated"]), 2)
        self.assertEqual(len(result["new"]), 0)
        self.assertEqual(len(result["maybe_removed"]), 0)

    def test_classification_preserved_with_dict(self):
        """Inline dict classifications ({category, owner}) survive the merge."""
        old = {"Roth Account": 50000.0}
        new = [
            {"name": "Roth Account", "balance": 55000.0, "date": "2026-06-01"},
        ]
        cls = {"Roth Account": {"category": "roth", "owner": "person1"}}
        result = merge_accounts(old, new, cls)
        self.assertEqual(len(result["updated"]), 1)
        self.assertEqual(result["updated"][0]["category"], "roth")
        self.assertEqual(result["updated"][0]["owner"], "person1")


class BuildCsvStartingInputsTests(unittest.TestCase):
    """build_csv_starting_inputs() — integration with monarch_bridge classification."""

    def test_basic_classification(self):
        """Simple cash accounts are classified into the cash bucket."""
        config = {
            "csv_source": {
                "accounts": {
                    "Checking": 5432.10,
                    "Savings": 12345.00,
                },
            },
            "accounts": {
                "Checking": "cash",
                "Savings": "cash",
            },
        }
        portfolio, extras, liability_balances, properties, owner_seeds, basis = (
            build_csv_starting_inputs(config)
        )
        self.assertAlmostEqual(portfolio["cash"], 5432.10 + 12345.00)

    def test_mixed_by_category(self):
        """Different account types route to correct buckets."""
        config = {
            "csv_source": {
                "accounts": {
                    "Checking": 5000.00,
                    "Vanguard Roth": 55000.00,
                    "Vanguard Trad": 250000.00,
                    "Home": 380000.00,
                },
            },
            "accounts": {
                "Checking": "cash",
                "Vanguard Roth": {"category": "roth", "owner": "person1"},
                "Vanguard Trad": {"category": "trad_ira", "owner": "person1"},
                "Home": "real_estate",
            },
        }
        portfolio, extras, liability_balances, properties, owner_seeds, basis = (
            build_csv_starting_inputs(config)
        )
        self.assertAlmostEqual(portfolio["cash"], 5000.00)
        self.assertAlmostEqual(portfolio["roth"], 55000.00)
        self.assertAlmostEqual(portfolio["trad_ira"], 250000.00)
        self.assertAlmostEqual(extras["home_value"], 380000.00)

    def test_liability_excluded_from_portfolio(self):
        """Liability-classified accounts are excluded from portfolio."""
        config = {
            "csv_source": {
                "accounts": {
                    "Checking": 5000.00,
                    "Mortgage": -280000.00,
                },
            },
            "accounts": {
                "Checking": "cash",
                "Mortgage": "liability",
            },
        }
        portfolio, extras, liability_balances, properties, owner_seeds, basis = (
            build_csv_starting_inputs(config)
        )
        self.assertAlmostEqual(portfolio["cash"], 5000.00)
        # Liability excluded from investable
        self.assertAlmostEqual(sum(portfolio.values()), 5000.00)

    def test_disabled_accounts_excluded(self):
        """Disabled accounts are excluded from balance calculation."""
        config = {
            "csv_source": {
                "accounts": {
                    "Checking": 5000.00,
                    "Old Card": 100.00,
                },
            },
            "accounts": {
                "Checking": "cash",
                "Old Card": "ignore",
                "disabled": ["Old Card"],
            },
        }
        portfolio, extras, liability_balances, properties, owner_seeds, basis = (
            build_csv_starting_inputs(config)
        )
        self.assertAlmostEqual(portfolio["cash"], 5000.00)

    def test_empty_csv_source(self):
        """No csv_source section produces all-zero balances."""
        config = {}
        portfolio, extras, liability_balances, properties, owner_seeds, basis = (
            build_csv_starting_inputs(config)
        )
        self.assertEqual(sum(portfolio.values()), 0.0)
        self.assertEqual(sum(extras.values()), 0.0)

    def test_property_values_from_classification(self):
        """Named real_estate accounts return their actual account name, not a synthetic fallback."""
        config = {
            "csv_source": {
                "accounts": {
                    "Home": 380000.00,
                },
            },
            "accounts": {
                "Home": "real_estate",
            },
        }
        *_, properties, _, _ = build_csv_starting_inputs(config)
        self.assertEqual(properties, {"Home": 380000.00})

    def test_owner_balances_extracted(self):
        """Owner-attributed retirement accounts populate owner_seeds correctly."""
        config = {
            "csv_source": {
                "accounts": {
                    "My Roth": 50000.00,
                    "Spouse Roth": 30000.00,
                },
            },
            "accounts": {
                "My Roth": {"category": "roth", "owner": "person1"},
                "Spouse Roth": {"category": "roth", "owner": "person2"},
            },
            "person1": {"name": "Alex"},
            "person2": {"name": "Sam"},
        }
        *_, owner_seeds, _ = build_csv_starting_inputs(config)
        self.assertIn("roth", owner_seeds)
        self.assertAlmostEqual(owner_seeds["roth"]["person1"], 50000.00)
        self.assertAlmostEqual(owner_seeds["roth"]["person2"], 30000.00)


if __name__ == "__main__":
    unittest.main()
