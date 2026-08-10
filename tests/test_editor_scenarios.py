import os
import asyncio
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import admin_app
from src.scenarios import ScenarioRef


class _FakeJsonRequest:
    def __init__(self, scenario_slug: str, body: dict):
        self.query_params = {"scenario": scenario_slug}
        self._body = body

    async def json(self):
        return self._body


class EditorScenarioTests(unittest.TestCase):
    def test_sample_render_job_rebuilds_without_writing_config(self):
        sample = ScenarioRef(
            slug="sample",
            name="Sample",
            description="Bundled demo",
            config_path=Path("scenarios/sample.toml"),
            is_default=False,
        )
        request = SimpleNamespace(base_url="http://testserver/")
        response_payload = admin_app.JSONResponse({"ok": True, "job_id": "render-job"})

        with patch("admin_app._parse_form", AsyncMock(return_value={
            "action": "save_render",
            "content": "[scenario]\nname = 'attempted edit'\n",
            "scenario_slug": "sample",
        })), \
             patch("admin_app._current_scenario", return_value=sample), \
             patch("admin_app._start_render_job_response", return_value=response_payload) as start_job, \
             patch("admin_app._backup_and_write") as backup:
            response = asyncio.run(admin_app.start_render_job(request))

        self.assertIs(response, response_payload)
        backup.assert_not_called()
        self.assertEqual(start_job.call_args.kwargs["action"], "render")
        self.assertIsNone(start_job.call_args.kwargs["backup_path"])

    def test_sample_scenario_writes_are_refused(self):
        sample = ScenarioRef(
            slug="sample-a",
            name="Sample A",
            description="Bundled demo",
            config_path=Path("scenarios/sample-a.toml"),
            is_default=False,
        )
        request = _FakeJsonRequest("sample-a", {"scenario_name": "Changed"})

        with patch("admin_app._current_scenario", return_value=sample):
            response = asyncio.run(admin_app.api_save_quick_controls(request))

        self.assertEqual(response.status_code, 403)
        body = json.loads(response.body)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], admin_app._SAMPLE_READ_ONLY_MESSAGE)

    def test_sample_prefix_is_case_insensitive(self):
        sample = ScenarioRef(
            slug="Sample-Couples",
            name="Sample Couples",
            description="Bundled demo",
            config_path=Path("scenarios/sample-couples.toml"),
            is_default=False,
        )
        with patch("admin_app._current_scenario", return_value=sample):
            self.assertTrue(admin_app._scenario_is_read_only("Sample-Couples"))

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
