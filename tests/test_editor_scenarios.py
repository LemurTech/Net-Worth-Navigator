import unittest
from pathlib import Path
from unittest.mock import patch

import admin_app
from src.scenarios import ScenarioRef


class EditorScenarioTests(unittest.TestCase):
    def test_current_scenario_uses_requested_slug(self):
        default = ScenarioRef(
            slug="default",
            name="Default Plan",
            description="Baseline",
            config_path=Path("scenarios/default.toml"),
            is_default=True,
        )
        alt = ScenarioRef(
            slug="alt",
            name="Alt Plan",
            description="Alternative",
            config_path=Path("scenarios/alt.toml"),
            is_default=False,
        )

        with patch("admin_app.get_scenario", side_effect=lambda slug=None: alt if slug == "alt" else default):
            self.assertEqual(admin_app._current_scenario("alt").slug, "alt")
            self.assertEqual(admin_app._config_path("alt"), Path("scenarios/alt.toml"))
            self.assertTrue(str(admin_app._backup_dir("alt")).endswith("config-backups\\alt"))

    def test_render_all_scenarios_runs_each_discovered_slug(self):
        default = ScenarioRef(
            slug="default",
            name="Default Plan",
            description="Baseline",
            config_path=Path("scenarios/default.toml"),
            is_default=True,
        )
        alt = ScenarioRef(
            slug="alt",
            name="Alt Plan",
            description="Alternative",
            config_path=Path("scenarios/alt.toml"),
            is_default=False,
        )

        calls = []

        class DummyResult:
            returncode = 0
            stdout = ""
            stderr = ""

        with patch("admin_app.discover_scenarios", return_value=[default, alt]), \
             patch("admin_app._render_projection_offline", side_effect=lambda slug=None: calls.append(slug) or DummyResult()):
            results = admin_app._render_all_scenarios()

        self.assertEqual(calls, ["default", "alt"])
        self.assertEqual(len(results), 2)
