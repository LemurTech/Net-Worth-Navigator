"""
monarch_bridge.py — Fetch and classify account balances from Monarch Money.

Uses the MCP server's Python environment (which is already authenticated)
via subprocess, avoiding library version conflicts. Classification is driven
by config.toml [accounts].

Returns:
    portfolio   — investable: {taxable, trad_ira, roth, cash}
    extras      — {home_equity, vehicles, liabilities, other}

Run standalone to list/verify accounts:
    python -m src.monarch_bridge --list
    python -m src.monarch_bridge          (shows classified totals)
"""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"

MCP_PYTHON = Path("/opt/monarch-mcp-server/.venv/bin/python3")
MCP_SRC    = Path("/opt/monarch-mcp-server/src")

# Inline script run inside the MCP venv — fetches accounts as JSON to stdout
_FETCH_SCRIPT = """
import asyncio, json, sys
sys.path.insert(0, '{src}')
from monarch_mcp_server.secure_session import secure_session
from monarchmoney import MonarchMoney

async def main():
    token = secure_session.load_token()
    mm = MonarchMoney(token=token)
    result = await mm.get_accounts()
    accounts = result.get('accounts', [])
    out = [{{
        'name': a.get('displayName') or a.get('name', '?'),
        'balance': float(a.get('currentBalance') or 0),
        'type': a.get('type', {{}}).get('name', '') if isinstance(a.get('type'), dict) else '',
    }} for a in accounts]
    print(json.dumps(out))

asyncio.run(main())
""".format(src=str(MCP_SRC))


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def fetch_raw_accounts() -> list[dict]:
    """
    Call the MCP server's Python to fetch accounts as JSON.
    Uses the already-authenticated session token.
    """
    result = subprocess.run(
        [str(MCP_PYTHON), "-c", _FETCH_SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"Monarch fetch failed (exit {result.returncode}).\n"
            f"stderr: {stderr}\n"
            "Re-auth: cd /opt/monarch-mcp-server && uv run python login_setup.py"
        )
    # Strip any warning lines (non-JSON) and parse the last JSON line
    lines = [l for l in result.stdout.strip().splitlines() if l.startswith("[")]
    if not lines:
        raise RuntimeError(f"No JSON in Monarch output. stdout: {result.stdout!r}")
    return json.loads(lines[-1])


def get_balances() -> tuple[dict[str, float], dict[str, float]]:
    """
    Classify accounts per config.toml [accounts] and return totals.

    Returns:
        portfolio   — investable: {taxable, trad_ira, roth, cash}
        extras      — {home_equity, vehicles, liabilities, other}
    """
    config = load_config()
    classification_map: dict[str, str] = config.get("accounts", {})

    raw = fetch_raw_accounts()

    portfolio = {"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0}
    extras = {"home_equity": 0.0, "vehicles": 0.0, "liabilities": 0.0, "other": 0.0}
    unclassified = []

    for acct in raw:
        name    = acct["name"]
        balance = acct["balance"]
        cat     = classification_map.get(name)

        if cat is None:
            unclassified.append((name, balance))
        elif cat == "ignore":
            pass
        elif cat in portfolio:
            portfolio[cat] += balance
        elif cat == "real_estate":
            extras["home_equity"] += balance
        elif cat == "vehicle":
            extras["vehicles"] += balance
        elif cat == "liability":
            extras["liabilities"] += balance  # Monarch stores as negative
        else:
            extras["other"] += balance

    if unclassified:
        print("  WARNING: unclassified accounts — add to [accounts] in config.toml:")
        for name, bal in unclassified:
            print(f"    \"{name}\"  (balance: ${bal:,.2f})")

    return portfolio, extras


def get_account_balances() -> dict[str, float]:
    """Compatibility shim — returns just the investable portfolio dict."""
    portfolio, _ = get_balances()
    return portfolio


def list_accounts():
    """Print all accounts with current classification status."""
    raw   = fetch_raw_accounts()
    config = load_config()
    classified = config.get("accounts", {})

    print(f"\n{'Account Name':<45} {'Type':<15} {'Balance':>14}   {'Classified As'}")
    print("─" * 100)
    for acct in raw:
        name  = acct["name"]
        bal   = acct["balance"]
        atype = acct["type"]
        cat   = classified.get(name, "⚠ UNCLASSIFIED")
        print(f"  {name:<43} {atype:<15} ${bal:>12,.2f}   {cat}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_accounts()
    else:
        portfolio, extras = get_balances()
        print("\nInvestable Portfolio:")
        for cat, total in portfolio.items():
            print(f"  {cat:<12}: ${total:>12,.2f}")
        total_invest = sum(portfolio.values())
        print(f"  {'TOTAL':<12}: ${total_invest:>12,.2f}")
        home_equity = extras["home_equity"] + extras["liabilities"]
        print(f"\nHome Equity (property + mortgage): ${home_equity:>12,.2f}")
        print(f"Vehicles:                          ${extras['vehicles']:>12,.2f}")
        total_nw = total_invest + home_equity + extras["vehicles"] + extras["other"]
        print(f"\nEstimated Total Net Worth:         ${total_nw:>12,.2f}")
