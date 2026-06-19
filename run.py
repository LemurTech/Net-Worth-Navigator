"""
run.py — Net Worth Navigator entry point

Usage:
    python run.py              # full run: pulls live Monarch balances, renders chart
    python run.py --offline    # offline run: uses cached balances, renders chart
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from src.charts import build_chart
from src.model import load_config, run_projection
from src.monarch_bridge import (
    classify_accounts,
    extract_liability_balances,
    extract_real_estate_accounts,
    fetch_raw_accounts,
)
from src.scenarios import (
    SCENARIO_OUTPUT_ROOT,
    get_scenario,
    scenario_output_dir,
    write_scenarios_index,
)
from src.scenario_shell import build_scenario_shell
from src.sidecars import write_sidecars

OUTPUT_DIR  = Path("output")
DEPLOY_DIR  = Path("/srv/web-projects/finances")
CACHE_FILE  = OUTPUT_DIR / "balances_cache.json"
OFFLINE     = "--offline" in sys.argv


def selected_scenario_slug(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--scenario" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--scenario="):
            return arg.split("=", 1)[1]
    return None


def save_cache(
    portfolio: dict,
    extras: dict,
    liability_balances: dict,
    raw_accounts: list[dict] | None = None,
) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "portfolio": portfolio,
        "extras": extras,
        "liability_balances": liability_balances,
    }
    if raw_accounts is not None:
        payload["raw_accounts"] = raw_accounts
    CACHE_FILE.write_text(json.dumps(payload, indent=2))


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            "No cached balances found at output/balances_cache.json.\n"
            "Run without --offline first to create the cache."
        )
    data = json.loads(CACHE_FILE.read_text())
    ts   = data.get("timestamp", "unknown")
    print(f"  Using cached balances from {ts}")
    return data


def main():
    scenario = get_scenario(selected_scenario_slug(sys.argv))
    config = load_config(scenario.config_path)
    scenario_dir = scenario_output_dir(scenario.slug)

    print("Net Worth Navigator")
    print("=" * 40)
    print(f"Scenario: {scenario.name} ({scenario.slug})")
    mode = "offline" if OFFLINE else "full"
    print(f"Mode: {'OFFLINE (cached)' if OFFLINE else 'FULL (live Monarch)'}")

    # 1. Balances — live or cached
    cache_timestamp = None
    if OFFLINE:
        cached = load_cache()
        cache_timestamp = cached.get("timestamp")
        raw_accounts = cached.get("raw_accounts")
        if raw_accounts is not None:
            portfolio, extras = classify_accounts(raw_accounts, config=config)
            liability_balances = extract_liability_balances(raw_accounts, config=config)
            property_values = extract_real_estate_accounts(raw_accounts, config=config)
            print(f"  Reclassified cached raw accounts using {scenario.config_path.name}")
        else:
            portfolio = cached["portfolio"]
            extras = cached["extras"]
            liability_balances = cached["liability_balances"]
            property_values = {"Primary Residence": float(extras.get("home_value", 0.0))}
            print("  WARNING: legacy cache lacks raw account data; config-only account changes require one full run")
    else:
        print("→ Fetching account balances from Monarch...")
        raw_accounts = fetch_raw_accounts()
        portfolio, extras = classify_accounts(raw_accounts, config=config)
        liability_balances = extract_liability_balances(raw_accounts, config=config)
        property_values = extract_real_estate_accounts(raw_accounts, config=config)
        save_cache(portfolio, extras, liability_balances, raw_accounts=raw_accounts)

    home_value        = extras["home_value"]
    total_liabilities = sum(liability_balances.values())
    print(f"  Investable:     ${sum(portfolio.values()):>12,.2f}")
    print(f"  Home value:     ${home_value:>12,.2f}")
    print(f"  Liabilities:    ${total_liabilities:>12,.2f}")
    print(f"  Home equity:    ${home_value - total_liabilities:>12,.2f}")

    # 2. Run projection
    print("→ Running projection...")
    df = run_projection(
        portfolio,
        home_value=home_value,
        liability_balances=liability_balances,
        property_values=property_values,
        config=config,
    )
    print(f"  Projection years: {df['year'].min()}–{df['year'].max()}")

    # 3. Generate chart and sidecars
    OUTPUT_DIR.mkdir(exist_ok=True)
    scenario_dir.mkdir(parents=True, exist_ok=True)
    sidecar_dir = scenario_dir / "sidecars"
    output_path = scenario_dir / "projection.html"
    print(f"→ Generating chart → {output_path}")
    build_chart(df, output_path, config=config)
    print(f"→ Writing sidecar analysis files → {sidecar_dir}")
    sidecars = write_sidecars(
        output_dir=sidecar_dir,
        df=df,
        config=config,
        scenario=scenario,
        mode=mode,
        cache_timestamp=cache_timestamp,
        portfolio=portfolio,
        extras=extras,
        liability_balances=liability_balances,
        property_values=property_values,
        raw_accounts=raw_accounts,
    )
    for label, path in sidecars.items():
        print(f"  {label}: {path}")
    index_path = write_scenarios_index(output_root=SCENARIO_OUTPUT_ROOT)
    print(f"  scenarios_index_json: {index_path}")
    shell_manifest = json.loads(index_path.read_text(encoding="utf-8"))
    shell_output_path = OUTPUT_DIR / "projection.html"
    build_scenario_shell(
        manifest=shell_manifest,
        output_path=shell_output_path,
        manifest_relpath="scenarios/index.json",
        editor_url="/finances/config/",
    )
    print(f"  scenario_shell_html: {shell_output_path}")

    # 4. Deploy to web server
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    deploy_scenario_dir = DEPLOY_DIR / "scenarios" / scenario.slug
    shutil.copytree(scenario_dir, deploy_scenario_dir, dirs_exist_ok=True)
    deploy_index_path = DEPLOY_DIR / "scenarios" / "index.json"
    deploy_index_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(index_path, deploy_index_path)
    deploy_path = DEPLOY_DIR / "projection.html"
    shutil.copy2(shell_output_path, deploy_path)
    deploy_path.chmod(0o644)
    print(f"→ Deployed → {deploy_path}")
    print(f"  View at: http://casalemuria.lan/finances/projection.html")
    print("Done.")


if __name__ == "__main__":
    main()
