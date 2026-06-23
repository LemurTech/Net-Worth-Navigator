import json
import tempfile
import unittest
from pathlib import Path

from src.scenario_shell import build_scenario_shell


class ScenarioShellTests(unittest.TestCase):
    def test_build_scenario_shell_writes_manifest_backed_selector_page(self):
        manifest = {
            "generated_at": "2026-06-19T13:00:00",
            "default_slug": "default",
            "scenarios": [
                {
                    "slug": "default",
                    "name": "Default Plan",
                    "description": "Baseline scenario",
                    "projection_path": "scenarios/default/deterministic/projection.html",
                    "rendered_at": "2026-06-19T13:00:00",
                    "default_mode": "deterministic",
                    "modes": [
                        {
                            "mode": "deterministic",
                            "label": "Deterministic",
                            "projection_path": "scenarios/default/deterministic/projection.html",
                            "rendered_at": "2026-06-19T13:00:00",
                        },
                        {
                            "mode": "monte_carlo",
                            "label": "Monte Carlo",
                            "projection_path": "scenarios/default/monte_carlo/projection.html",
                            "rendered_at": "2026-06-19T13:05:00",
                        },
                    ],
                    "is_default": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "projection.html"
            build_scenario_shell(
                manifest=manifest,
                output_path=output_path,
                manifest_relpath="scenarios/index.json",
                editor_url="/finances/config/",
            )
            html = output_path.read_text(encoding="utf-8")

        self.assertIn("Net Worth Navigator", html)
        self.assertIn("scenarios/index.json", html)
        self.assertIn("scenarios/default/deterministic/projection.html", html)
        self.assertIn("mode-select", html)
        self.assertIn('url.searchParams.set("mode", mode);', html)
        self.assertIn("modeEntryFor", html)
        self.assertIn(json.dumps(manifest), html)
        self.assertIn("scenario-select", html)
        self.assertIn("edit-scenarios-link", html)
        self.assertIn('url.searchParams.set("scenario", slug);', html)
        self.assertIn('editScenariosLink.href = editorUrlFor(selected);', html)
