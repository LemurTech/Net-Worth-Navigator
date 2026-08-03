import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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
            self.assertTrue(str(admin_app._backup_dir("alt")).endswith(str(Path("config-backups") / "alt")))

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

    def test_prune_backups_removes_stale_backups_keeps_recent(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "config-backups" / "default"
            backup_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()

            for index in range(10):
                path = backup_dir / f"config-recent-{index:02d}.toml"
                path.write_text(f"recent {index}", encoding="utf-8")
                timestamp = (now - timedelta(minutes=10 - index)).timestamp()
                os.utime(path, (timestamp, timestamp))

            stale_paths = []
            for index in range(2):
                path = backup_dir / f"config-stale-{index:02d}.toml"
                path.write_text(f"stale {index}", encoding="utf-8")
                timestamp = (now - timedelta(days=30 + index)).timestamp()
                os.utime(path, (timestamp, timestamp))
                stale_paths.append(path)

            admin_app._prune_backups(backup_dir)

            remaining = sorted(path.name for path in backup_dir.glob("config-*.toml"))
            # Time-based retention (14 days): stale backups removed, recent kept
            self.assertEqual(len(remaining), 10)
            self.assertNotIn(stale_paths[0].name, remaining)
            self.assertNotIn(stale_paths[1].name, remaining)

    def test_build_context_uses_scenario_specific_projection_and_editor_urls(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            default_path = tmp_path / "default.toml"
            alt_path = tmp_path / "alt.toml"
            default_path.write_text("[scenario]\nname='Default'\n", encoding="utf-8")
            alt_path.write_text("[scenario]\nname='Alt'\n", encoding="utf-8")

            default = ScenarioRef(
                slug="default",
                name="Default Plan",
                description="Baseline",
                config_path=default_path,
                is_default=True,
            )
            alt = ScenarioRef(
                slug="alt",
                name="Alt Plan",
                description="Alternative",
                config_path=alt_path,
                is_default=False,
            )

            with patch("admin_app._current_scenario", side_effect=lambda slug=None: alt if slug == "alt" else default), \
                 patch("admin_app.discover_scenarios", return_value=[default, alt]):
                context = admin_app._build_context(
                    SimpleNamespace(base_url="http://testserver/"),
                    content="[scenario]\nname='Alt'\n",
                    scenario_slug="alt",
                    last_action="save",
                )

        self.assertTrue(context["projection_url"].endswith("?scenario=alt"))
        self.assertTrue(context["editor_url"].endswith("?scenario=alt"))
        self.assertIn('"current_scenario_slug": "alt"', context["render_plan_json"])
        self.assertIn('"current_render_count": 3', context["render_plan_json"])
        self.assertEqual(context["last_action"], "save")
