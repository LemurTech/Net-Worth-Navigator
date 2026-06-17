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


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def run_projection(balances: dict[str, float], home_equity: float = 0.0) -> pd.DataFrame:
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

    # Home equity grows at inflation (not portfolio rate — non-liquid, no reinvestment)
    current_home_equity = home_equity

    rows = []

    for year in range(start_year, end_year + 1):
        # ── Apply events for this year ─────────────────────────────────────────
        active_labels = []
        event_cash_flow = 0.0

        for event in events:
            etype = event["type"]

            if etype == "Retire":
                if event["year"] == year:
                    active_labels.append(event["label"])

            elif etype == "SocialSecurity":
                if year >= event["year"]:
                    person_key = event["person"]
                    # SS income handled in income calculation below
                    pass

            elif etype == "Expense":
                if event["year"] == year:
                    event_cash_flow += event["amount"]
                    active_labels.append(event["label"])

            elif etype == "Income":
                end = event.get("end_year", event["year"])
                if event["year"] <= year <= end:
                    event_cash_flow += event["amount"]
                    if event["year"] == year:
                        active_labels.append(event["label"])

            elif etype == "BuyHome":
                if event["year"] == year:
                    event_cash_flow -= event["down_payment"]
                    active_labels.append(event["label"])
                # Mortgage payments handled as ongoing expense — TODO V2

            elif etype == "NewJob":
                if event["year"] == year:
                    active_labels.append(event["label"])
                # Income update handled in income calculation below

            elif etype == "CareerBreak":
                if event["start_year"] == year:
                    active_labels.append(event["label"])
                # Income zeroed in income calculation below

            elif etype == "Education":
                if event["start_year"] <= year <= event["end_year"]:
                    event_cash_flow -= event["annual_cost"]
                    if event["start_year"] == year:
                        active_labels.append(event["label"])

            elif etype == "Marriage":
                if event["year"] == year:
                    active_labels.append(event["label"])

        # ── Income for this year ───────────────────────────────────────────────
        matthew_income = _person_income(matthew, year, events)
        weny_income = _person_income(weny, year, events)
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
        target_spend = spending.get("retirement_annual", 0)
        annual_spend = target_spend if (matthew_retired and weny_retired) else total_income - total_contrib
        net_flow = total_income - annual_spend + event_cash_flow

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

        # Grow home equity at inflation rate
        current_home_equity *= (1 + assumptions["inflation"])

        rows.append({
            "year":           year,
            "net_worth":      total_portfolio,
            "home_equity":    current_home_equity,
            "total_net_worth": total_portfolio + current_home_equity,
            "matthew_income": matthew_income,
            "weny_income":    weny_income,
            "annual_spend":   annual_spend,
            "net_flow":       net_flow,
            "events_active":  ", ".join(active_labels) if active_labels else "",
            "taxable":        portfolio["taxable"],
            "trad_ira":       portfolio["trad_ira"],
            "roth":           portfolio["roth"],
            "cash":           portfolio["cash"],
        })

    return pd.DataFrame(rows)


def _person_income(person: dict, year: int, events: list) -> float:
    """Calculate a person's income for a given year, considering events."""
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
