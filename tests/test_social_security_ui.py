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

[person1]
name = "Alex"
dob = "1975-01-01"
ss_start_age = 67
survivor_ss_start_age = 60

[person1.social_security_benefits]
62 = 1400
67 = 2020

[person2]
name = "Sam"
dob = "1977-01-01"
"""


def _fake_backup_and_write(config_path):
    def _write(doc, scenario_slug=None):
        config_path.write_text(doc.as_string(), encoding="utf-8")
        return config_path
    return _write


class QuickControlMapTests(unittest.TestCase):
    def test_social_security_scalar_fields_are_registered(self):
        expected = {
            "person1_ss_start_age": ("person1.ss_start_age", int),
            "person2_ss_start_age": ("person2.ss_start_age", int),
            "person1_survivor_ss_start_age": ("person1.survivor_ss_start_age", int),
            "person2_survivor_ss_start_age": ("person2.survivor_ss_start_age", int),
            "person1_ss_monthly_benefit": ("person1.ss_monthly_benefit", float),
            "person2_ss_monthly_benefit": ("person2.ss_monthly_benefit", float),
        }
        for field, spec in expected.items():
            self.assertEqual(admin_app._QUICK_CONTROL_MAP[field], spec)


class SocialSecurityGetEndpointTests(unittest.TestCase):
    def test_returns_benefits_table_and_scalar_fields_per_person(self):
        with patch("admin_app._read_config_text", return_value=SAMPLE_TOML):
            response = asyncio.run(admin_app.api_social_security(_FakeRequest()))

        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual(body["person1"]["benefits"], {"62": 1400, "67": 2020})
        self.assertEqual(body["person1"]["ss_start_age"], 67)
        self.assertEqual(body["person1"]["survivor_ss_start_age"], 60)
        self.assertEqual(body["person2"]["benefits"], {})
        self.assertIsNone(body["person2"]["ss_start_age"])


class SocialSecuritySaveEndpointTests(unittest.TestCase):
    def test_single_household_ignores_person2_benefits_without_creating_table(self):
        single_toml = SAMPLE_TOML.replace(
            '[person2]\nname = "Sam"\ndob = "1977-01-01"\n',
            '',
        ).replace('slug = "test"', 'slug = "test"\nhousehold_type = "single"')
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(single_toml, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                response = asyncio.run(admin_app.api_save_social_security(_FakeRequest(json_body={
                    "person1": {"67": 2200},
                    "person2": {"67": 1800},
                })))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["person1"]["social_security_benefits"], {"67": 2200})
            self.assertNotIn("person2", parsed)

    def test_whole_table_replace_writes_both_persons_and_sorts_by_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                request = _FakeRequest(json_body={
                    "person1": {"70": 3000, "62": 1500},
                    "person2": {"65": 1800},
                })
                response = asyncio.run(admin_app.api_save_social_security(request))

            body = json.loads(response.body)
            self.assertTrue(body["ok"])

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["person1"]["social_security_benefits"], {"62": 1500, "70": 3000})
            self.assertEqual(parsed["person2"]["social_security_benefits"], {"65": 1800})

    def test_empty_benefits_clears_existing_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                request = _FakeRequest(json_body={"person1": {}})
                response = asyncio.run(admin_app.api_save_social_security(request))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("social_security_benefits", parsed.get("person1", {}))

    def test_non_positive_and_non_numeric_entries_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test.toml"
            config_path.write_text(SAMPLE_TOML, encoding="utf-8")

            with patch("admin_app._config_path", return_value=config_path), \
                 patch("admin_app._backup_and_write_toml", side_effect=_fake_backup_and_write(config_path)):
                request = _FakeRequest(json_body={
                    "person1": {"62": 1400, "63": 0, "64": -500, "not_an_age": 900},
                })
                response = asyncio.run(admin_app.api_save_social_security(request))

            self.assertTrue(json.loads(response.body)["ok"])
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["person1"]["social_security_benefits"], {"62": 1400})
