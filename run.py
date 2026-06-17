"""
run.py — Net Worth Navigator entry point

Usage:
    python run.py

Reads config.toml, pulls live Monarch balances, runs the projection,
generates output/projection.html, and deploys to /srv/web-projects/finances/.
"""

import shutil
import sys
from pathlib import Path

from src.monarch_bridge import get_balances
from src.model import run_projection
from src.charts import build_chart

OUTPUT_DIR = Path("output")
DEPLOY_DIR = Path("/srv/web-projects/finances")


def main():
    print("Net Worth Navigator")
    print("=" * 40)

    # 1. Pull live balances from Monarch
    print("→ Fetching account balances from Monarch...")
    from src.monarch_bridge import get_balances, get_liability_balances
    portfolio, extras = get_balances()
    liability_balances = get_liability_balances()
    home_value = extras["home_value"]
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
