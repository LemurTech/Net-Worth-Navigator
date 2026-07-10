"""
run.py — Net Worth Navigator entry point

Usage:
    python run.py              # full run: pulls live Monarch balances, renders chart
    python run.py --offline    # offline run: uses cached balances, renders chart
"""

import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from src.charts import build_chart
from src.csv_importer import build_csv_starting_inputs
from src.definitions_page import write_definitions_page
from src.model import load_config, run_projection_result
from src.version import __version__
from src.monarch_bridge import (
    classify_accounts,
    extract_basis_seeds,
    extract_liability_balances,
    extract_real_estate_accounts,
    extract_retirement_owner_balances,
    fetch_raw_accounts,
)
from src.scenarios import (
    SCENARIO_OUTPUT_ROOT,
    get_default_scenario,
    get_scenario,
    normalized_render_modes,
    scenario_output_dir,
    write_scenarios_index,
)
from src.scenario_shell import build_scenario_shell, build_compare_page
from src.sidecars import write_sidecars

OUTPUT_DIR  = Path("output")
DEPLOY_DIR  = Path("/srv/web-projects/finances")
CACHE_FILE  = OUTPUT_DIR / "balances_cache.json"
OFFLINE     = "--offline" in sys.argv
BUNDLED_HISTORICAL_RETURNS_PATH = "config/return_sequences/us_balanced_returns.csv"


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
    ts   = data.get("cache_timestamp", data.get("generated_at", "unknown"))
    print(f"  Using cached balances from {ts}")
    return data


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _synthetic_inputs_from_config(config: dict) -> tuple[dict, dict, dict, dict, dict, dict]:
    synthetic = config.get("synthetic_start", {}) if isinstance(config.get("synthetic_start"), dict) else {}

    portfolio = {
        "taxable": _f(synthetic.get("taxable", 0.0)),
        "trad_ira": _f(synthetic.get("trad_ira", 0.0)),
        "roth": _f(synthetic.get("roth", 0.0)),
        "cash": _f(synthetic.get("cash", 0.0)),
    }
    extras = {
        "home_value": _f(synthetic.get("home_value", 0.0)),
        "vehicles": _f(synthetic.get("vehicles", 0.0)),
        "other": _f(synthetic.get("other", 0.0)),
    }

    raw_liability_balances = synthetic.get("liability_balances", {})
    liability_balances = {
        str(name): _f(balance)
        for name, balance in raw_liability_balances.items()
        if _f(balance) > 0
    } if isinstance(raw_liability_balances, dict) else {}

    raw_property_values = synthetic.get("property_values", {})
    property_values = {
        str(name): _f(value)
        for name, value in raw_property_values.items()
        if _f(value) != 0
    } if isinstance(raw_property_values, dict) else {}

    raw_owner_balances = synthetic.get("retirement_owner_balances", {})
    retirement_owner_balances = {
        bucket: {
            "person1": _f((bucket_values or {}).get("person1", 0.0)),
            "person2": _f((bucket_values or {}).get("person2", 0.0)),
        }
        for bucket, bucket_values in raw_owner_balances.items()
        if bucket in {"trad_ira", "roth"} and isinstance(bucket_values, dict)
    }

    basis_seeds: dict[str, float] = {}
    if "taxable_cost_basis" in synthetic:
        basis_seeds["taxable_cost_basis"] = _f(synthetic.get("taxable_cost_basis", 0.0))
    if "roth_contribution_basis" in synthetic:
        basis_seeds["roth_contribution_basis"] = _f(synthetic.get("roth_contribution_basis", 0.0))

    if not property_values and extras["home_value"] != 0:
        property_values = {"Primary Residence": extras["home_value"]}

    return portfolio, extras, liability_balances, property_values, retirement_owner_balances, basis_seeds


def scenario_render_modes(config: dict) -> list[str]:
    simulation_cfg = config.get("simulation", {}) if isinstance(config.get("simulation"), dict) else {}
    return normalized_render_modes(simulation_cfg.get("render_modes"))

def config_for_render_mode(config: dict, mode: str) -> dict:
    rendered = deepcopy(config)
    simulation_cfg = dict(rendered.get("simulation", {}))
    simulation_cfg["mode"] = mode
    if mode == "historical" and not simulation_cfg.get("historical_returns_path"):
        simulation_cfg["historical_returns_path"] = BUNDLED_HISTORICAL_RETURNS_PATH
    rendered["simulation"] = simulation_cfg
    return rendered


def check_first_run():
    """Detect first run and show welcome message."""
    first_run_marker = OUTPUT_DIR / ".initialized"
    
    if first_run_marker.exists():
        return False  # Not first run
    
    print("=" * 70)
    print("Welcome to Net Worth Navigator!")
    print("=" * 70)
    print()
    print("This appears to be your first run. A few tips:")
    print()
    print("1. If you're new, try the sample scenario first:")
    print("   python run.py --scenario sample")
    print()
    print("2. To create your own scenario:")
    print("   - Copy scenarios/starter.toml to scenarios/myhousehold.toml")
    print("   - Fill in your household data")
    print("   - Run: python run.py --scenario myhousehold")
    print()
    print("3. Use the web UI for easier setup:")
    print("   python admin_app.py")
    print("   Open http://localhost:8010/setup")
    print()
    print("4. Run scripts/verify_install.py anytime to check your installation")
    print()
    print("=" * 70)
    print()
    
    # Create marker file
    OUTPUT_DIR.mkdir(exist_ok=True)
    first_run_marker.write_text(f"First run: {datetime.now().isoformat()}\n")
    
    return True


def main():
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"Net Worth Navigator v{__version__}")
        return
    
    # Check for first run and show welcome message
    is_first_run = check_first_run()
    scenario = get_scenario(selected_scenario_slug(sys.argv))
    config = load_config(scenario.config_path)
    
    # Validate scenario configuration before running projection
    from src.model import validate_scenario
    is_valid, validation_errors = validate_scenario(config, scenario.config_path)
    
    if not is_valid:
        print("=" * 70)
        print("ERROR: Scenario Validation Failed")
        print("=" * 70)
        print()
        print(f"Scenario: {scenario.name} ({scenario.slug})")
        print(f"Config: {scenario.config_path}")
        print()
        print(f"Found {len(validation_errors)} issue(s) that must be fixed:")
        print()
        for i, error in enumerate(validation_errors, 1):
            # Multi-line errors get indented continuation
            lines = error.split("\n")
            print(f"{i}. {lines[0]}")
            for continuation in lines[1:]:
                print(f"   {continuation}")
            print()
        print("=" * 70)
        print("Fix these issues in your scenario file, then try again.")
        print("=" * 70)
        sys.exit(1)
    
    default_scenario = get_default_scenario()
    baseline_config = load_config(default_scenario.config_path)
    scenario_dir = scenario_output_dir(scenario.slug)
    render_modes = scenario_render_modes(config)

    print("Net Worth Navigator")
    print("=" * 40)
    print(f"Scenario: {scenario.name} ({scenario.slug})")

    data_source_cfg = config.get("data_source", {}) if isinstance(config.get("data_source"), dict) else {}
    data_source_mode = str(data_source_cfg.get("mode", "monarch")).strip().lower() or "monarch"
    use_synthetic  = data_source_mode == "synthetic"
    use_csv_import = data_source_mode == "csv_import"

    mode = (
        "synthetic" if use_synthetic else (
            "csv_import" if use_csv_import else (
                "offline" if OFFLINE else "full"
            )
        )
    )

    if use_synthetic:
        print("Mode: SYNTHETIC (scenario-provided starting balances; Monarch bypassed)")
    elif use_csv_import:
        print("Mode: CSV IMPORT (per-account balances from [csv_source]; Monarch bypassed)")
    else:
        print(f"Mode: {'OFFLINE (cached)' if OFFLINE else 'FULL (live Monarch)'}")

    # 1. Balances — synthetic, csv_import, live, or cached
    cache_timestamp = None
    data_as_of = None
    if use_synthetic:
        portfolio, extras, liability_balances, property_values, retirement_owner_seed, basis_seed = _synthetic_inputs_from_config(config)
        raw_accounts = []
        # data_as_of stays None — no clamp for synthetic
    elif use_csv_import:
        print("=> Reading account balances from [csv_source]...")
        portfolio, extras, liability_balances, property_values, retirement_owner_seed, basis_seed = build_csv_starting_inputs(config)
        raw_accounts = []
        csv_source = config.get("csv_source", {}) or {}
        last_import = csv_source.get("last_import") if isinstance(csv_source, dict) else None
        if last_import:
            try:
                data_as_of = datetime.fromisoformat(last_import).date()
            except (ValueError, TypeError):
                pass
        print(f"  Investable:     ${sum(portfolio.values()):>12,.2f}")
        print(f"  Home value:     ${extras.get('home_value', 0.0):>12,.2f}")
        print(f"  Liabilities:    ${sum(liability_balances.values()):>12,.2f}")
        print(f"  Accounts:       {len(config.get('csv_source', {}).get('accounts', {}))} from CSV import")
    elif OFFLINE:
        cached = load_cache()
        cache_timestamp = cached.get("cache_timestamp", cached.get("generated_at"))
        if cache_timestamp:
            try:
                data_as_of = datetime.fromisoformat(cache_timestamp).date()
            except (ValueError, TypeError):
                pass
        raw_accounts = cached.get("raw_accounts")
        if raw_accounts is not None:
            portfolio, extras = classify_accounts(raw_accounts, config=config)
            liability_balances = extract_liability_balances(raw_accounts, config=config)
            property_values = extract_real_estate_accounts(raw_accounts, config=config)
            retirement_owner_seed = extract_retirement_owner_balances(raw_accounts, config=config)
            basis_seed = extract_basis_seeds(raw_accounts, config=config)
            print(f"  Reclassified cached raw accounts using {scenario.config_path.name}")
        else:
            portfolio = cached["portfolio"]
            extras = cached["extras"]
            liability_balances = cached["liability_balances"]
            property_values = {"Primary Residence": float(extras.get("home_value", 0.0))}
            retirement_owner_seed = {}
            basis_seed = {}
            print("  WARNING: legacy cache lacks raw account data; config-only account changes require one full run")
    else:
        print("=> Fetching account balances from Monarch...")
        try:
            raw_accounts = fetch_raw_accounts()
        except RuntimeError as exc:
            print(f"\nERROR: Could not fetch Monarch balances.\n")
            for line in str(exc).splitlines():
                print(f"  {line}")
            print()
            print("Alternatives:")
            print("  Offline (cached):  python run.py --offline")
            print("  No Monarch:        set [data_source].mode = \"synthetic\" in your scenario")
            sys.exit(1)
        data_as_of = datetime.now().date()
        portfolio, extras = classify_accounts(raw_accounts, config=config)
        liability_balances = extract_liability_balances(raw_accounts, config=config)
        property_values = extract_real_estate_accounts(raw_accounts, config=config)
        retirement_owner_seed = extract_retirement_owner_balances(raw_accounts, config=config)
        basis_seed = extract_basis_seeds(raw_accounts, config=config)
        save_cache(portfolio, extras, liability_balances, raw_accounts=raw_accounts)

    home_value        = extras["home_value"]
    total_liabilities = sum(liability_balances.values())
    print(f"  Investable:     ${sum(portfolio.values()):>12,.2f}")
    print(f"  Home value:     ${home_value:>12,.2f}")
    print(f"  Liabilities:    ${total_liabilities:>12,.2f}")
    print(f"  Home equity:    ${home_value - total_liabilities:>12,.2f}")

    # 2. Run projection(s)
    rendered_modes: list[str] = []
    OUTPUT_DIR.mkdir(exist_ok=True)
    scenario_dir.mkdir(parents=True, exist_ok=True)
    for render_mode in render_modes:
        mode_config = config_for_render_mode(config, render_mode)
        mode_baseline_config = config_for_render_mode(baseline_config, render_mode)
        mode_dir = scenario_output_dir(scenario.slug, render_mode)
        sidecar_dir = mode_dir / "sidecars"
        output_path = mode_dir / "projection.html"

        print(f"=> Running projection [{render_mode}]...")
        projection_result = run_projection_result(
            portfolio,
            home_value=home_value,
            liability_balances=liability_balances,
            property_values=property_values,
            retirement_owner_balances=retirement_owner_seed,
            basis_seeds=basis_seed,
            data_as_of=data_as_of,
            config=mode_config,
        )
        df = projection_result.yearly_df
        print(f"  Projection years: {df['year'].min()}-{df['year'].max()}")
        print(f"  Simulation mode: {projection_result.mode} ({projection_result.run_count} run{'s' if projection_result.run_count != 1 else ''})")
        print(f"=> Generating chart [{render_mode}] => {output_path}")
        build_chart(
            projection_result,
            output_path,
            config=mode_config,
            scenario=scenario,
            baseline_config=mode_baseline_config,
        )
        print(f"=> Writing sidecar analysis files [{render_mode}] => {sidecar_dir}")
        sidecars = write_sidecars(
            output_dir=sidecar_dir,
            df=df,
            projection_result=projection_result,
            config=mode_config,
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
        rendered_modes.append(render_mode)
    index_path = write_scenarios_index(output_root=SCENARIO_OUTPUT_ROOT, cache_timestamp=cache_timestamp)
    print(f"  scenarios_index_json: {index_path}")
    shell_manifest = json.loads(index_path.read_text(encoding="utf-8"))
    shell_output_path = OUTPUT_DIR / "projection.html"
    build_scenario_shell(
        manifest=shell_manifest,
        output_path=shell_output_path,
        manifest_relpath="scenarios/index.json",
        setup_url="/finances/config/setup",
        definitions_url="/finances/definitions.html",
    )
    print(f"  scenario_shell_html: {shell_output_path}")
    definitions_output_path = OUTPUT_DIR / "definitions.html"
    write_definitions_page(
        definitions_output_path,
        editor_url="/finances/config/setup",
        projection_url="/finances/projection.html",
    )
    print(f"  definitions_html: {definitions_output_path}")

    compare_output_path = OUTPUT_DIR / "compare.html"
    build_compare_page(
        manifest=shell_manifest,
        output_path=compare_output_path,
        manifest_relpath="scenarios/index.json",
        shell_url="/finances/projection.html",
        definitions_url="/finances/definitions.html",
    )
    print(f"  compare_html: {compare_output_path}")

    # 4. Deploy to web server
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    deploy_scenario_dir = DEPLOY_DIR / "scenarios" / scenario.slug
    shutil.copytree(scenario_dir, deploy_scenario_dir, dirs_exist_ok=True)
    deploy_index_path = DEPLOY_DIR / "scenarios" / "index.json"
    deploy_index_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(index_path, deploy_index_path)
    deploy_path = DEPLOY_DIR / "projection.html"
    shutil.copy2(shell_output_path, deploy_path)
    deploy_definitions_path = DEPLOY_DIR / "definitions.html"
    shutil.copy2(definitions_output_path, deploy_definitions_path)
    deploy_compare_path = DEPLOY_DIR / "compare.html"
    shutil.copy2(compare_output_path, deploy_compare_path)
    deploy_path.chmod(0o644)
    deploy_definitions_path.chmod(0o644)
    deploy_compare_path.chmod(0o644)
    print(f"=> Deployed => {deploy_path}")
    print(f"  View at: http://casalemuria.lan/finances/projection.html")
    print("Done.")


if __name__ == "__main__":
    main()
