"""Scenario discovery and manifest helpers for Net Worth Navigator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import tomllib

from src.config_loader import PROJECT_ROOT

SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
SCENARIO_OUTPUT_ROOT = PROJECT_ROOT / "output" / "scenarios"
SCENARIO_INDEX_JSON = "index.json"
AVAILABLE_RENDER_MODES = ("deterministic", "historical", "monte_carlo")
RENDER_MODE_LABELS = {
    "deterministic": "Deterministic",
    "historical": "Historical",
    "monte_carlo": "Monte Carlo",
}


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
        return []

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
    if not scenarios:
        raise FileNotFoundError(
            f"No scenario configs were found in {SCENARIOS_DIR}."
        )
    for scenario in scenarios:
        if scenario.is_default:
            return scenario
    return scenarios[0]


def get_scenario(slug: str | None = None) -> ScenarioRef:
    scenarios = discover_scenarios()
    if not scenarios:
        raise FileNotFoundError(
            f"No scenario configs were found in {SCENARIOS_DIR}."
        )
    if not slug:
        return get_default_scenario()
    normalized = _slugify(slug, "default")
    for scenario in scenarios:
        if scenario.slug == normalized:
            return scenario
    raise KeyError(f"Scenario '{slug}' not found.")


def scenario_output_dir(slug: str, mode: str | None = None) -> Path:
    base = SCENARIO_OUTPUT_ROOT / slug
    return base / mode if mode else base


def scenario_projection_relpath(slug: str, mode: str) -> str:
    return f"scenarios/{slug}/{mode}/projection.html"


def normalized_render_modes(raw_modes) -> list[str]:
    if not isinstance(raw_modes, list):
        return list(AVAILABLE_RENDER_MODES)
    normalized: list[str] = []
    for raw_mode in raw_modes:
        mode = str(raw_mode).strip().lower()
        if mode in AVAILABLE_RENDER_MODES and mode not in normalized:
            normalized.append(mode)
    if "deterministic" not in normalized:
        normalized.insert(0, "deterministic")
    return normalized or list(AVAILABLE_RENDER_MODES)


def scenario_path_for_slug(slug: str) -> Path:
    normalized = _slugify(slug, "scenario")
    return SCENARIOS_DIR / f"{normalized}.toml"


def _scenario_metadata_block(*, name: str, slug: str, description: str, is_default: bool = False) -> str:
    description = description.replace('"', '\\"')
    name = name.replace('"', '\\"')
    lines = [
        "[scenario]",
        f'name = "{name}"',
        f'slug = "{slug}"',
        f'description = "{description}"',
    ]
    if is_default:
        lines.append("is_default = true")
    return "\n".join(lines)


def materialize_scenario_content(
    source_content: str,
    *,
    name: str,
    slug: str,
    description: str,
    is_default: bool = False,
) -> str:
    normalized_slug = _slugify(slug, "scenario")
    metadata = _scenario_metadata_block(
        name=name,
        slug=normalized_slug,
        description=description,
        is_default=is_default,
    )
    stripped = re.sub(
        r"(?ms)^\[scenario\]\s*\n.*?(?=^\[[^\]]+\]|\Z)",
        "",
        source_content,
        count=1,
    ).lstrip()
    return f"{metadata}\n\n{stripped}"


def create_scenario_from_content(
    source_content: str,
    *,
    name: str,
    slug: str,
    description: str,
) -> ScenarioRef:
    normalized_slug = _slugify(slug, "scenario")
    if not name.strip():
        raise ValueError("Scenario name is required.")
    target_path = scenario_path_for_slug(normalized_slug)
    if target_path.exists():
        raise ValueError(f"Scenario '{normalized_slug}' already exists.")

    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    target_content = materialize_scenario_content(
        source_content,
        name=name.strip(),
        slug=normalized_slug,
        description=description.strip(),
        is_default=False,
    )
    target_path.write_text(target_content, encoding="utf-8")
    return ScenarioRef(
        slug=normalized_slug,
        name=name.strip(),
        description=description.strip(),
        config_path=target_path,
        is_default=False,
    )


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
        scenario_dir = output_root / scenario.slug
        mode_entries = []
        for mode in AVAILABLE_RENDER_MODES:
            projection_path = scenario_dir / mode / "projection.html"
            if not projection_path.exists():
                continue
            mode_entries.append(
                {
                    "mode": mode,
                    "label": RENDER_MODE_LABELS.get(mode, mode.replace("_", " ").title()),
                    "projection_path": scenario_projection_relpath(scenario.slug, mode),
                    "rendered_at": datetime.fromtimestamp(projection_path.stat().st_mtime).isoformat(),
                }
            )
        default_mode = "deterministic" if any(entry["mode"] == "deterministic" for entry in mode_entries) else (
            mode_entries[0]["mode"] if mode_entries else None
        )
        payload["scenarios"].append(
            {
                "slug": scenario.slug,
                "name": scenario.name,
                "description": scenario.description,
                "config_path": _display_config_path(scenario.config_path),
                "projection_path": scenario_projection_relpath(scenario.slug, default_mode) if default_mode else None,
                "rendered_at": next((entry["rendered_at"] for entry in mode_entries if entry["mode"] == default_mode), None),
                "default_mode": default_mode,
                "modes": mode_entries,
                "is_default": scenario.is_default,
            }
        )

    index_path = output_root / SCENARIO_INDEX_JSON
    index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return index_path
