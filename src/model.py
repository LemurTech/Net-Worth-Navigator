"""
model.py — Net Worth Navigator projection engine.

Reads config.toml and a balances dict from monarch_bridge.
Returns a pandas DataFrame with one row per year:

    year | net_worth | matthew_income | weny_income | events_active | ...
"""

import tomllib
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"

# ── Event type → emoji icon ────────────────────────────────────────────────────
EVENT_ICONS = {
    "EndOfPlan":      "⚰️",
    "Retire":         "🎉",
    "SocialSecurity": "🏛️",
    "Expense":        "💸",
    "Income":         "💰",
    "BuyHome":        "🏠",
    "NewJob":         "💼",
    "CareerBreak":    "⏸️",
    "Education":      "🎓",
    "Marriage":       "💍",
}

EXPENSE_KIND_ICONS = {
    "mandatory": "💸",
    "discretionary": "🏖️",
}

LIABILITY_ICONS = {
    "mortgage": "🏠",
    "auto":     "🚗",
    "other":    "✅",
}

DEFAULT_WITHDRAWAL_ORDER = [
    "cash_above_target",
    "taxable",
    "trad_ira",
    "roth",
    "cash_below_target",
]

DEFAULT_TAX_FILING_STATUS = {
    "pre_retirement": "married_joint",
    "retirement": "married_joint",
    "survivor": "single",
}


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def resolve_runtime_config(config: dict) -> dict:
    """Return a runtime-safe config with recurring events expanded to concrete events."""
    runtime = deepcopy(config)
    runtime["events"] = expand_events(
        runtime.get("events", []),
        runtime.get("simulation", {}),
    )
    return runtime


def expand_events(events: list[dict], simulation: dict | None = None) -> list[dict]:
    """Expand recurring event definitions into concrete event instances."""
    sim_end = simulation.get("end_year") if simulation else None
    expanded: list[dict] = []

    for event in events:
        interval = event.get("repeat_every_years")
        if interval is None:
            concrete = dict(event)
            concrete.setdefault("_show_chart_label", True)
            expanded.append(concrete)
            continue

        base_field = _event_anchor_field(event)
        if base_field is None:
            raise ValueError(
                f"Recurring event '{event.get('label', '?')}' must have year or start_year"
            )

        interval = int(interval)
        if interval <= 0:
            raise ValueError(
                f"Recurring event '{event.get('label', '?')}' must have repeat_every_years > 0"
            )

        repeat_count = event.get("repeat_count")
        if repeat_count is not None:
            repeat_count = int(repeat_count)
            if repeat_count < 1:
                raise ValueError(
                    f"Recurring event '{event.get('label', '?')}' must have repeat_count >= 1"
                )

        repeat_until_year = event.get("repeat_until_year", sim_end)
        if repeat_until_year is not None:
            repeat_until_year = int(repeat_until_year)

        if repeat_count is None and repeat_until_year is None and sim_end is None:
            raise ValueError(
                f"Recurring event '{event.get('label', '?')}' needs repeat_count, repeat_until_year, or simulation.end_year"
            )

        occurrence = 0
        while True:
            anchor_year = int(event[base_field]) + (occurrence * interval)
            if repeat_count is not None and occurrence >= repeat_count:
                break
            if repeat_until_year is not None and anchor_year > repeat_until_year:
                break
            if sim_end is not None and anchor_year > sim_end:
                break

            expanded.append(
                _materialize_recurring_event(event, base_field, anchor_year, occurrence)
            )
            occurrence += 1

    return expanded


def _event_anchor_field(event: dict) -> str | None:
    if "year" in event:
        return "year"
    if "start_year" in event:
        return "start_year"
    return None


def _materialize_recurring_event(
    event: dict,
    base_field: str,
    anchor_year: int,
    occurrence: int,
) -> dict:
    concrete = dict(event)
    for field in ("repeat_every_years", "repeat_until_year", "repeat_count"):
        concrete.pop(field, None)

    year_delta = anchor_year - int(event[base_field])
    concrete[base_field] = anchor_year
    if base_field == "start_year" and "end_year" in event:
        concrete["end_year"] = int(event["end_year"]) + year_delta

    chart_first_only = bool(event.get("chart_first_occurrence_only", False))
    concrete["_show_chart_label"] = (not chart_first_only) or occurrence == 0
    return concrete


def normalize_expense_kind(event: dict | None) -> str:
    """Return a normalized expense kind for Expense events."""
    kind = str((event or {}).get("expense_kind", "mandatory")).strip().lower()
    return "discretionary" if kind == "discretionary" else "mandatory"


def should_show_chart_label(event: dict) -> bool:
    """Return whether this event instance should annotate the main projection chart."""
    return bool(event.get("_show_chart_label", True))


def get_event_icon(event: dict) -> str:
    """Return the display icon for an event, including expense subtypes."""
    if event.get("type") == "Expense":
        return EXPENSE_KIND_ICONS[normalize_expense_kind(event)]
    return EVENT_ICONS.get(event.get("type", ""), "•")


def make_event_item(label: str, amount: float, event_type: str,
                    expense_kind: str | None = None) -> dict[str, object]:
    """Build normalized event-item metadata for cash-flow tables."""
    item = {
        "label": label,
        "amount": amount,
        "event_type": event_type,
    }
    if expense_kind is not None:
        item["expense_kind"] = expense_kind
    return item


def resolve_withdrawal_policy(config: dict, balances: dict[str, float]) -> dict[str, object]:
    """Return phase-specific withdrawal policy with sensible defaults."""
    section = config.get("withdrawal_policy", {})
    spending = config.get("spending", {})
    current_cash = round(float(balances.get("cash", 0.0)), 2)
    retirement_spend = float(spending.get("retirement_annual", 0.0))
    survivor_spend = float(
        spending.get("survivor_annual", round(retirement_spend * 0.70))
    )

    return {
        "accumulation_cash_target": max(
            0.0, float(section.get("accumulation_cash_target", current_cash))
        ),
        "retirement_cash_target": max(
            0.0, float(section.get("retirement_cash_target", retirement_spend))
        ),
        "survivor_cash_target": max(
            0.0, float(section.get("survivor_cash_target", survivor_spend))
        ),
        "accumulation_withdrawal_order": _normalize_withdrawal_order(
            section.get("accumulation_withdrawal_order", DEFAULT_WITHDRAWAL_ORDER)
        ),
        "retirement_withdrawal_order": _normalize_withdrawal_order(
            section.get("retirement_withdrawal_order", DEFAULT_WITHDRAWAL_ORDER)
        ),
        "survivor_withdrawal_order": _normalize_withdrawal_order(
            section.get("survivor_withdrawal_order", DEFAULT_WITHDRAWAL_ORDER)
        ),
    }


def get_phase_withdrawal_settings(
    policy: dict[str, object],
    *,
    both_retired: bool,
    one_deceased: bool,
) -> tuple[float, list[str]]:
    """Return the active cash target and withdrawal order for the current phase."""
    if one_deceased:
        phase = "survivor"
    elif both_retired:
        phase = "retirement"
    else:
        phase = "accumulation"

    return (
        float(policy.get(f"{phase}_cash_target", 0.0)),
        list(policy.get(f"{phase}_withdrawal_order", DEFAULT_WITHDRAWAL_ORDER)),
    )


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
    config = resolve_runtime_config(load_config())
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
    withdrawal_policy = resolve_withdrawal_policy(config, balances)

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
        taxable_event_income = 0.0
        event_items: list[dict[str, object]] = []   # normalized cash-flow items for tables

        for event in events:
            etype = event["type"]

            if etype == "EndOfPlan":
                if event["year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["EndOfPlan"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "Retire":
                if event["year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["Retire"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "SocialSecurity":
                if year == event["year"] and should_show_chart_label(event):
                    icon = EVENT_ICONS["SocialSecurity"]
                    active_labels.append(f"{icon} {event['label']}")

            elif etype == "Expense":
                if event["year"] == year:
                    event_cash_flow += event["amount"]
                    expense_kind = normalize_expense_kind(event)
                    event_items.append(
                        make_event_item(
                            label=event["label"],
                            amount=event["amount"],
                            event_type="Expense",
                            expense_kind=expense_kind,
                        )
                    )
                    icon = get_event_icon(event)
                    if should_show_chart_label(event):
                        active_labels.append(f"{icon} {event['label']}")

            elif etype == "Income":
                end = event.get("end_year", event["year"])
                if event["year"] <= year <= end:
                    event_cash_flow += event["amount"]
                    event_items.append(
                        make_event_item(
                            label=event["label"],
                            amount=event["amount"],
                            event_type="Income",
                        )
                    )
                    if event["amount"] > 0:
                        taxable_event_income += (
                            event["amount"] * _event_taxable_fraction(event, default=1.0)
                        )
                    if event["year"] == year and should_show_chart_label(event):
                        icon = EVENT_ICONS["Income"]
                        active_labels.append(f"{icon} {event['label']}")

            elif etype == "BuyHome":
                if event["year"] == year:
                    event_cash_flow -= event["down_payment"]
                    event_items.append(
                        make_event_item(
                            label=event["label"],
                            amount=-event["down_payment"],
                            event_type="BuyHome",
                        )
                    )
                    icon = EVENT_ICONS["BuyHome"]
                    if should_show_chart_label(event):
                        active_labels.append(f"{icon} {event['label']}")
                # Mortgage payments handled as ongoing expense — TODO V2

            elif etype == "NewJob":
                if event["year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["NewJob"]
                    active_labels.append(f"{icon} {event['label']}")
                # Income update handled in income calculation below

            elif etype == "CareerBreak":
                if event["start_year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["CareerBreak"]
                    active_labels.append(f"{icon} {event['label']}")
                # Income zeroed in income calculation below

            elif etype == "Education":
                if event["start_year"] <= year <= event["end_year"]:
                    event_cash_flow -= event["annual_cost"]
                    if event["start_year"] == year and should_show_chart_label(event):
                        icon = EVENT_ICONS["Education"]
                        active_labels.append(f"{icon} {event['label']}")

            elif etype == "Marriage":
                if event["year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["Marriage"]
                    active_labels.append(f"{icon} {event['label']}")

        # ── Income for this year ───────────────────────────────────────────────
        matthew_parts = _person_income_components(
            matthew, year, events, deceased=matthew_deceased
        )
        weny_parts = _person_income_components(
            weny, year, events, deceased=weny_deceased
        )

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
            matthew_ss_taxable = sum(
                (e.get("monthly_benefit", 0) * 12) * _event_taxable_fraction(e, default=1.0)
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
            weny_ss_taxable = sum(
                (e.get("monthly_benefit", 0) * 12) * _event_taxable_fraction(e, default=1.0)
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
                    weny_parts["ss_income"] = matthew_ss
                    weny_parts["ss_taxable_income"] = matthew_ss_taxable
                    weny_parts["cash_income"] = (
                        weny_parts["earned_income"] + weny_parts["ss_income"]
                    )
            elif weny_deceased and not matthew_deceased and matthew_ss > 0:
                # Person 1 survives: already on higher check, no change needed
                pass

        matthew_income = matthew_parts["cash_income"]
        weny_income    = weny_parts["cash_income"]
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

        cash_target, withdrawal_order = get_phase_withdrawal_settings(
            withdrawal_policy,
            both_retired=both_retired,
            one_deceased=one_deceased,
        )

        active_tax_system = resolve_tax_system(
            config,
            assumptions=assumptions,
            both_retired=both_retired,
            one_deceased=one_deceased,
        )
        base_taxable_income = (
            matthew_parts["ss_taxable_income"] +
            weny_parts["ss_taxable_income"] +
            taxable_event_income
        )

        # Cash flow before any taxes or withdrawal sequencing
        base_net_flow = total_income - annual_spend + event_cash_flow + freed_this_year

        # ── Grow portfolio ─────────────────────────────────────────────────────
        growth_rate = (
            assumptions["stock_return"] * assumptions["equity_allocation"] +
            assumptions["bond_return"] * (1 - assumptions["equity_allocation"])
        )
        current_total = sum(portfolio.values())
        if current_total > 0:
            grown_portfolio = {
                cat: balance * (1 + growth_rate)
                for cat, balance in portfolio.items()
            }
        else:
            grown_portfolio = portfolio.copy()

        annual_taxes = estimate_annual_taxes(
            base_taxable_income=base_taxable_income,
            withdrawal_taxable_income=0.0,
            tax_system=active_tax_system,
        )
        withdrawal_taxable_income = 0.0
        working_portfolio = grown_portfolio.copy()

        # Iterate because taxable withdrawals themselves increase taxes.
        for _ in range(12):
            working_portfolio = grown_portfolio.copy()
            post_tax_flow = base_net_flow - annual_taxes

            if post_tax_flow >= 0:
                _apply_surplus_with_reserve_target(
                    working_portfolio,
                    surplus=post_tax_flow,
                    cash_target=cash_target,
                )
                withdrawal_taxable_income = 0.0
            else:
                withdrawal_taxable_income, unmet_deficit = _cover_deficit_with_policy(
                    working_portfolio,
                    deficit=-post_tax_flow,
                    assumptions=assumptions,
                    withdrawal_order=withdrawal_order,
                    cash_target=cash_target,
                )
                if unmet_deficit > 0:
                    for cat in working_portfolio:
                        working_portfolio[cat] = 0.0
                    working_portfolio["cash"] = -unmet_deficit

            new_annual_taxes = estimate_annual_taxes(
                base_taxable_income=base_taxable_income,
                withdrawal_taxable_income=withdrawal_taxable_income,
                tax_system=active_tax_system,
            )
            if abs(new_annual_taxes - annual_taxes) < 0.01:
                annual_taxes = new_annual_taxes
                break
            annual_taxes = new_annual_taxes

        portfolio = working_portfolio
        taxable_income = base_taxable_income + withdrawal_taxable_income
        net_flow = base_net_flow - annual_taxes

        # ── Grow home value at inflation; compute equity ───────────────────────
        total_portfolio = sum(portfolio.values())
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
            "taxable_income": taxable_income,
            "annual_taxes":   annual_taxes,
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


def _person_income_components(
    person: dict, year: int, events: list, deceased: bool = False
) -> dict[str, float]:
    """Return earned-net and SS-gross components for a person's annual cash income."""
    if deceased:
        return {
            "earned_income": 0.0,
            "ss_income": 0.0,
            "ss_taxable_income": 0.0,
            "cash_income": 0.0,
        }

    person_key = person["name"].lower()
    earned_income = person.get("annual_take_home", 0)
    ss_income = 0.0
    ss_taxable_income = 0.0

    # Stop income at retirement
    if year >= person["retirement_year"]:
        earned_income = 0.0

    # Add Social Security
    for event in events:
        if event["type"] == "SocialSecurity" and event.get("person") == person_key:
            if year >= event["year"]:
                annual_ss = event.get("monthly_benefit", 0) * 12
                ss_income += annual_ss
                ss_taxable_income += annual_ss * _event_taxable_fraction(event, default=1.0)

    # Career break: zero income for duration
    for event in events:
        if event["type"] == "CareerBreak" and event.get("person") == person_key:
            if event["start_year"] <= year <= event["end_year"]:
                # Zero earned income (SS preserved separately)
                earned_income = 0.0

    # New job: replace base income
    for event in events:
        if event["type"] == "NewJob" and event.get("person") == person_key:
            if year >= event["year"] and year < person["retirement_year"]:
                earned_income = event["annual_income"]

    return {
        "earned_income": earned_income,
        "ss_income": ss_income,
        "ss_taxable_income": ss_taxable_income,
        "cash_income": earned_income + ss_income,
    }


def _event_taxable_fraction(event: dict, default: float = 1.0) -> float:
    """Return event taxability as a fraction in [0,1]."""
    if "taxable_fraction" in event:
        try:
            return max(0.0, min(1.0, float(event["taxable_fraction"])))
        except (TypeError, ValueError):
            return default
    if event.get("taxable") is False:
        return 0.0
    return default


def _withdrawal_taxable_fraction(category: str, assumptions: dict) -> float:
    """Return taxable fraction for withdrawals from a portfolio bucket."""
    if category == "trad_ira":
        return assumptions.get("trad_ira_withdrawal_taxable_fraction", 1.0)
    if category == "taxable":
        return assumptions.get("taxable_withdrawal_taxable_fraction", 0.50)
    return 0.0


def resolve_tax_system(
    config: dict,
    *,
    assumptions: dict,
    both_retired: bool,
    one_deceased: bool,
) -> dict[str, object]:
    """Return the active tax system for the current simulation phase."""
    taxes = config.get("taxes", {})
    phase = _tax_phase(both_retired=both_retired, one_deceased=one_deceased)

    filing_status = str(
        taxes.get(f"{phase}_filing_status", DEFAULT_TAX_FILING_STATUS[phase])
    ).strip().lower()
    if filing_status not in {"single", "married_joint", "head_of_household"}:
        filing_status = DEFAULT_TAX_FILING_STATUS[phase]

    standard_deduction = float(
        taxes.get("standard_deduction", {}).get(filing_status, 0.0)
    )
    brackets = list(taxes.get("brackets", {}).get(filing_status, []))

    if taxes.get("enabled") and brackets:
        return {
            "mode": "brackets",
            "filing_status": filing_status,
            "standard_deduction": standard_deduction,
            "brackets": brackets,
        }

    return {
        "mode": "effective_rate",
        "rate": float(
            assumptions["effective_tax_rate_post_retirement"]
            if both_retired else assumptions["effective_tax_rate_pre_retirement"]
        ),
    }


def _tax_phase(*, both_retired: bool, one_deceased: bool) -> str:
    if one_deceased:
        return "survivor"
    if both_retired:
        return "retirement"
    return "pre_retirement"


def calculate_progressive_tax(
    *,
    taxable_income: float,
    standard_deduction: float,
    brackets: list[dict],
) -> float:
    """Calculate tax for ordinary income using a progressive bracket table."""
    remaining_taxable = max(0.0, float(taxable_income) - max(0.0, float(standard_deduction)))
    lower_bound = 0.0
    total_tax = 0.0

    for bracket in brackets:
        rate = max(0.0, float(bracket.get("rate", 0.0)))
        upper_bound = bracket.get("up_to")

        if upper_bound is None:
            total_tax += max(0.0, remaining_taxable - lower_bound) * rate
            break

        upper_bound = float(upper_bound)
        taxable_in_bracket = max(0.0, min(remaining_taxable, upper_bound) - lower_bound)
        total_tax += taxable_in_bracket * rate
        if remaining_taxable <= upper_bound:
            break
        lower_bound = upper_bound

    return total_tax


def estimate_annual_taxes(
    *,
    base_taxable_income: float,
    withdrawal_taxable_income: float,
    tax_system: dict[str, object],
) -> float:
    """Estimate annual taxes from taxable income using the active tax system."""
    taxable_income = max(0.0, base_taxable_income + withdrawal_taxable_income)
    if tax_system.get("mode") == "brackets":
        return calculate_progressive_tax(
            taxable_income=taxable_income,
            standard_deduction=float(tax_system.get("standard_deduction", 0.0)),
            brackets=list(tax_system.get("brackets", [])),
        )
    return taxable_income * float(tax_system.get("rate", 0.0))


def _normalize_withdrawal_order(order) -> list[str]:
    """Return a validated withdrawal order list."""
    valid_steps = set(DEFAULT_WITHDRAWAL_ORDER)
    if not isinstance(order, list):
        return list(DEFAULT_WITHDRAWAL_ORDER)

    normalized: list[str] = []
    for step in order:
        step = str(step).strip()
        if step in valid_steps and step not in normalized:
            normalized.append(step)

    return normalized or list(DEFAULT_WITHDRAWAL_ORDER)


def _cover_deficit_with_policy(
    portfolio: dict[str, float],
    deficit: float,
    assumptions: dict,
    withdrawal_order: list[str],
    cash_target: float,
) -> tuple[float, float]:
    """Cover a deficit using the configured withdrawal policy."""
    remaining = max(0.0, deficit)
    taxable_withdrawals = 0.0

    for step in withdrawal_order:
        if remaining <= 0:
            break

        if step == "cash_above_target":
            available = max(0.0, portfolio.get("cash", 0.0) - cash_target)
            take = min(available, remaining)
            portfolio["cash"] = portfolio.get("cash", 0.0) - take
        elif step == "cash_below_target":
            available = max(0.0, portfolio.get("cash", 0.0))
            take = min(available, remaining)
            portfolio["cash"] = portfolio.get("cash", 0.0) - take
        else:
            available = max(0.0, portfolio.get(step, 0.0))
            take = min(available, remaining)
            portfolio[step] = portfolio.get(step, 0.0) - take
            taxable_withdrawals += take * _withdrawal_taxable_fraction(step, assumptions)

        remaining -= take

    return taxable_withdrawals, remaining


def _apply_surplus_with_reserve_target(
    portfolio: dict[str, float],
    surplus: float,
    cash_target: float,
) -> None:
    """Refill cash to target first, then invest the remaining surplus."""
    if surplus <= 0:
        return

    current_cash = portfolio.get("cash", 0.0)
    refill = min(max(0.0, cash_target - current_cash), surplus)
    portfolio["cash"] = current_cash + refill
    remaining = surplus - refill
    if remaining <= 0:
        return

    positive_non_cash_total = sum(
        balance
        for category, balance in portfolio.items()
        if category != "cash" and balance > 0
    )
    if positive_non_cash_total <= 0:
        portfolio["cash"] = portfolio.get("cash", 0.0) + remaining
        return

    for category, balance in list(portfolio.items()):
        if category != "cash" and balance > 0:
            portfolio[category] += remaining * (balance / positive_non_cash_total)
