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
from src.sidecars import write_sidecars

OUTPUT_DIR  = Path("output")
DEPLOY_DIR  = Path("/srv/web-projects/finances")
CACHE_FILE  = OUTPUT_DIR / "balances_cache.json"
OFFLINE     = "--offline" in sys.argv


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
    print("Net Worth Navigator")
    print("=" * 40)
    mode = "offline" if OFFLINE else "full"
    print(f"Mode: {'OFFLINE (cached)' if OFFLINE else 'FULL (live Monarch)'}")

    # 1. Balances — live or cached
    cache_timestamp = None
    if OFFLINE:
        cached = load_cache()
        cache_timestamp = cached.get("timestamp")
        raw_accounts = cached.get("raw_accounts")
        if raw_accounts is not None:
            portfolio, extras = classify_accounts(raw_accounts)
            liability_balances = extract_liability_balances(raw_accounts)
            property_values = extract_real_estate_accounts(raw_accounts)
            print("  Reclassified cached raw accounts using current config.toml")
        else:
            portfolio = cached["portfolio"]
            extras = cached["extras"]
            liability_balances = cached["liability_balances"]
            property_values = {"Primary Residence": float(extras.get("home_value", 0.0))}
            print("  WARNING: legacy cache lacks raw account data; config-only account changes require one full run")
    else:
        print("→ Fetching account balances from Monarch...")
        raw_accounts = fetch_raw_accounts()
        portfolio, extras = classify_accounts(raw_accounts)
        liability_balances = extract_liability_balances(raw_accounts)
        property_values = extract_real_estate_accounts(raw_accounts)
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
    )
    print(f"  Projection years: {df['year'].min()}–{df['year'].max()}")

    # 3. Generate chart and sidecars
    OUTPUT_DIR.mkdir(exist_ok=True)
    config = load_config()
    output_path = OUTPUT_DIR / "projection.html"
    print(f"→ Generating chart → {output_path}")
    build_chart(df, output_path)

    print("→ Writing sidecar analysis files...")
    sidecars = write_sidecars(
        output_dir=OUTPUT_DIR,
        df=df,
        config=config,
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

    # 4. Deploy to web server
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    deploy_path = DEPLOY_DIR / "projection.html"
    shutil.copy2(output_path, deploy_path)
    deploy_path.chmod(0o644)
    print(f"→ Deployed → {deploy_path}")
    print(f"  View at: http://casalemuria.lan/finances/projection.html")
    print("Done.")


if __name__ == "__main__":
    main()
