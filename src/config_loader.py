"""Shared config loading utilities for Net Worth Navigator."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "scenarios" / "default.toml"
TAX_TABLES_DIR = PROJECT_ROOT / "config" / "tax_tables"


def load_raw_toml(path: Path) -> dict:
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def deep_merge(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def merge_tax_tables(config: dict) -> dict:
    taxes = dict(config.get("taxes", {}))
    table_set = str(taxes.get("table_set", "")).strip()
    if not table_set:
        return deepcopy(config)

    table_path = TAX_TABLES_DIR / f"{table_set}.toml"
    if not table_path.exists():
        raise FileNotFoundError(
            f"Tax table set '{table_set}' not found at {table_path}"
        )

    table_data = load_raw_toml(table_path)
    shared_taxes = table_data.get("taxes")
    if not isinstance(shared_taxes, dict):
        raise ValueError(
            f"Tax table file {table_path} must define a [taxes] table."
        )

    merged = deepcopy(config)
    merged["taxes"] = deep_merge(shared_taxes, taxes)
    return merged


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or CONFIG_PATH
    return merge_tax_tables(load_raw_toml(path))
