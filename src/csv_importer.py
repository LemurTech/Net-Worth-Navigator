"""
csv_importer.py — Parse Monarch-format CSV account exports and merge with
existing account classification in scenario config.

Three public functions:
    parse_csv(file_path)          → list[{name, balance, date}]
    merge_accounts(old, new, cls) → {updated, new, maybe_removed}
    build_csv_starting_inputs     → (portfolio, extras, liability_balances,
      (config)                       property_values, retirement_owner_balances,
                                     basis_seeds)
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from src.monarch_bridge import (
    classify_accounts,
    extract_basis_seeds,
    extract_liability_balances,
    extract_real_estate_accounts,
    extract_retirement_owner_balances,
)

_DATE_FMTS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d")


def _parse_date(val: str) -> datetime | None:
    """Try common date formats; return None if none match."""
    cleaned = val.strip().strip('"')
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def parse_csv(file_path: str | Path) -> list[dict]:
    """
    Parse a Monarch-format CSV: Date,Balance,Account

    Returns a list of dicts, one per unique account, with the LATEST date's
    balance for each account.  Debts (negative balances) are stored as-is
    (negative), matching what Monarch's API returns for liability accounts.

    Returns:
        [{name: str, balance: float, date: str (YYYY-MM-DD)}, ...]

    Raises:
        ValueError: CSV has no rows, missing expected columns, or unparseable.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty.")

        header_norm = [h.strip().lower() for h in header]
        try:
            date_idx = header_norm.index("date")
            bal_idx = header_norm.index("balance")
            acct_idx = header_norm.index("account")
        except ValueError:
            raise ValueError(
                "CSV must have columns named Date, Balance, Account. "
                f"Found: {header}"
            )

        raw: list[dict] = []
        for row_num, row in enumerate(reader, start=2):
            # Skip empty rows
            if not row or all(cell.strip() == "" for cell in row):
                continue
            if len(row) <= max(date_idx, bal_idx, acct_idx):
                continue

            name = row[acct_idx].strip()
            if not name:
                continue

            bal = _f(row[bal_idx])
            dt = _parse_date(row[date_idx])
            if dt is None:
                continue

            raw.append({"name": name, "balance": bal, "date": dt})

    if not raw:
        raise ValueError("No parseable account rows found in CSV.")

    # Group by account name, keep the latest date per account
    latest: dict[str, dict] = {}
    for entry in raw:
        key = entry["name"]
        if key not in latest or entry["date"] >= latest[key]["date"]:
            latest[key] = entry

    # Return sorted by name for deterministic output
    result = sorted(latest.values(), key=lambda e: e["name"])
    return [
        {"name": e["name"], "balance": e["balance"], "date": e["date"].strftime("%Y-%m-%d")}
        for e in result
    ]


def accounts_from_csv(csv_path: str | Path) -> dict[str, float]:
    """Convenience: parse CSV and return {name: balance} dict (latest per account)."""
    entries = parse_csv(csv_path)
    return {e["name"]: e["balance"] for e in entries}


def merge_accounts(
    old_accounts: dict[str, float],
    new_accounts: list[dict],
    existing_classifications: dict[str, Any],
    removed_ok: bool = False,
) -> dict:
    """
    Compare new parsed accounts against existing state.

    Args:
        old_accounts:       Current {name: balance} from [csv_source.accounts]
        new_accounts:       List from parse_csv() — [{name, balance, date}]
        existing_classifications: Current [accounts] section (name → category or dict)
        removed_ok:         If True, auto-remove old accounts not in new CSV.

    Returns:
        {
            "updated":      [{name, balance, date, category, owner}]
            "new":          [{name, balance, date, category: None, owner: None}]
            "maybe_removed": [{name, balance, date}]  (present in old but not new)
        }
    """
    old_names = set(old_accounts.keys())
    new_map = {e["name"]: e for e in new_accounts}
    new_names = set(new_map.keys())

    updated: list[dict] = []
    new_entries: list[dict] = []
    maybe_removed: list[dict] = []

    # Accounts in both old and new → update balance, preserve classification
    for name in sorted(old_names & new_names):
        entry = dict(new_map[name])
        cls = existing_classifications.get(name)
        if isinstance(cls, dict):
            entry["category"] = cls.get("category")
            entry["owner"] = cls.get("owner", "n/a")
        elif isinstance(cls, str):
            entry["category"] = cls
            entry["owner"] = "n/a"
        else:
            entry["category"] = None
            entry["owner"] = "n/a"
        updated.append(entry)

    # Accounts only in new → unclassified
    for name in sorted(new_names - old_names):
        entry = dict(new_map[name])
        entry["category"] = None
        entry["owner"] = "n/a"
        new_entries.append(entry)

    # Accounts only in old → potentially removed
    for name in sorted(old_names - new_names):
        entry = {
            "name": name,
            "balance": old_accounts[name],
            "date": None,
            "category": existing_classifications.get(name),
            "owner": None,
        }
        maybe_removed.append(entry)

    return {
        "updated": updated,
        "new": new_entries,
        "maybe_removed": maybe_removed,
    }


def _config(config: dict) -> tuple[dict, dict]:
    """Normalise config to (csv_source dict, accounts dict)."""
    ds = config.get("csv_source", {})
    if not isinstance(ds, dict):
        ds = {}
    accts = config.get("accounts", {})
    if not isinstance(accts, dict):
        accts = {}
    return ds, accts


def _build_virtual_raw_accounts(
    csv_source: dict,
) -> list[dict]:
    """
    Convert [csv_source.accounts] into the same {name, balance, type} shape
    that monarch_bridge functions expect, so we can reuse classify_accounts()
    and friends.
    """
    accounts = csv_source.get("accounts", {})
    if not isinstance(accounts, dict):
        return []
    return [
        {"name": name, "balance": balance, "type": ""}
        for name, balance in accounts.items()
        if balance is not None
    ]


def build_csv_starting_inputs(config: dict) -> tuple[dict, dict, dict, dict, dict, dict]:
    """
    Main function called by run.py when data_source.mode == "csv_import".

    Reads [csv_source.accounts] and [accounts] from config and returns the
    same 6-tuple shape as _synthetic_inputs_from_config():
        portfolio, extras, liability_balances,
        property_values, retirement_owner_balances, basis_seeds

    Reuses monarch_bridge classification/extraction functions by building
    a virtual raw-account list from the CSV source data.
    """
    csv_source, accts = _config(config)
    raw = _build_virtual_raw_accounts(csv_source)

    portfolio, extras = classify_accounts(raw, config=config)
    liability_balances = extract_liability_balances(raw, config=config)
    property_values = extract_real_estate_accounts(raw, config=config)
    retirement_owner_balances = extract_retirement_owner_balances(raw, config=config)
    basis_seeds = extract_basis_seeds(raw, config=config)

    # If no named properties were extracted but home_value is in extras,
    # build a synthetic one (matching synthetic_start behavior in run.py)
    if not property_values and extras.get("home_value", 0.0) != 0:
        property_values = {"Primary Residence": extras["home_value"]}

    return (
        portfolio,
        extras,
        liability_balances,
        property_values,
        retirement_owner_balances,
        basis_seeds,
    )
