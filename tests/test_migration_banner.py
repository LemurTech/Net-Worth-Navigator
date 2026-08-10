"""Tests for v1→v2 migration detection and the Setup Panel migration banner."""

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import admin_app


class _FakeRequest:
    def __init__(self, slug: str | None = None):
        self.query_params = {"scenario": slug} if slug else {}


class MigrationStatusTests(unittest.TestCase):
    def _v1_doc(self):
        return {
            "scenario": {"name": "V1 Scratch"},
            "person1": {
                "name": "Test",
                "dob": "1970-01-01",
                "retirement_year": 2035,
                "ss_start_age": 67,
                "life_expectancy": 90,
            },
        }

    def test_detects_v1_fields_without_events(self):
        needed, items = admin_app._migration_status(self._v1_doc())
        self.assertTrue(needed)
        self.assertEqual(len(items), 3)
        self.assertIn("Person 1 — Retirement", items)
        self.assertIn("Person 1 — Social Security", items)
        self.assertIn("Person 1 — End of Plan", items)

    def test_clean_when_events_exist(self):
        doc = self._v1_doc()
        doc["events"] = [
            {"type": "Retire", "person": "person1", "year": 2035},
            {"type": "SocialSecurity", "person": "person1", "year": 2037},
            {"type": "EndOfPlan", "person": "person1", "year": 2060},
        ]
        needed, items = admin_app._migration_status(doc)
        self.assertFalse(needed)
        self.assertEqual(items, [])

    def test_partial_migration_lists_only_missing(self):
        doc = self._v1_doc()
        doc["events"] = [{"type": "Retire", "person": "person1", "year": 2035}]
        needed, items = admin_app._migration_status(doc)
        self.assertTrue(needed)
        self.assertEqual(items, ["Person 1 — Social Security", "Person 1 — End of Plan"])

    def test_skips_absent_person2(self):
        needed, items = admin_app._migration_status(self._v1_doc())
        self.assertTrue(needed)
        self.assertFalse(any("Person 2" in item for item in items))

    def test_endpoint_returns_flags(self):
        with patch.object(admin_app, "_toml_open", return_value=(self._v1_doc(), None)):
            response = asyncio.run(admin_app.api_migration_status(_FakeRequest("v1scratch")))
        data = json.loads(response.body)
        self.assertTrue(data["ok"])
        self.assertTrue(data["migration_needed"])
        self.assertEqual(len(data["items"]), 3)

    def test_endpoint_clean_when_migrated(self):
        doc = {
            "scenario": {"name": "Migrated"},
            "person1": {"name": "Test", "dob": "1970-01-01"},
            "events": [{"type": "Retire", "person": "person1", "year": 2035}],
        }
        with patch.object(admin_app, "_toml_open", return_value=(doc, None)):
            response = asyncio.run(admin_app.api_migration_status(_FakeRequest("migrated")))
        data = json.loads(response.body)
        self.assertTrue(data["ok"])
        self.assertFalse(data["migration_needed"])
        self.assertEqual(data["items"], [])

    def test_events_endpoint_keeps_flags(self):
        with patch.object(admin_app, "_toml_open", return_value=(self._v1_doc(), None)):
            response = asyncio.run(admin_app.api_list_events(_FakeRequest("v1scratch")))
        data = json.loads(response.body)
        self.assertTrue(data["ok"])
        self.assertTrue(data["migration_needed"])
        self.assertEqual(len(data["migration_items"]), 3)


class MigrateBannerTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = Path("templates/setup_panel.html").read_text(encoding="utf-8")

    def test_banner_markup_and_link_present(self):
        self.assertIn('class="migrate-banner" id="migrate-banner"', self.template)
        self.assertIn('id="migrate-banner-items"', self.template)
        self.assertIn("guides/migrating-to-v2", self.template)

    def test_banner_fetch_and_init_present(self):
        self.assertIn("api/migration-status", self.template)
        self.assertIn("function initMigrationBanner", self.template)
        self.assertIn("initMigrationBanner()", self.template)

    def test_banner_css_present(self):
        self.assertIn(".migrate-banner", self.template)


if __name__ == "__main__":
    unittest.main()
