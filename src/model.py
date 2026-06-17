"""
model.py — Net Worth Navigator projection engine.

Reads config.toml and a balances dict from monarch_bridge.
Returns a pandas DataFrame with one row per year:

    year | net_worth | matthew_income | weny_income | events_active | ...
"""

import tomllib
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"

# ── Event type → emoji icon ────────────────────────────────────────────────────
EVENT_ICONS = {
    "EndOfPlan":      "⚰️",
    "Retire":         "🏖️",
    "SocialSecurity": "🏛️",
    "Expense":        "💸",
    "Income":         "💰",
    "BuyHome":        "🏠",
    "NewJob":         "💼",
    "CareerBreak":    "⏸️",
    "Education":      "🎓",
    "Marriage":       "💍",
}

LIABILITY_ICONS = {
    "mortgage": "🏠",
    "auto":     "🚗",
    "other":    "✅",
}


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def run_projection(
    balances: dict[str, float],
    home_value: float = 0.0,
    liability_balances: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Run the year-by-year net worth projection.

    balances: dict from monarch_bridge — {category: total_balance}
    Returns: DataFrame with projection data
    """
    config = load_config()
    sim = config["simulation"]
    assumptions = config["assumptions"]
    events = [e for e in config.get("events", []) if e.get("enabled", False)]

    start_year = sim["start_year"]
    end_year = sim["end_year"]

    # ── Initial state ──────────────────────────────────────────────────────────
    # If Monarch bridge returns real data, use it; otherwise fall back to 0
    portfolio = {
        "taxable":  balances.get("taxable", 0.0),
        "trad_ira": balances.get("trad_ira", 0.0),
        "roth":     balances.get("roth", 0.0),
        "cash":     balances.get("cash", 0.0),
    }

    matthew = config["matthew"]
    weny = config["weny"]
    spending = config["spending"]
    liability_configs = config.get("liabilities", [])

    if liability_balances is None:
        liability_balances = {}

    # ── Initialize liability amortization state ────────────────────────────────
    # Each liability tracks: balance, monthly payment, rate, type, payoff_year
    lib_state = []
    for lib in liability_configs:
        bal = liability_balances.get(lib["name"], 0.0)
        lib_state.append({
            "name":          lib["name"],
            "balance":       bal,
            "monthly_rate":  lib["annual_rate"] / 12,
            "monthly_total": lib["monthly_base"] + lib.get("monthly_extra", 0.0),
            "monthly_freed": 0.0,   # set to monthly_total in payoff year
            "type":          lib.get("type", "other"),
            "payoff_year":   None,
            "paid_off":      bal <= 0,
        })

    # ── Home tracking ──────────────────────────────────────────────────────────
    # home_value grows at inflation; mortgage balance is tracked in lib_state
    current_home_value = home_value
    # Sum initial mortgage balances for starting home equity
    mortgage_balance = sum(
        s["balance"] for s in lib_state if s["type"] == "mortgage"
    )

    rows = []

    for year in range(start_year, end_year + 1):
        # ── Amortize liabilities for this year (12 monthly steps) ─────────────
        payoff_labels = []
        freed_this_year = 0.0

        for lib in lib_state:
            if lib["paid_off"]:
                freed_this_year += lib["monthly_total"] * 12
                continue

            for _ in range(12):
                if lib["balance"] <= 0:
                    break
                interest = lib["balance"] * lib["monthly_rate"]
                principal = lib["monthly_total"] - interest
                lib["balance"] = max(0.0, lib["balance"] - principal)

            if lib["balance"] <= 0 and lib["payoff_year"] is None:
                lib["payoff_year"] = year
                lib["paid_off"] = True
                short_name = lib["name"].split("(")[0].strip()
                icon = LIABILITY_ICONS.get(lib["type"], "✅")
                payoff_labels.append(f"{icon} {short_name} paid off")

            if lib["paid_off"]:
                freed_this_year += lib["monthly_total"] * 12

        # Update running mortgage balance for home equity
        mortgage_balance = sum(
            s["balance"] for s in lib_state if s["type"] == "mortgage"
        )

        # ── Determine survivor state ───────────────────────────────────────────
        matthew_deceased = year > matthew["retirement_year"] and any(
            e["type"] == "EndOfPlan" and e.get("person") == "matthew" and year > e["year"]
            for e in events
        )
        weny_deceased = year > weny["retirement_year"] and any(
            e["type"] == "EndOfPlan" and e.get("person") == "weny" and year > e["year"]
            for e in events
        )

        # ── Apply events for this year ─────────────────────────────────────────
        active_labels = []
        event_cash_flow = 0.0
        event_items: list[tuple[str, float]] = []   # (label, amount) for cash flow table

        for event in events:
            etype = event["type"]

            if etype == "EndOfPlan":
                if event["year"] == year:
                    icon = EVENT_ICONS["EndOfPlan"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "Retire":
                if event["year"] == year:
                    icon = EVENT_ICONS["Retire"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "SocialSecurity":
                if year == event["year"]:
                    icon = EVENT_ICONS["SocialSecurity"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "Expense":
                if event["year"] == year:
                    event_cash_flow += event["amount"]
                    event_items.append((event["label"], event["amount"]))
                    icon = EVENT_ICONS["Expense"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "Income":
                end = event.get("end_year", event["year"])
                if event["year"] <= year <= end:
                    event_cash_flow += event["amount"]
                    event_items.append((event["label"], event["amount"]))
                    if event["year"] == year:
                        icon = EVENT_ICONS["Income"]
                        active_labels.append(f"{icon} {event['label']}")

            elif etype == "BuyHome":
                if event["year"] == year:
                    event_cash_flow -= event["down_payment"]
                    event_items.append((event["label"], -event["down_payment"]))
                    icon = EVENT_ICONS["BuyHome"]
                    active_labels.append(f"{icon} {event['label']}")
                # Mortgage payments handled as ongoing expense — TODO V2

            elif etype == "NewJob":
                if event["year"] == year:
                    icon = EVENT_ICONS["NewJob"]
                    active_labels.append(f"{icon} {event['label']}")
                # Income update handled in income calculation below

            elif etype == "CareerBreak":
                if event["start_year"] == year:
                    icon = EVENT_ICONS["CareerBreak"]
                    active_labels.append(f"{icon} {event['label']}")
                # Income zeroed in income calculation below

            elif etype == "Education":
                if event["start_year"] <= year <= event["end_year"]:
                    event_cash_flow -= event["annual_cost"]
                    if event["start_year"] == year:
                        icon = EVENT_ICONS["Education"]
                        active_labels.append(f"{icon} {event['label']}")

            elif etype == "Marriage":
                if event["year"] == year:
                    icon = EVENT_ICONS["Marriage"]
                    active_labels.append(f"{icon} {event['label']}")

        # ── Income for this year ───────────────────────────────────────────────
        matthew_income = _person_income(matthew, year, events, deceased=matthew_deceased)
        weny_income    = _person_income(weny, year, events, deceased=weny_deceased)

        # ── SS survivor benefit: survivor keeps the higher of the two checks ───
        # If one person is deceased and both had started SS, the survivor's
        # own benefit is already captured in _person_income. But if the deceased
        # had the higher benefit, the survivor steps up — recalculate here.
        if matthew_deceased or weny_deceased:
            matthew_ss = sum(
                e.get("monthly_benefit", 0) * 12
                for e in events
                if e["type"] == "SocialSecurity"
                and e.get("person") == "matthew"
                and year >= e["year"]
            )
            weny_ss = sum(
                e.get("monthly_benefit", 0) * 12
                for e in events
                if e["type"] == "SocialSecurity"
                and e.get("person") == "weny"
                and year >= e["year"]
            )
            higher_ss = max(matthew_ss, weny_ss)
            lower_ss  = min(matthew_ss, weny_ss)

            if matthew_deceased and not weny_deceased and weny_ss > 0:
                # Person 2 survives: receives higher of two checks (Person 1's if higher)
                if matthew_ss > weny_ss:
                    # Step Person 2 up — replace her SS with Person 1's higher amount
                    weny_income = weny_income - weny_ss + matthew_ss
            elif weny_deceased and not matthew_deceased and matthew_ss > 0:
                # Person 1 survives: already on higher check, no change needed
                pass

        total_income = matthew_income + weny_income

        # ── Contributions (pre-retirement only) ────────────────────────────────
        matthew_retired = year >= matthew["retirement_year"]
        weny_retired = year >= weny["retirement_year"]

        matthew_contrib = 0.0 if matthew_retired else (
            matthew.get("annual_401k_contribution", 0) +
            matthew.get("annual_ira_contribution", 0)
        )
        weny_contrib = 0.0 if weny_retired else (
            weny.get("annual_401k_contribution", 0) +
            weny.get("annual_ira_contribution", 0)
        )
        total_contrib = matthew_contrib + weny_contrib

        # ── Net cash flow for the year ─────────────────────────────────────────
        target_spend   = spending.get("retirement_annual", 0)
        survivor_spend = spending.get("survivor_annual", round(target_spend * 0.70))
        both_retired   = matthew_retired and weny_retired
        one_deceased   = matthew_deceased or weny_deceased

        if both_retired and one_deceased:
            annual_spend = survivor_spend
        elif both_retired:
            annual_spend = target_spend
        else:
            annual_spend = total_income - total_contrib

        # Freed liability payments add to net cash flow
        net_flow = total_income - annual_spend + event_cash_flow + freed_this_year

        # ── Grow portfolio ─────────────────────────────────────────────────────
        growth_rate = (
            assumptions["stock_return"] * assumptions["equity_allocation"] +
            assumptions["bond_return"] * (1 - assumptions["equity_allocation"])
        )
        total_portfolio = sum(portfolio.values())
        total_portfolio = total_portfolio * (1 + growth_rate) + net_flow

        # Simplified: grow each bucket proportionally
        # V2: model withdrawals with proper sequencing
        current_total = sum(portfolio.values())
        if current_total > 0 and total_portfolio > 0:
            for cat in portfolio:
                portfolio[cat] = (portfolio[cat] / current_total) * total_portfolio
        elif total_portfolio <= 0:
            # Portfolio depleted — track as negative cash (debt/shortfall)
            for cat in portfolio:
                portfolio[cat] = 0.0
            portfolio["cash"] = total_portfolio
        else:
            portfolio["cash"] = total_portfolio

        # ── Grow home value at inflation; compute equity ───────────────────────
        current_home_value *= (1 + assumptions["inflation"])
        home_equity = current_home_value - mortgage_balance

        # Merge all annotation labels for this year
        all_labels = payoff_labels + active_labels

        rows.append({
            "year":           year,
            "net_worth":      total_portfolio,
            "home_value":     current_home_value,
            "mortgage":       mortgage_balance,
            "home_equity":    home_equity,
            "total_net_worth": total_portfolio + home_equity,
            "matthew_income": matthew_income,
            "weny_income":    weny_income,
            "annual_spend":   annual_spend,
            "freed_payments": freed_this_year,
            "net_flow":       net_flow,
            "survivor":       one_deceased and both_retired,
            "event_items":    event_items,
            "events_active":  ", ".join(all_labels) if all_labels else "",
            "taxable":        portfolio["taxable"],
            "trad_ira":       portfolio["trad_ira"],
            "roth":           portfolio["roth"],
            "cash":           portfolio["cash"],
        })

    return pd.DataFrame(rows)


def _person_income(person: dict, year: int, events: list, deceased: bool = False) -> float:
    """Calculate a person's income for a given year, considering events."""
    if deceased:
        return 0.0

    person_key = person["name"].lower()
    base_income = person.get("annual_take_home", 0)

    # Stop income at retirement
    if year >= person["retirement_year"]:
        base_income = 0

    # Add Social Security
    for event in events:
        if event["type"] == "SocialSecurity" and event.get("person") == person_key:
            if year >= event["year"]:
                base_income += event.get("monthly_benefit", 0) * 12

    # Career break: zero income for duration
    for event in events:
        if event["type"] == "CareerBreak" and event.get("person") == person_key:
            if event["start_year"] <= year <= event["end_year"]:
                # Zero earned income (SS preserved if applicable)
                ss_income = sum(
                    e.get("monthly_benefit", 0) * 12
                    for e in events
                    if e["type"] == "SocialSecurity" and e.get("person") == person_key
                    and year >= e["year"]
                )
                base_income = ss_income

    # New job: replace base income
    for event in events:
        if event["type"] == "NewJob" and event.get("person") == person_key:
            if year >= event["year"] and year < person["retirement_year"]:
                base_income = event["annual_income"]

    return base_income
