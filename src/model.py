"""
model.py — Net Worth Navigator projection engine.

Reads config.toml and a balances dict from monarch_bridge.
Returns a pandas DataFrame with one row per year:

    year | net_worth | matthew_income | weny_income | events_active | ...
"""

from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

from src.config_loader import load_config as shared_load_config
from src.oregon_tax_2025 import OREGON_2025_TAX_TABLE, OREGON_2025_RATE_CHARTS

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"

# ── Event type → emoji icon ────────────────────────────────────────────────────
EVENT_ICONS = {
    "EndOfPlan":      "💀",
    "Retire":         "🎉",
    "SocialSecurity": "🏛️",
    "Expense":        "💸",
    "Income":         "💰",
    "BuyHome":        "🏠",
    "SellHome":       "🏡",
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

VALID_FILING_STATUSES = {"single", "married_joint", "head_of_household"}
WITHDRAWAL_BUCKETS = ("cash", "taxable", "trad_ira", "roth")


def _empty_withdrawal_breakdown() -> dict[str, float]:
    return {bucket: 0.0 for bucket in WITHDRAWAL_BUCKETS}


def load_config(config_path: Path | None = None) -> dict:
    return shared_load_config(config_path or CONFIG_PATH)


def resolve_runtime_config(config: dict) -> dict:
    """Return a runtime-safe config with recurring events expanded to concrete events."""
    runtime = deepcopy(config)
    runtime["events"] = expand_events(
        runtime.get("events", []),
        runtime.get("simulation", {}),
    )
    runtime["events"] = _sync_end_of_plan_years(runtime)
    runtime["events"] = _resolve_retirement_events(runtime)
    runtime["events"] = _resolve_social_security_events(runtime)
    return runtime


def _sync_end_of_plan_years(config: dict) -> list[dict]:
    """Sync EndOfPlan event years to the household dob/life_expectancy settings."""
    synced: list[dict] = []
    for event in config.get("events", []):
        updated = dict(event)
        if updated.get("type") == "EndOfPlan" and updated.get("person"):
            person = config.get(str(updated["person"]), {})
            dob = person.get("dob")
            life_expectancy = person.get("life_expectancy")
            if dob and life_expectancy is not None:
                try:
                    birth_year = int(str(dob).split("-", 1)[0])
                    updated["year"] = birth_year + int(life_expectancy)
                except (TypeError, ValueError):
                    pass
        synced.append(updated)
    return synced


def _resolve_retirement_events(config: dict) -> list[dict]:
    """Return events with Retire derived from person-level retirement settings.

    Person sections are the source of truth for retirement timing.
    Legacy Retire events are treated as compatibility metadata carriers
    (for example label / enabled) and are replaced by synthesized runtime
    events where person settings are complete.
    """
    events = list(config.get("events", []))

    legacy_retire_by_person: dict[str, dict] = {}
    passthrough_events: list[dict] = []
    for event in events:
        etype = event.get("type")
        person_key = str(event.get("person", "")).lower()
        if etype == "Retire" and person_key:
            if person_key not in legacy_retire_by_person:
                legacy_retire_by_person[person_key] = dict(event)
            continue
        passthrough_events.append(dict(event))

    resolved_events = list(passthrough_events)
    handled_person_keys = set()
    for person_key in ("matthew", "weny"):
        handled_person_keys.add(person_key)
        person = config.get(person_key)
        if not isinstance(person, dict):
            if person_key in legacy_retire_by_person:
                resolved_events.append(dict(legacy_retire_by_person[person_key]))
            continue

        synthesized = _synthesize_retire_event(
            person_key=person_key,
            person=person,
            legacy_event=legacy_retire_by_person.get(person_key),
        )
        if synthesized is not None:
            resolved_events.append(synthesized)
            continue

        # Fallback compatibility path: keep a legacy Retire event when
        # person-level fields are incomplete and synthesis is not possible.
        if person_key in legacy_retire_by_person:
            resolved_events.append(dict(legacy_retire_by_person[person_key]))

    # Preserve any Retire events for non-default person keys untouched.
    for person_key, legacy_event in legacy_retire_by_person.items():
        if person_key not in handled_person_keys:
            resolved_events.append(dict(legacy_event))

    return resolved_events


def _synthesize_retire_event(
    *,
    person_key: str,
    person: dict,
    legacy_event: dict | None,
) -> dict | None:
    retirement_year = person.get("retirement_year")
    if retirement_year is None:
        return None

    try:
        retirement_year = int(retirement_year)
    except (TypeError, ValueError):
        return None

    event = {
        "enabled": True,
        "type": "Retire",
        "label": f"Retirement ({person_key[:1].upper()})",
        "person": person_key,
        "year": retirement_year,
    }

    if legacy_event:
        if "enabled" in legacy_event:
            event["enabled"] = legacy_event["enabled"]
        if legacy_event.get("label"):
            event["label"] = legacy_event["label"]
        if "chart_first_occurrence_only" in legacy_event:
            event["chart_first_occurrence_only"] = legacy_event[
                "chart_first_occurrence_only"
            ]

    return event


def _resolve_social_security_events(config: dict) -> list[dict]:
    """Return events with Social Security derived from person-level settings.

    Person sections are the source of truth for SS start age and benefit values.
    Legacy SocialSecurity events are treated as compatibility metadata carriers
    (for example label / taxable_fraction / enabled) and are replaced by
    synthesized runtime events where person settings are complete.
    """
    events = list(config.get("events", []))

    legacy_ss_by_person: dict[str, dict] = {}
    passthrough_events: list[dict] = []
    for event in events:
        etype = event.get("type")
        person_key = str(event.get("person", "")).lower()
        if etype == "SocialSecurity" and person_key:
            if person_key not in legacy_ss_by_person:
                legacy_ss_by_person[person_key] = dict(event)
            continue
        passthrough_events.append(dict(event))

    resolved_events = list(passthrough_events)
    handled_person_keys = set()
    for person_key in ("matthew", "weny"):
        handled_person_keys.add(person_key)
        person = config.get(person_key)
        if not isinstance(person, dict):
            if person_key in legacy_ss_by_person:
                resolved_events.append(dict(legacy_ss_by_person[person_key]))
            continue

        synthesized = _synthesize_social_security_event(
            person_key=person_key,
            person=person,
            legacy_event=legacy_ss_by_person.get(person_key),
        )
        if synthesized is not None:
            resolved_events.append(synthesized)
            continue

        # Fallback compatibility path: keep a legacy SocialSecurity event when
        # person-level fields are incomplete and synthesis is not possible.
        if person_key in legacy_ss_by_person:
            resolved_events.append(dict(legacy_ss_by_person[person_key]))

    # Preserve any SocialSecurity events for non-default person keys untouched.
    for person_key, legacy_event in legacy_ss_by_person.items():
        if person_key not in handled_person_keys:
            resolved_events.append(dict(legacy_event))

    return resolved_events


def _synthesize_social_security_event(
    *,
    person_key: str,
    person: dict,
    legacy_event: dict | None,
) -> dict | None:
    dob = person.get("dob")
    ss_start_age = person.get("ss_start_age")
    if not dob or ss_start_age is None:
        return None

    try:
        birth_year = int(str(dob).split("-", 1)[0])
        start_year = birth_year + int(ss_start_age)
    except (TypeError, ValueError):
        return None

    monthly_benefit = _resolve_social_security_monthly_benefit(
        person,
        ss_start_age=ss_start_age,
    )
    if monthly_benefit is None:
        return None

    try:
        monthly_benefit = float(monthly_benefit)
    except (TypeError, ValueError):
        return None

    event = {
        "enabled": True,
        "type": "SocialSecurity",
        "label": f"SS Begins ({person_key[:1].upper()})",
        "person": person_key,
        "year": start_year,
        "monthly_benefit": monthly_benefit,
    }

    if legacy_event:
        if "enabled" in legacy_event:
            event["enabled"] = legacy_event["enabled"]
        if legacy_event.get("label"):
            event["label"] = legacy_event["label"]
        for field in ("taxable", "taxable_fraction", "chart_first_occurrence_only"):
            if field in legacy_event:
                event[field] = legacy_event[field]

    return event


def _resolve_social_security_monthly_benefit(
    person: dict,
    *,
    ss_start_age,
) -> float | None:
    """Return the configured SS monthly benefit for the selected start age."""
    benefit_schedule = person.get("social_security_benefits")
    if isinstance(benefit_schedule, dict) and ss_start_age is not None:
        lookup_keys = []
        try:
            lookup_keys.append(str(int(ss_start_age)))
        except (TypeError, ValueError):
            lookup_keys.append(str(ss_start_age))
        lookup_keys.append(ss_start_age)

        for key in lookup_keys:
            if key in benefit_schedule:
                return benefit_schedule[key]

    return person.get("ss_monthly_benefit")


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


def _initial_property_state(
    *,
    home_value: float,
    property_values: dict[str, float] | None,
) -> dict[str, float]:
    """Return the tracked property-value state for the simulation."""
    if property_values:
        return {str(name): float(value) for name, value in property_values.items()}
    if home_value != 0:
        return {"Primary Residence": float(home_value)}
    return {}


def _sell_home_property_name(event: dict) -> str:
    """Return the property/account name referenced by a SellHome event."""
    property_name = event.get("property") or event.get("account")
    if not property_name:
        raise ValueError(
            f"SellHome event '{event.get('label', '?')}' must define property or account"
        )
    return str(property_name)


def _sell_home_fee_rate(event: dict, assumptions: dict) -> float:
    """Return the sale-fee rate for a SellHome event."""
    raw_rate = event.get(
        "sale_fee_rate",
        assumptions.get("real_estate_sale_fee_rate", 0.06),
    )
    try:
        rate = float(raw_rate)
    except (TypeError, ValueError):
        rate = 0.06
    return max(0.0, min(1.0, rate))


def _sell_home_reinvest_target(event: dict) -> str | None:
    """Return the optional destination bucket for post-sale reinvestment."""
    raw_target = event.get("reinvest_to")
    if raw_target is None:
        return None
    target = str(raw_target).strip().lower()
    if target in {"", "cash", "none"}:
        return None
    if target != "taxable":
        raise ValueError(
            f"SellHome event '{event.get('label', '?')}' has unsupported reinvest_to '{raw_target}'. "
            "Use 'taxable' or omit it to keep proceeds in cash."
        )
    return target


def _sell_home_reinvest_fraction(event: dict) -> float:
    """Return the optional fraction of net proceeds to reinvest after a sale."""
    raw_fraction = event.get("reinvest_fraction", 1.0)
    try:
        fraction = float(raw_fraction)
    except (TypeError, ValueError):
        fraction = 1.0
    return max(0.0, min(1.0, fraction))


def _resolve_sell_home_liabilities(
    event: dict,
    lib_state: list[dict],
    property_state: dict[str, float],
) -> list[dict]:
    """Return mortgage liabilities that should be cleared by a home sale."""
    requested = event.get("liability_names")
    if requested is None and event.get("liability_name"):
        requested = [event["liability_name"]]

    liabilities_by_name = {str(lib["name"]): lib for lib in lib_state}

    if requested is not None:
        if isinstance(requested, str):
            requested_names = [requested]
        else:
            requested_names = [str(name) for name in requested]
        missing = [name for name in requested_names if name not in liabilities_by_name]
        if missing:
            raise ValueError(
                f"SellHome event '{event.get('label', '?')}' references unknown liabilities: {', '.join(missing)}"
            )
        return [liabilities_by_name[name] for name in requested_names]

    active_properties = [
        name for name, value in property_state.items()
        if float(value) > 0
    ]
    if len(active_properties) <= 1:
        return [
            lib for lib in lib_state
            if lib.get("type") == "mortgage" and float(lib.get("balance", 0.0)) > 0
        ]

    raise ValueError(
        f"SellHome event '{event.get('label', '?')}' must specify liability_names when multiple active properties exist"
    )


def resolve_withdrawal_policy(config: dict, balances: dict[str, float]) -> dict[str, object]:
    """Return phase-specific withdrawal policy with sensible defaults."""
    section = config.get("withdrawal_policy", {})
    spending = config.get("spending", {})
    current_cash = round(float(balances.get("cash", 0.0)), 2)
    retirement_spend = float(spending.get("retirement_annual", 0.0))
    survivor_spend = resolve_survivor_spending(spending)

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


def resolve_survivor_spending(spending: dict) -> float:
    """Return survivor annual spending from percent-of-retirement or legacy fallback."""
    retirement_spend = float(spending.get("retirement_annual", 0.0))
    survivor_ratio = spending.get("survivor_percent_of_retirement")
    if survivor_ratio is not None:
        try:
            return retirement_spend * float(survivor_ratio)
        except (TypeError, ValueError):
            pass
    return float(spending.get("survivor_annual", round(retirement_spend * 0.70)))


def _combined_annual_growth_rate(*rates) -> float:
    """Return the compounded annual growth rate produced by multiple components."""
    factor = 1.0
    for raw_rate in rates:
        try:
            factor *= 1.0 + float(raw_rate)
        except (TypeError, ValueError):
            continue
    return factor - 1.0


def _grow_annual_amount(base_amount, annual_rate: float, years_elapsed: int) -> float:
    """Return a base annual amount grown by a compounded annual rate."""
    try:
        amount = float(base_amount)
    except (TypeError, ValueError):
        return 0.0
    years_elapsed = max(0, int(years_elapsed))
    return amount * ((1.0 + float(annual_rate)) ** years_elapsed)


def _person_income_growth_rate(person: dict, assumptions: dict) -> float:
    """Return annual take-home growth from inflation plus real raise."""
    return _combined_annual_growth_rate(
        assumptions.get("inflation", 0.0),
        person.get("annual_take_home_real_raise", 0.0),
    )


def _person_401k_growth_rate(person: dict, assumptions: dict) -> float:
    """Return annual 401(k) growth from income growth plus elective step-up."""
    return _combined_annual_growth_rate(
        _person_income_growth_rate(person, assumptions),
        person.get("annual_401k_contribution_extra_increase", 0.0),
    )


def resolve_spending_basis(spending: dict) -> str:
    """Return configured spending basis: real (inflation-indexed) or nominal."""
    basis = str(spending.get("spending_basis", "real")).strip().lower()
    return "nominal" if basis == "nominal" else "real"


def resolve_cash_growth_rate(assumptions: dict) -> float:
    """Return annual nominal growth for cash buckets.

    Defaults to inflation when cash_return is not provided.
    """
    try:
        return float(assumptions.get("cash_return", assumptions.get("inflation", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def resolve_pre_retirement_spending(
    spending: dict,
    *,
    total_income: float,
    total_contrib: float,
    assumptions: dict,
    year: int,
    simulation_start_year: int,
) -> float:
    """Return pre-retirement annual spending with explicit override precedence.

    Precedence:
    1) spending.pre_retirement_spending
    2) spending.annual_savings_override
    3) implied spending = total_income - total_contrib
    """
    implied_spend = max(0.0, float(total_income) - float(total_contrib))

    if "pre_retirement_spending" in spending:
        try:
            configured = float(spending.get("pre_retirement_spending", implied_spend))
        except (TypeError, ValueError):
            return implied_spend
        if resolve_spending_basis(spending) == "real":
            configured = _grow_annual_amount(
                configured,
                assumptions.get("inflation", 0.0),
                year - simulation_start_year,
            )
        return max(0.0, configured)

    if "annual_savings_override" in spending:
        try:
            savings_override = float(spending.get("annual_savings_override", 0.0))
        except (TypeError, ValueError):
            return implied_spend
        return max(0.0, float(total_income) - savings_override)

    return implied_spend


def resolve_wage_tax_treatment(config: dict) -> str:
    """Return wage tax treatment mode for pre-retirement earned income.

    Modes:
    - net_cash (default): wages are cashflow-only, excluded from taxable base
    - taxable_wages: wages are included in taxable ordinary income
    """
    taxes = config.get("taxes", {}) if isinstance(config, dict) else {}
    mode = str(taxes.get("wage_tax_treatment", "net_cash")).strip().lower()
    return "taxable_wages" if mode == "taxable_wages" else "net_cash"


def _project_person_take_home(
    person: dict,
    *,
    year: int,
    simulation_start_year: int,
    assumptions: dict,
    base_amount=None,
    anchor_year: int | None = None,
) -> float:
    """Return grown annual take-home income for the active pre-retirement baseline."""
    if anchor_year is None:
        anchor_year = simulation_start_year
    if base_amount is None:
        base_amount = person.get("annual_take_home", 0.0)
    return _grow_annual_amount(
        base_amount,
        _person_income_growth_rate(person, assumptions),
        year - anchor_year,
    )


def _project_person_401k_contribution(
    person: dict,
    *,
    year: int,
    simulation_start_year: int,
    assumptions: dict,
) -> float:
    """Return grown annual 401(k) contribution for the current pre-retirement year."""
    return _grow_annual_amount(
        person.get("annual_401k_contribution", 0.0),
        _person_401k_growth_rate(person, assumptions),
        year - simulation_start_year,
    )


def _normalize_contribution_bucket(raw_bucket: object, *, default: str) -> str:
    """Return a valid portfolio bucket for contribution routing."""
    bucket = str(raw_bucket or default).strip().lower()
    return bucket if bucket in {"trad_ira", "roth"} else default


def _as_bool(value: object, default: bool = False) -> bool:
    """Parse permissive bool-like config values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _take_home_is_net_of_retirement_contributions(person: dict) -> bool:
    """Whether annual_take_home already excludes payroll retirement contributions.

    When true, retirement contributions are treated as payroll-prefunded and should
    not be subtracted again from implied pre-retirement spending cash.
    """
    return _as_bool(
        person.get("annual_take_home_is_net_of_retirement_contributions"),
        default=False,
    )


def _person_retirement_contribution_breakdown(
    person: dict,
    *,
    year: int,
    simulation_start_year: int,
    assumptions: dict,
) -> dict[str, float]:
    """Return current-year retirement contributions by destination bucket.

    Defaults:
    - 401(k) -> trad_ira
    - IRA -> roth
    """
    annual_401k = _project_person_401k_contribution(
        person,
        year=year,
        simulation_start_year=simulation_start_year,
        assumptions=assumptions,
    )
    try:
        annual_ira = float(person.get("annual_ira_contribution", 0.0))
    except (TypeError, ValueError):
        annual_ira = 0.0

    bucket_401k = _normalize_contribution_bucket(
        person.get("annual_401k_contribution_bucket"),
        default="trad_ira",
    )
    bucket_ira = _normalize_contribution_bucket(
        person.get("annual_ira_contribution_bucket"),
        default="roth",
    )

    breakdown = {"trad_ira": 0.0, "roth": 0.0}
    breakdown[bucket_401k] += max(0.0, annual_401k)
    breakdown[bucket_ira] += max(0.0, annual_ira)
    return breakdown


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
    property_values: dict[str, float] | None = None,
    config: dict | None = None,
) -> pd.DataFrame:
    """
    Run the year-by-year net worth projection.

    balances: dict from monarch_bridge — {category: total_balance}
    Returns: DataFrame with projection data
    """
    config = resolve_runtime_config(config or load_config())
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
    # property values grow at inflation; mortgage balance is tracked in lib_state
    property_state = _initial_property_state(
        home_value=home_value,
        property_values=property_values,
    )
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
        cash_preserve_flow = 0.0
        pending_reinvestments: list[tuple[str, float]] = []
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
                    if should_show_chart_label(event):
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

            elif etype == "SellHome":
                if event["year"] == year:
                    property_name = _sell_home_property_name(event)
                    if property_name not in property_state:
                        raise ValueError(
                            f"SellHome event '{event.get('label', '?')}' references unknown property '{property_name}'"
                        )

                    property_value = float(property_state[property_name])
                    sale_fee_rate = _sell_home_fee_rate(event, assumptions)
                    sale_liabilities = _resolve_sell_home_liabilities(
                        event,
                        lib_state,
                        property_state,
                    )
                    mortgage_payoff = sum(
                        float(lib.get("balance", 0.0)) for lib in sale_liabilities
                    )
                    sale_fees = property_value * sale_fee_rate
                    net_proceeds = property_value - sale_fees - mortgage_payoff

                    event_cash_flow += net_proceeds
                    cash_preserve_flow += max(0.0, net_proceeds)
                    reinvest_target = _sell_home_reinvest_target(event)
                    if reinvest_target and net_proceeds > 0:
                        reinvest_amount = net_proceeds * _sell_home_reinvest_fraction(event)
                        if reinvest_amount > 0:
                            pending_reinvestments.append((reinvest_target, reinvest_amount))
                    event_items.append(
                        make_event_item(
                            label=event["label"],
                            amount=net_proceeds,
                            event_type="SellHome",
                        )
                    )
                    property_state[property_name] = 0.0

                    for lib in sale_liabilities:
                        prior_balance = float(lib.get("balance", 0.0))
                        if prior_balance <= 0:
                            continue
                        lib["balance"] = 0.0
                        lib["paid_off"] = True
                        if lib.get("payoff_year") is None:
                            lib["payoff_year"] = year
                        short_name = lib["name"].split("(")[0].strip()
                        icon = LIABILITY_ICONS.get(lib.get("type", "other"), "✅")
                        payoff_labels.append(f"{icon} {short_name} paid off")
                        freed_this_year += float(lib.get("monthly_total", 0.0)) * 12

                    icon = EVENT_ICONS["SellHome"]
                    if should_show_chart_label(event):
                        active_labels.append(f"{icon} {event['label']}")

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

        mortgage_balance = sum(
            s["balance"] for s in lib_state if s["type"] == "mortgage"
        )

        # ── Income for this year ───────────────────────────────────────────────
        include_taxable_wages = resolve_wage_tax_treatment(config) == "taxable_wages"
        matthew_parts = _person_income_components(
            matthew,
            year,
            events,
            assumptions=assumptions,
            simulation_start_year=start_year,
            deceased=matthew_deceased,
            include_taxable_wages=include_taxable_wages,
        )
        weny_parts = _person_income_components(
            weny,
            year,
            events,
            assumptions=assumptions,
            simulation_start_year=start_year,
            deceased=weny_deceased,
            include_taxable_wages=include_taxable_wages,
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

        matthew_contrib_buckets = (
            {"trad_ira": 0.0, "roth": 0.0}
            if matthew_retired
            else _person_retirement_contribution_breakdown(
                matthew,
                year=year,
                simulation_start_year=start_year,
                assumptions=assumptions,
            )
        )
        weny_contrib_buckets = (
            {"trad_ira": 0.0, "roth": 0.0}
            if weny_retired
            else _person_retirement_contribution_breakdown(
                weny,
                year=year,
                simulation_start_year=start_year,
                assumptions=assumptions,
            )
        )

        prefunded_contrib_buckets = {"trad_ira": 0.0, "roth": 0.0}
        cash_required_contrib_buckets = {"trad_ira": 0.0, "roth": 0.0}

        matthew_prefunded = _take_home_is_net_of_retirement_contributions(matthew)
        weny_prefunded = _take_home_is_net_of_retirement_contributions(weny)

        for bucket in ("trad_ira", "roth"):
            if matthew_prefunded:
                prefunded_contrib_buckets[bucket] += matthew_contrib_buckets[bucket]
            else:
                cash_required_contrib_buckets[bucket] += matthew_contrib_buckets[bucket]

            if weny_prefunded:
                prefunded_contrib_buckets[bucket] += weny_contrib_buckets[bucket]
            else:
                cash_required_contrib_buckets[bucket] += weny_contrib_buckets[bucket]

        total_cash_required_contrib = sum(cash_required_contrib_buckets.values())

        # ── Net cash flow for the year ─────────────────────────────────────────
        target_spend   = spending.get("retirement_annual", 0)
        survivor_spend = resolve_survivor_spending(spending)
        both_retired   = matthew_retired and weny_retired
        one_deceased   = matthew_deceased or weny_deceased

        if both_retired:
            base_spend = survivor_spend if one_deceased else target_spend
            annual_spend = base_spend
            if resolve_spending_basis(spending) == "real":
                annual_spend = _grow_annual_amount(
                    base_spend,
                    assumptions.get("inflation", 0.0),
                    year - start_year,
                )
        else:
            annual_spend = resolve_pre_retirement_spending(
                spending,
                total_income=total_income,
                total_contrib=total_cash_required_contrib,
                assumptions=assumptions,
                year=year,
                simulation_start_year=start_year,
            )

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
        active_state_tax_system = resolve_state_tax_system(
            config,
            filing_status=str(active_tax_system.get("filing_status", "married_joint")),
        )
        taxable_wage_income = (
            matthew_parts["taxable_wage_income"] + weny_parts["taxable_wage_income"]
        )
        base_non_ss_taxable_income = taxable_event_income + taxable_wage_income
        total_social_security_income = (
            matthew_parts["ss_income"] + weny_parts["ss_income"]
        )
        legacy_ss_taxable_income = (
            matthew_parts["ss_taxable_income"] + weny_parts["ss_taxable_income"]
        )

        # Cash flow before any taxes or withdrawal sequencing
        base_net_flow = total_income - annual_spend + event_cash_flow + freed_this_year

        # ── Grow portfolio ─────────────────────────────────────────────────────
        invested_growth_rate = (
            assumptions["stock_return"] * assumptions["equity_allocation"] +
            assumptions["bond_return"] * (1 - assumptions["equity_allocation"])
        )
        cash_growth_rate = resolve_cash_growth_rate(assumptions)
        current_total = sum(portfolio.values())
        if current_total > 0:
            grown_portfolio = {
                cat: balance * (
                    1 + (cash_growth_rate if cat == "cash" else invested_growth_rate)
                )
                for cat, balance in portfolio.items()
            }
        else:
            grown_portfolio = portfolio.copy()

        annual_taxes, taxable_income, federal_taxes, state_taxes = estimate_annual_taxes(
            non_ss_taxable_income=base_non_ss_taxable_income,
            social_security_income=total_social_security_income,
            withdrawal_taxable_income=0.0,
            tax_system=active_tax_system,
            state_tax_system=active_state_tax_system,
            legacy_ss_taxable_income=legacy_ss_taxable_income,
        )
        withdrawal_taxable_income = 0.0
        withdrawal_breakdown = _empty_withdrawal_breakdown()
        contribution_breakdown = prefunded_contrib_buckets.copy()
        working_portfolio = grown_portfolio.copy()

        # Iterate because taxable withdrawals themselves increase taxes.
        for _ in range(12):
            working_portfolio = grown_portfolio.copy()
            contribution_breakdown = prefunded_contrib_buckets.copy()
            for bucket, amount in prefunded_contrib_buckets.items():
                if amount > 0:
                    working_portfolio[bucket] = working_portfolio.get(bucket, 0.0) + amount

            post_tax_flow = base_net_flow - annual_taxes

            if post_tax_flow >= 0:
                preserved_cash = min(post_tax_flow, cash_preserve_flow)
                if preserved_cash > 0:
                    working_portfolio["cash"] = working_portfolio.get("cash", 0.0) + preserved_cash

                available_for_contrib = max(0.0, post_tax_flow - preserved_cash)
                trad_contrib = min(cash_required_contrib_buckets["trad_ira"], available_for_contrib)
                available_for_contrib -= trad_contrib
                roth_contrib = min(cash_required_contrib_buckets["roth"], available_for_contrib)
                available_for_contrib -= roth_contrib
                if trad_contrib > 0:
                    working_portfolio["trad_ira"] = working_portfolio.get("trad_ira", 0.0) + trad_contrib
                if roth_contrib > 0:
                    working_portfolio["roth"] = working_portfolio.get("roth", 0.0) + roth_contrib
                contribution_breakdown["trad_ira"] += trad_contrib
                contribution_breakdown["roth"] += roth_contrib

                _apply_surplus_with_reserve_target(
                    working_portfolio,
                    surplus=available_for_contrib,
                    cash_target=cash_target,
                )
                withdrawal_taxable_income = 0.0
                withdrawal_breakdown = _empty_withdrawal_breakdown()
            else:
                withdrawal_taxable_income, unmet_deficit, withdrawal_breakdown = _cover_deficit_with_policy(
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

            new_annual_taxes, taxable_income, federal_taxes, state_taxes = estimate_annual_taxes(
                non_ss_taxable_income=base_non_ss_taxable_income,
                social_security_income=total_social_security_income,
                withdrawal_taxable_income=withdrawal_taxable_income,
                tax_system=active_tax_system,
                state_tax_system=active_state_tax_system,
                legacy_ss_taxable_income=legacy_ss_taxable_income,
            )
            if abs(new_annual_taxes - annual_taxes) < 0.01:
                annual_taxes = new_annual_taxes
                break
            annual_taxes = new_annual_taxes

        portfolio = working_portfolio
        for reinvest_target, requested_amount in pending_reinvestments:
            move_amount = min(
                max(0.0, portfolio.get("cash", 0.0)),
                max(0.0, requested_amount),
            )
            if move_amount <= 0:
                continue
            portfolio["cash"] = portfolio.get("cash", 0.0) - move_amount
            portfolio[reinvest_target] = portfolio.get(reinvest_target, 0.0) + move_amount
        net_flow = base_net_flow - annual_taxes

        # ── Grow home value at configured real-estate appreciation; compute equity ──
        total_portfolio = sum(portfolio.values())
        real_estate_growth = float(
            assumptions.get("real_estate_appreciation", assumptions["inflation"])
        )
        for property_name in list(property_state):
            property_state[property_name] *= (1 + real_estate_growth)
        current_home_value = sum(property_state.values())
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
            "taxable_wage_income": taxable_wage_income,
            "annual_taxes":   annual_taxes,
            "annual_federal_taxes": federal_taxes,
            "annual_state_taxes": state_taxes,
            "annual_spend":   annual_spend,
            "freed_payments": freed_this_year,
            "net_flow":       net_flow,
            "withdrawal_cash": withdrawal_breakdown["cash"],
            "withdrawal_taxable": withdrawal_breakdown["taxable"],
            "withdrawal_trad_ira": withdrawal_breakdown["trad_ira"],
            "withdrawal_roth": withdrawal_breakdown["roth"],
            "contribution_trad_ira": contribution_breakdown["trad_ira"],
            "contribution_roth": contribution_breakdown["roth"],
            "contribution_total": contribution_breakdown["trad_ira"] + contribution_breakdown["roth"],
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
    person: dict,
    year: int,
    events: list,
    *,
    assumptions: dict,
    simulation_start_year: int,
    deceased: bool = False,
    include_taxable_wages: bool = False,
) -> dict[str, float]:
    """Return earned-net and SS-gross components for a person's annual cash income."""
    if deceased:
        return {
            "earned_income": 0.0,
            "taxable_wage_income": 0.0,
            "ss_income": 0.0,
            "ss_taxable_income": 0.0,
            "cash_income": 0.0,
        }

    person_key = person["name"].lower()
    earned_income = _project_person_take_home(
        person,
        year=year,
        simulation_start_year=simulation_start_year,
        assumptions=assumptions,
    )
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
                earned_income = _project_person_take_home(
                    person,
                    year=year,
                    simulation_start_year=simulation_start_year,
                    assumptions=assumptions,
                    base_amount=event.get("annual_income", 0.0),
                    anchor_year=int(event["year"]),
                )

    taxable_wage_income = earned_income if include_taxable_wages else 0.0
    return {
        "earned_income": earned_income,
        "taxable_wage_income": taxable_wage_income,
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
    if filing_status not in VALID_FILING_STATUSES:
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
            "social_security": dict(taxes.get("social_security", {})),
        }

    return {
        "mode": "effective_rate",
        "rate": float(
            assumptions["effective_tax_rate_post_retirement"]
            if both_retired else assumptions["effective_tax_rate_pre_retirement"]
        ),
    }


def resolve_state_tax_system(
    config: dict,
    *,
    filing_status: str,
) -> dict[str, object]:
    """Return the active state tax system, if any."""
    state = config.get("taxes", {}).get("state", {})
    if not state.get("enabled"):
        return {"enabled": False}

    state_name = str(state.get("name", "")).strip().lower()
    filing_status = filing_status if filing_status in VALID_FILING_STATUSES else "married_joint"

    if state_name == "oregon":
        return {
            "enabled": True,
            "name": "oregon",
            "filing_status": filing_status,
            "standard_deduction": float(state.get("standard_deduction", {}).get(filing_status, 0.0)),
            "tax_social_security": bool(state.get("tax_social_security", False)),
        }

    return {"enabled": False}


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
    non_ss_taxable_income: float,
    social_security_income: float,
    withdrawal_taxable_income: float,
    tax_system: dict[str, object],
    state_tax_system: dict[str, object],
    legacy_ss_taxable_income: float = 0.0,
) -> tuple[float, float, float, float]:
    """Estimate annual federal+state taxes and total modeled taxable income."""
    other_taxable_income = max(0.0, non_ss_taxable_income + withdrawal_taxable_income)
    taxable_ss_income = 0.0
    if tax_system.get("mode") == "brackets":
        taxable_ss_income = calculate_social_security_taxable_income(
            social_security_income=max(0.0, social_security_income),
            other_taxable_income=other_taxable_income,
            filing_status=str(tax_system.get("filing_status", "married_joint")),
            social_security_config=dict(tax_system.get("social_security", {})),
        )
        taxable_income = other_taxable_income + taxable_ss_income
        federal_taxes = calculate_progressive_tax(
            taxable_income=taxable_income,
            standard_deduction=float(tax_system.get("standard_deduction", 0.0)),
            brackets=list(tax_system.get("brackets", [])),
        )
    else:
        taxable_income = max(0.0, other_taxable_income + legacy_ss_taxable_income)
        federal_taxes = taxable_income * float(tax_system.get("rate", 0.0))
        taxable_ss_income = legacy_ss_taxable_income

    state_taxes = estimate_state_taxes(
        non_ss_taxable_income=other_taxable_income,
        social_security_taxable_income=taxable_ss_income,
        state_tax_system=state_tax_system,
    )
    total_taxes = federal_taxes + state_taxes
    return total_taxes, taxable_income, federal_taxes, state_taxes


def estimate_state_taxes(
    *,
    non_ss_taxable_income: float,
    social_security_taxable_income: float,
    state_tax_system: dict[str, object],
) -> float:
    """Estimate state tax from modeled taxable inflows."""
    if not state_tax_system.get("enabled"):
        return 0.0
    if state_tax_system.get("name") != "oregon":
        return 0.0

    filing_status = str(state_tax_system.get("filing_status", "married_joint"))
    state_taxable_income = max(0.0, non_ss_taxable_income)
    if state_tax_system.get("tax_social_security", False):
        state_taxable_income += max(0.0, social_security_taxable_income)
    state_taxable_income = max(0.0, state_taxable_income - float(state_tax_system.get("standard_deduction", 0.0)))
    return calculate_oregon_state_tax(
        taxable_income=state_taxable_income,
        filing_status=filing_status,
    )


def calculate_oregon_state_tax(*, taxable_income: float, filing_status: str) -> float:
    """Calculate 2025 Oregon personal income tax from official OR-40 tables/charts."""
    taxable_income = max(0.0, float(taxable_income))
    chart = OREGON_2025_RATE_CHARTS.get(filing_status, OREGON_2025_RATE_CHARTS["married_joint"])

    if taxable_income < chart["base_threshold"]:
        column_index = 2 if chart["table_column"] == "S" else 3
        for lower, upper, s_tax, j_tax in OREGON_2025_TAX_TABLE:
            if lower <= taxable_income < upper:
                return float(s_tax if column_index == 2 else j_tax)
        return float(OREGON_2025_TAX_TABLE[-1][2 if column_index == 2 else 3])

    if taxable_income <= chart["upper_threshold"]:
        return float(round(chart["base_tax"] + ((taxable_income - chart["base_threshold"]) * chart["middle_rate"])))
    return float(round(chart["top_base_tax"] + ((taxable_income - chart["upper_threshold"]) * chart["top_rate"])))


def calculate_social_security_taxable_income(
    *,
    social_security_income: float,
    other_taxable_income: float,
    filing_status: str,
    social_security_config: dict,
) -> float:
    """Return modeled taxable Social Security income using provisional-income bands."""
    if social_security_income <= 0:
        return 0.0
    if not social_security_config.get("use_provisional_income", True):
        return social_security_income * float(social_security_config.get("default_taxable_fraction", 0.85))

    thresholds = social_security_config.get("thresholds", {})
    status_thresholds = thresholds.get(filing_status, thresholds.get("single", {}))
    base = float(status_thresholds.get("base", 25_000.0))
    adjusted = float(status_thresholds.get("adjusted", 34_000.0))
    provisional_income = max(0.0, other_taxable_income) + (social_security_income * 0.5)

    if provisional_income <= base:
        fraction = 0.0
    elif provisional_income <= adjusted:
        fraction = 0.50
    else:
        fraction = 0.85
    return social_security_income * fraction


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
) -> tuple[float, float, dict[str, float]]:
    """Cover a deficit using the configured withdrawal policy."""
    remaining = max(0.0, deficit)
    taxable_withdrawals = 0.0
    breakdown = _empty_withdrawal_breakdown()

    for step in withdrawal_order:
        if remaining <= 0:
            break

        if step == "cash_above_target":
            available = max(0.0, portfolio.get("cash", 0.0) - cash_target)
            take = min(available, remaining)
            portfolio["cash"] = portfolio.get("cash", 0.0) - take
            breakdown["cash"] += take
        elif step == "cash_below_target":
            available = max(0.0, portfolio.get("cash", 0.0))
            take = min(available, remaining)
            portfolio["cash"] = portfolio.get("cash", 0.0) - take
            breakdown["cash"] += take
        else:
            available = max(0.0, portfolio.get(step, 0.0))
            take = min(available, remaining)
            portfolio[step] = portfolio.get(step, 0.0) - take
            breakdown[step] += take
            taxable_withdrawals += take * _withdrawal_taxable_fraction(step, assumptions)

        remaining -= take

    return taxable_withdrawals, remaining, breakdown


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
