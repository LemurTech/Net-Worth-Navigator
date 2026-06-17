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

from src.model import run_projection
from src.charts import build_chart

OUTPUT_DIR  = Path("output")
DEPLOY_DIR  = Path("/srv/web-projects/finances")
CACHE_FILE  = OUTPUT_DIR / "balances_cache.json"
OFFLINE     = "--offline" in sys.argv


def save_cache(portfolio: dict, extras: dict, liability_balances: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps({
        "timestamp":         datetime.now().isoformat(),
        "portfolio":         portfolio,
        "extras":            extras,
        "liability_balances": liability_balances,
    }, indent=2))


def load_cache() -> tuple[dict, dict, dict]:
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            "No cached balances found at output/balances_cache.json.\n"
            "Run without --offline first to create the cache."
        )
    data = json.loads(CACHE_FILE.read_text())
    ts   = data.get("timestamp", "unknown")
    print(f"  Using cached balances from {ts}")
    return data["portfolio"], data["extras"], data["liability_balances"]


def main():
    print("Net Worth Navigator")
    print("=" * 40)
    mode = "OFFLINE (cached)" if OFFLINE else "FULL (live Monarch)"
    print(f"Mode: {mode}")

    # 1. Balances — live or cached
    if OFFLINE:
        portfolio, extras, liability_balances = load_cache()
    else:
        print("→ Fetching account balances from Monarch...")
        from src.monarch_bridge import get_balances, get_liability_balances
        portfolio, extras       = get_balances()
        liability_balances      = get_liability_balances()
        save_cache(portfolio, extras, liability_balances)

    home_value        = extras["home_value"]
    total_liabilities = sum(liability_balances.values())
    print(f"  Investable:     ${sum(portfolio.values()):>12,.2f}")
    print(f"  Home value:     ${home_value:>12,.2f}")
    print(f"  Liabilities:    ${total_liabilities:>12,.2f}")
    print(f"  Home equity:    ${home_value - total_liabilities:>12,.2f}")

    # 2. Run projection
    print("→ Running projection...")
    df = run_projection(portfolio, home_value=home_value, liability_balances=liability_balances)
    print(f"  Projection years: {df['year'].min()}–{df['year'].max()}")

    # 3. Generate chart
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "projection.html"
    print(f"→ Generating chart → {output_path}")
    build_chart(df, output_path)

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
