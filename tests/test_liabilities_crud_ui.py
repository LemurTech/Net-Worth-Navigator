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

[synthetic_start]
taxable = 10000

[synthetic_start.liability_balances]
"Home Mortgage" = 280000

[[liabilities]]
name = "Home Mortgage"
annual_rate = 0.0575
monthly_base = 2163
monthly_escrow = 494.54
monthly_extra = 200
type = "mortgage"

[[liabilities]]
name = "Auto Loan"
annual_rate = 0.065
monthly_base = 550
type = "auto"
"""


def _fake_backup_and_write(config_path):
    def _write(doc, scenario_slug=None):
        config_path.write_text(doc.as_string(), encoding="utf-8")
        return config_path
    return _write


class ListLiabilitiesTests(unittest.TestCase):
    def test_returns_all_liabilities_with_index(self):
        with patch("admin_app._read_config_text", return_value=SAMPLE_TOML):
            response = asyncio.run(admin_app.api_list_liabilities(_FakeRequest()))

        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["liabilities"]), 2)
        self.assertEqual(body["liabilities"][0]["name"], "Home Mortgage")
        self.assertEqual(body["liabilities"][0]["index"], 0)
        self.assertEqual(body["liabilities"][1]["name"], "Auto Loan")
        self.assertEqual(body["liabilities"][1]["index"], 1)


class AddLiabilityTests(unittest.TestCase):
    def test_adds_new_liability(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_add_liability(_FakeRequest(json_body={
                    "name": "Student Loan",
                    "type": "other",
                    "annual_rate": 0.045,
                    "monthly_base": 300,
                })))

            body = json.loads(response.body)
            self.assertTrue(body["ok"])
            self.assertEqual(body["index"], 2)

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(len(parsed["liabilities"]), 3)
            self.assertEqual(parsed["liabilities"][2]["name"], "Student Loan")
            self.assertEqual(parsed["liabilities"][2]["monthly_base"], 300)

    def test_rejects_duplicate_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_add_liability(_FakeRequest(json_body={
                    "name": "Home Mortgage",
                    "annual_rate": 0.05,
                    "monthly_base": 1000,
                })))

            body = json.loads(response.body)
            self.assertFalse(body["ok"])
            self.assertIn("already exists", body["error"])

    def test_rejects_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_add_liability(_FakeRequest(json_body={"name": "New Loan"})))

            body = json.loads(response.body)
            self.assertFalse(body["ok"])
            self.assertIn("annual_rate", body["error"])
            self.assertIn("monthly_base", body["error"])

    def test_rejects_invalid_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_add_liability(_FakeRequest(json_body={
                    "name": "New Loan", "annual_rate": 0.05, "monthly_base": 500, "type": "boat",
                })))

            body = json.loads(response.body)
            self.assertFalse(body["ok"])
            self.assertIn("type must be one of", body["error"])


class UpdateLiabilityTests(unittest.TestCase):
    def test_rename_migrates_matching_balance_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_update_liability(_FakeRequest(json_body={
                    "index": 0,
                    "name": "Primary Mortgage",
                    "annual_rate": 0.0575,
                    "monthly_base": 2163,
                    "type": "mortgage",
                })))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["liabilities"][0]["name"], "Primary Mortgage")
            balances = parsed["synthetic_start"]["liability_balances"]
            self.assertNotIn("Home Mortgage", balances)
            self.assertEqual(balances["Primary Mortgage"], 280000)

    def test_rejects_rename_colliding_with_another_liability(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_update_liability(_FakeRequest(json_body={
                    "index": 0,
                    "name": "Auto Loan",
                    "annual_rate": 0.0575,
                    "monthly_base": 2163,
                })))

            body = json.loads(response.body)
            self.assertFalse(body["ok"])
            self.assertIn("already exists", body["error"])

    def test_keeping_same_name_is_not_treated_as_a_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_update_liability(_FakeRequest(json_body={
                    "index": 0,
                    "name": "Home Mortgage",
                    "annual_rate": 0.06,
                    "monthly_base": 2200,
                })))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["liabilities"][0]["annual_rate"], 0.06)


class DeleteLiabilityTests(unittest.TestCase):
    def test_delete_removes_definition_and_matching_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_delete_liability(_FakeRequest(json_body={"index": 0})))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(len(parsed["liabilities"]), 1)
            self.assertEqual(parsed["liabilities"][0]["name"], "Auto Loan")
            self.assertNotIn("Home Mortgage", parsed["synthetic_start"]["liability_balances"])

    def test_delete_at_invalid_index_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_delete_liability(_FakeRequest(json_body={"index": 99})))

            body = json.loads(response.body)
            self.assertFalse(body["ok"])
