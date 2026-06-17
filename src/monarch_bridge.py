"""
monarch_bridge.py — Fetch and classify account balances from Monarch Money MCP.

Returns a dict mapping account category → current balance:
    {
        "taxable":  float,
        "trad_ira": float,
        "roth":     float,
        "cash":     float,
    }

Account classification is driven by config.toml [accounts] section.
Run with --list to print raw Monarch account names for classification setup.
"""

import sys
import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def get_account_balances() -> dict[str, float]:
    """
    Query Monarch MCP for current account balances.
    Classify each account using the [accounts] mapping in config.toml.
    Returns totals by category.
    """
    config = load_config()
    classification_map = config.get("accounts", {})

    # TODO: Replace stub with live Monarch MCP query
    # The Monarch MCP exposes account balances. When implementing, use
    # the monarch MCP tools to fetch all accounts and their balances.
    raw_accounts = _fetch_monarch_accounts()

    totals = {"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0}

    for account_name, balance in raw_accounts.items():
        category = classification_map.get(account_name)
        if category and category != "ignore" and category in totals:
            totals[category] += balance
        elif category == "ignore":
            pass
        else:
            print(f"  WARNING: Account '{account_name}' not classified — excluded from model.")
            print(f"  Add it to [accounts] in config.toml")

    return totals


def _fetch_monarch_accounts() -> dict[str, float]:
    """
    Stub: returns empty dict until Monarch MCP integration is wired.
    Replace with live MCP call in the next implementation phase.
    """
    # TODO: Call Monarch MCP here
    # Expected return format: {"Account Name": balance_float, ...}
    return {}


def list_accounts():
    """Print all Monarch account names — use this to set up config.toml [accounts]."""
    raw = _fetch_monarch_accounts()
    if not raw:
        print("No accounts returned. Monarch MCP may need authentication.")
        print("Re-auth: cd /opt/monarch-mcp-server && uv run python login_setup.py")
        return
    print("Monarch accounts (copy names into config.toml [accounts]):")
    for name, balance in sorted(raw.items()):
        print(f"  \"{name}\" = \"?\"   # balance: ${balance:,.2f}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_accounts()
    else:
        balances = get_account_balances()
        for cat, total in balances.items():
            print(f"  {cat:12}: ${total:>12,.2f}")
