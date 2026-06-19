import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.scenarios import ScenarioRef, discover_scenarios, write_scenarios_index


class ScenarioTests(unittest.TestCase):
    def test_discover_scenarios_falls_back_to_legacy_root_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.toml"
            config_path.write_text("[simulation]\nstart_year=2026\nend_year=2026\n", encoding="utf-8")

            with patch("src.scenarios.PROJECT_ROOT", root), \
                 patch("src.scenarios.CONFIG_PATH", config_path), \
                 patch("src.scenarios.SCENARIOS_DIR", root / "scenarios"):
                scenarios = discover_scenarios()

        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0].slug, "default")
        self.assertTrue(scenarios[0].is_default)

    def test_write_scenarios_index_uses_projection_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output" / "scenarios"
            output_root.mkdir(parents=True, exist_ok=True)
            scenario_output = output_root / "default"
            scenario_output.mkdir(parents=True, exist_ok=True)
            (scenario_output / "projection.html").write_text("<html></html>", encoding="utf-8")
            scenario = ScenarioRef(
                slug="default",
                name="Default Plan",
                description="Baseline scenario",
                config_path=Path(tmp) / "config.toml",
                is_default=True,
            )

            with patch("src.scenarios.discover_scenarios", return_value=[scenario]), \
                 patch("src.scenarios.get_default_scenario", return_value=scenario):
                index_path = write_scenarios_index(output_root=output_root)

            payload = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["default_slug"], "default")
        self.assertEqual(payload["scenarios"][0]["projection_path"], "scenarios/default/projection.html")
        self.assertEqual(payload["scenarios"][0]["name"], "Default Plan")
