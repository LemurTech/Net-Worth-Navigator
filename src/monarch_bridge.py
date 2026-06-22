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
from pathlib import Path

from src.config_loader import load_config as shared_load_config

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
    return shared_load_config(CONFIG_PATH)


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


def _account_classification_entry(config: dict, account_name: str) -> object:
    accounts = config.get("accounts", {}) if isinstance(config, dict) else {}
    return accounts.get(account_name)


def _account_category(config: dict, account_name: str) -> str | None:
    entry = _account_classification_entry(config, account_name)
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        raw_category = entry.get("category")
        if raw_category is None:
            return None
        return str(raw_category)
    return None


def _account_owner(config: dict, account_name: str) -> str | None:
    entry = _account_classification_entry(config, account_name)
    if not isinstance(entry, dict):
        return None
    raw_owner = entry.get("owner")
    owner = str(raw_owner).strip() if raw_owner is not None else ""
    return owner if owner in {"person1", "person2"} else None


def classify_accounts(raw: list[dict], config: dict | None = None) -> tuple[dict[str, float], dict[str, float]]:
    """
    Classify raw Monarch accounts per config.toml [accounts] and return totals.

    Accounts in [accounts].disabled are excluded regardless of their category.
    Liability accounts are excluded here — they are tracked dynamically via
    [[liabilities]] amortization in model.py.

    Returns:
        portfolio   — investable: {taxable, trad_ira, roth, cash}
        extras      — {home_value (gross), vehicles, other}
    """
    if config is None:
        config = load_config()
    accounts_map: dict = config.get("accounts", {})
    disabled: set[str] = set(accounts_map.get("disabled", []))

    portfolio = {"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0}
    extras = {"home_value": 0.0, "vehicles": 0.0, "other": 0.0}
    unclassified = []

    for acct in raw:
        name    = acct["name"]
        balance = acct["balance"]

        if name in disabled:
            continue

        cat = _account_category(config, name)

        if cat is None:
            unclassified.append((name, balance))
        elif cat in ("ignore", "liability"):
            # liabilities excluded — tracked via [[liabilities]] amortization
            pass
        elif cat in portfolio:
            portfolio[cat] += balance
        elif cat == "real_estate":
            extras["home_value"] += balance
        elif cat == "vehicle":
            extras["vehicles"] += balance
        else:
            extras["other"] += balance

    if unclassified:
        print("  WARNING: unclassified accounts — add to [accounts] in config.toml:")
        for name, bal in unclassified:
            print(f"    \"{name}\"  (balance: ${bal:,.2f})")

    return portfolio, extras


def extract_retirement_owner_balances(
    raw: list[dict],
    config: dict | None = None,
) -> dict[str, dict[str, float]]:
    """Return owner-attributed retirement balances from raw account data."""
    if config is None:
        config = load_config()
    accounts_map: dict = config.get("accounts", {})
    disabled: set[str] = set(accounts_map.get("disabled", []))

    owner_balances = {
        "trad_ira": {"person1": 0.0, "person2": 0.0},
        "roth": {"person1": 0.0, "person2": 0.0},
    }

    for acct in raw:
        name = acct["name"]
        if name in disabled:
            continue
        category = _account_category(config, name)
        owner = _account_owner(config, name)
        if category not in owner_balances or owner not in {"person1", "person2"}:
            continue
        owner_balances[category][owner] += float(acct["balance"])

    return owner_balances


def extract_real_estate_accounts(raw: list[dict], config: dict | None = None) -> dict[str, float]:
    """Return named real-estate accounts from raw Monarch data."""
    if config is None:
        config = load_config()
    accounts_map: dict = config.get("accounts", {})
    disabled: set[str] = set(accounts_map.get("disabled", []))

    properties: dict[str, float] = {}
    for acct in raw:
        name = acct["name"]
        if name in disabled:
            continue
        if _account_category(config, name) == "real_estate":
            properties[str(name)] = float(acct["balance"])
    return properties


def get_balances() -> tuple[dict[str, float], dict[str, float]]:
    """Fetch and classify current Monarch balances using the live config."""
    return classify_accounts(fetch_raw_accounts())


def extract_liability_balances(raw: list[dict], config: dict | None = None) -> dict[str, float]:
    """
    Return balances for all [[liabilities]] in config.toml from raw account data.

    Returns: {liability_name: current_balance (positive float)}
    """
    if config is None:
        config = load_config()
    liabilities = config.get("liabilities", [])
    if not liabilities:
        return {}

    liability_names = {lib["name"] for lib in liabilities}
    balances = {}

    for acct in raw:
        name = acct["name"]
        if name in liability_names:
            # Monarch stores loans as negative — store as positive balance
            balances[name] = abs(float(acct["balance"]))

    for lib in liabilities:
        if lib["name"] not in balances:
            print(f"  WARNING: liability '{lib['name']}' not found in Monarch accounts")

    return balances


def get_liability_balances() -> dict[str, float]:
    """
    Return current balances for all [[liabilities]] in config.toml,
    pulled live from Monarch by account name.

    Returns: {liability_name: current_balance (positive float)}
    """
    return extract_liability_balances(fetch_raw_accounts())


def get_account_balances() -> dict[str, float]:
    """Compatibility shim — returns just the investable portfolio dict."""
    portfolio, _ = get_balances()
    return portfolio


def list_accounts():
    """Print all accounts with current classification and disabled status."""
    raw    = fetch_raw_accounts()
    config = load_config()
    classified = config.get("accounts", {})
    disabled   = set(classified.get("disabled", []))

    print(f"\n{'Account Name':<45} {'Type':<15} {'Balance':>14}   {'Status'}")
    print("─" * 100)
    for acct in raw:
        name  = acct["name"]
        bal   = acct["balance"]
        atype = acct["type"]
        cat = _account_category(config, name) or "⚠ UNCLASSIFIED"
        owner = _account_owner(config, name)
        if owner:
            cat = f"{cat} [{owner}]"
        if name in disabled:
            status = f"[disabled] ({cat})"
        else:
            status = cat
        print(f"  {name:<43} {atype:<15} ${bal:>12,.2f}   {status}")


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
