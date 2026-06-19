"""Scenario discovery and manifest helpers for Net Worth Navigator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import tomllib

from src.config_loader import CONFIG_PATH, PROJECT_ROOT

SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
SCENARIO_OUTPUT_ROOT = PROJECT_ROOT / "output" / "scenarios"
SCENARIO_INDEX_JSON = "index.json"


@dataclass(frozen=True)
class ScenarioRef:
    slug: str
    name: str
    description: str
    config_path: Path
    is_default: bool


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def _load_metadata(path: Path) -> dict:
    with open(path, "rb") as handle:
        parsed = tomllib.load(handle)
    return dict(parsed.get("scenario", {})) if isinstance(parsed, dict) else {}


def discover_scenarios() -> list[ScenarioRef]:
    scenario_files = sorted(SCENARIOS_DIR.glob("*.toml")) if SCENARIOS_DIR.exists() else []
    if not scenario_files:
        return [
            ScenarioRef(
                slug="default",
                name="Default Plan",
                description="Legacy root config scenario.",
                config_path=CONFIG_PATH,
                is_default=True,
            )
        ]

    scenarios: list[ScenarioRef] = []
    for path in scenario_files:
        metadata = _load_metadata(path)
        stem = path.stem
        slug = _slugify(str(metadata.get("slug", stem)), stem)
        name = str(metadata.get("name", stem.replace("-", " ").title()))
        description = str(metadata.get("description", "")).strip()
        is_default = bool(metadata.get("is_default", False))
        scenarios.append(
            ScenarioRef(
                slug=slug,
                name=name,
                description=description,
                config_path=path,
                is_default=is_default,
            )
        )

    if not any(s.is_default for s in scenarios):
        scenarios = [
            ScenarioRef(
                slug=s.slug,
                name=s.name,
                description=s.description,
                config_path=s.config_path,
                is_default=(s.slug == "default" or i == 0),
            )
            for i, s in enumerate(scenarios)
        ]
    return scenarios


def get_default_scenario() -> ScenarioRef:
    scenarios = discover_scenarios()
    for scenario in scenarios:
        if scenario.is_default:
            return scenario
    return scenarios[0]


def get_scenario(slug: str | None = None) -> ScenarioRef:
    scenarios = discover_scenarios()
    if not slug:
        return get_default_scenario()
    normalized = _slugify(slug, "default")
    for scenario in scenarios:
        if scenario.slug == normalized:
            return scenario
    raise KeyError(f"Scenario '{slug}' not found.")


def scenario_output_dir(slug: str) -> Path:
    return SCENARIO_OUTPUT_ROOT / slug


def scenario_projection_relpath(slug: str) -> str:
    return f"scenarios/{slug}/projection.html"


def _display_config_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def write_scenarios_index(*, output_root: Path | None = None) -> Path:
    output_root = output_root or SCENARIO_OUTPUT_ROOT
    output_root.mkdir(parents=True, exist_ok=True)
    scenarios = discover_scenarios()
    generated_at = datetime.now().isoformat()
    default_slug = get_default_scenario().slug

    payload = {
        "generated_at": generated_at,
        "default_slug": default_slug,
        "scenarios": [],
    }
    for scenario in scenarios:
        projection_path = output_root / scenario.slug / "projection.html"
        payload["scenarios"].append(
            {
                "slug": scenario.slug,
                "name": scenario.name,
                "description": scenario.description,
                "config_path": _display_config_path(scenario.config_path),
                "projection_path": scenario_projection_relpath(scenario.slug),
                "rendered_at": (
                    datetime.fromtimestamp(projection_path.stat().st_mtime).isoformat()
                    if projection_path.exists()
                    else None
                ),
                "is_default": scenario.is_default,
            }
        )

    index_path = output_root / SCENARIO_INDEX_JSON
    index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return index_path
