"""sidecars.py — write analysis-friendly output files for Net Worth Navigator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.model import resolve_runtime_config
from src.scenarios import ScenarioRef


PROJECTION_CSV = "projection_yearly.csv"
EVENT_FLOWS_CSV = "event_flows.csv"
SCENARIO_MANIFEST_JSON = "scenario_manifest.json"
ACCOUNTS_SNAPSHOT_JSON = "accounts_snapshot.json"


def _person_keys(config: dict) -> list[str]:
    preferred = [
        key for key in ("person1", "person2")
        if isinstance(config.get(key), dict)
        and any(field in config[key] for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    extras = [
        key for key, value in config.items()
        if key not in preferred
        and isinstance(value, dict)
        and any(field in value for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    return preferred + extras


def write_sidecars(
    *,
    output_dir: Path,
    df: pd.DataFrame,
    config: dict,
    scenario: ScenarioRef | None,
    mode: str,
    cache_timestamp: str | None,
    portfolio: dict[str, float],
    extras: dict[str, float],
    liability_balances: dict[str, float],
    property_values: dict[str, float],
    raw_accounts: list[dict[str, Any]] | None,
) -> dict[str, Path]:
    """Write a normalized sidecar bundle for independent analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat()
    runtime_config = resolve_runtime_config(config)

    projection_path = output_dir / PROJECTION_CSV
    event_flows_path = output_dir / EVENT_FLOWS_CSV
    manifest_path = output_dir / SCENARIO_MANIFEST_JSON
    accounts_path = output_dir / ACCOUNTS_SNAPSHOT_JSON

    projection_df = _projection_sidecar_frame(df)
    projection_df.to_csv(projection_path, index=False)

    event_flows_df = _event_flows_frame(df)
    event_flows_df.to_csv(event_flows_path, index=False)

    manifest = _scenario_manifest(
        generated_at=generated_at,
        mode=mode,
        cache_timestamp=cache_timestamp,
        scenario=scenario,
        config=config,
        runtime_config=runtime_config,
        df=df,
        raw_accounts=raw_accounts,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    accounts_snapshot = {
        "generated_at": generated_at,
        "mode": mode,
        "cache_timestamp": cache_timestamp,
        "portfolio": portfolio,
        "extras": extras,
        "liability_balances": liability_balances,
        "property_values": property_values,
        "raw_accounts": raw_accounts or [],
    }
    accounts_path.write_text(json.dumps(accounts_snapshot, indent=2), encoding="utf-8")

    return {
        "projection_yearly_csv": projection_path,
        "event_flows_csv": event_flows_path,
        "scenario_manifest_json": manifest_path,
        "accounts_snapshot_json": accounts_path,
    }


def _projection_sidecar_frame(df: pd.DataFrame) -> pd.DataFrame:
    scalar_columns = [column for column in df.columns if column != "event_items"]
    return df[scalar_columns].copy()


def _event_flows_frame(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["year"])
        for item in row.get("event_items", []) or []:
            if isinstance(item, dict):
                rows.append(
                    {
                        "year": year,
                        "label": str(item.get("label", "")),
                        "event_type": item.get("event_type"),
                        "expense_kind": item.get("expense_kind"),
                        "amount": float(item.get("amount", 0.0)),
                    }
                )
            else:
                label, amount = item
                rows.append(
                    {
                        "year": year,
                        "label": str(label),
                        "event_type": None,
                        "expense_kind": None,
                        "amount": float(amount),
                    }
                )

    return pd.DataFrame(rows, columns=["year", "label", "event_type", "expense_kind", "amount"])


def _scenario_manifest(
    *,
    generated_at: str,
    mode: str,
    cache_timestamp: str | None,
    scenario: ScenarioRef | None,
    config: dict,
    runtime_config: dict,
    df: pd.DataFrame,
    raw_accounts: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    enabled_events_config = [e for e in config.get("events", []) if e.get("enabled", False)]
    enabled_events_runtime = [e for e in runtime_config.get("events", []) if e.get("enabled", False)]

    resolved_end_of_plan_years = {
        event.get("person"): int(event["year"])
        for event in enabled_events_runtime
        if event.get("type") == "EndOfPlan" and event.get("person")
    }

    return {
        "generated_at": generated_at,
        "mode": mode,
        "cache_timestamp": cache_timestamp,
        "scenario": {
            "slug": scenario.slug if scenario else "default",
            "name": scenario.name if scenario else "Default Plan",
            "description": scenario.description if scenario else "",
            "config_path": str(scenario.config_path) if scenario else None,
        },
        "sidecars": {
            "projection_yearly_csv": PROJECTION_CSV,
            "event_flows_csv": EVENT_FLOWS_CSV,
            "scenario_manifest_json": SCENARIO_MANIFEST_JSON,
            "accounts_snapshot_json": ACCOUNTS_SNAPSHOT_JSON,
        },
        "simulation": dict(config.get("simulation", {})),
        "people": {
            person_key: {
                key: config.get(person_key, {}).get(key)
                for key in ["name", "dob", "life_expectancy", "retirement_year", "annual_take_home"]
            }
            for person_key in _person_keys(config)
        },
        "assumptions": dict(config.get("assumptions", {})),
        "withdrawal_policy": dict(config.get("withdrawal_policy", {})),
        "enabled_events_config": enabled_events_config,
        "enabled_events_runtime": enabled_events_runtime,
        "resolved_end_of_plan_years": resolved_end_of_plan_years,
        "projection_summary": {
            "start_year": int(df["year"].min()) if not df.empty else None,
            "end_year": int(df["year"].max()) if not df.empty else None,
            "row_count": int(len(df)),
            "raw_account_count": int(len(raw_accounts or [])),
        },
    }
