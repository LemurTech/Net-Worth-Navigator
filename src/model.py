"""
model.py — Net Worth Navigator projection engine.

Reads config.toml and a balances dict from monarch_bridge.
Returns a pandas DataFrame with one row per year:

    year | net_worth | person1_income | person2_income | events_active | ...
"""

from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass, field
import random

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
    "SpendingShift":  "🌍",
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

# Surplus routing preference when investing cash above reserve targets.
# Typical retirement behavior: sweep excess to taxable first.
DEFAULT_SURPLUS_ORDER = ["taxable", "roth", "trad_ira"]

DEFAULT_TAX_FILING_STATUS = {
    "pre_retirement": "married_joint",
    "retirement": "married_joint",
    "survivor": "single",
}

VALID_FILING_STATUSES = {"single", "married_joint", "head_of_household"}
WITHDRAWAL_BUCKETS = ("cash", "taxable", "trad_ira", "roth")
RETIREMENT_OWNER_KEYS = ("person1", "person2")
PROJECTION_RESULT_SCHEMA_VERSION = 1

# IRS Uniform Lifetime Table factors (2022+), used for RMD calculation.
# Applies to account owners age 72+; 120+ reuses age-120 factor.
UNIFORM_LIFETIME_FACTORS = {
    72: 27.4,
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22.0,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16.0,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
    95: 8.9,
    96: 8.4,
    97: 7.8,
    98: 7.3,
    99: 6.8,
    100: 6.4,
    101: 6.0,
    102: 5.6,
    103: 5.2,
    104: 4.9,
    105: 4.6,
    106: 4.3,
    107: 4.1,
    108: 3.9,
    109: 3.7,
    110: 3.5,
    111: 3.4,
    112: 3.3,
    113: 3.1,
    114: 3.0,
    115: 2.9,
    116: 2.8,
    117: 2.7,
    118: 2.5,
    119: 2.3,
    120: 2.0,
}


@dataclass
class ProjectionResult:
    """Normalized projection output for deterministic and stochastic modes."""

    mode: str
    yearly_df: pd.DataFrame
    summary: dict[str, object]
    simulation: dict[str, object]
    band_df: pd.DataFrame | None = None
    run_count: int = 1
    display_path_kind: str = "deterministic"


def _empty_withdrawal_breakdown() -> dict[str, float]:
    return {bucket: 0.0 for bucket in WITHDRAWAL_BUCKETS}


def _empty_retirement_owner_breakdown() -> dict[str, dict[str, float]]:
    return {
        key: {"trad_ira": 0.0, "roth": 0.0}
        for key in RETIREMENT_OWNER_KEYS
    }


def _clone_retirement_owner_balances(
    owner_balances: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    return {
        "trad_ira": {
            "person1": float(owner_balances.get("trad_ira", {}).get("person1", 0.0)),
            "person2": float(owner_balances.get("trad_ira", {}).get("person2", 0.0)),
        },
        "roth": {
            "person1": float(owner_balances.get("roth", {}).get("person1", 0.0)),
            "person2": float(owner_balances.get("roth", {}).get("person2", 0.0)),
        },
    }


def _normalize_two_person_shares(raw_1, raw_2) -> dict[str, float]:
    try:
        share_1 = max(0.0, float(raw_1)) if raw_1 is not None else 0.0
    except (TypeError, ValueError):
        share_1 = 0.0
    try:
        share_2 = max(0.0, float(raw_2)) if raw_2 is not None else 0.0
    except (TypeError, ValueError):
        share_2 = 0.0

    total = share_1 + share_2
    if total > 0:
        return {
            "person1": share_1 / total,
            "person2": share_2 / total,
        }
    return {"person1": 0.5, "person2": 0.5}


def _initial_retirement_owner_state(
    *,
    portfolio: dict[str, float],
    person1: dict,
    person2: dict,
    seeded_owner_balances: dict[str, dict[str, float]] | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    trad_shares = _normalized_household_rmd_shares(
        person1=person1,
        person2=person2,
        person1_deceased=False,
        person2_deceased=False,
    )
    roth_shares = _normalize_two_person_shares(
        person1.get("roth_share"),
        person2.get("roth_share"),
    )

    owner_balances = {
        "trad_ira": _resolve_initial_owner_bucket(
            total_balance=float(portfolio.get("trad_ira", 0.0)),
            seeded_bucket=(seeded_owner_balances or {}).get("trad_ira"),
            fallback_shares=trad_shares,
        ),
        "roth": _resolve_initial_owner_bucket(
            total_balance=float(portfolio.get("roth", 0.0)),
            seeded_bucket=(seeded_owner_balances or {}).get("roth"),
            fallback_shares=roth_shares,
        ),
    }
    defaults = {
        "trad_ira": dict(trad_shares),
        "roth": dict(roth_shares),
    }
    return owner_balances, defaults


def _resolve_initial_owner_bucket(
    *,
    total_balance: float,
    seeded_bucket: dict[str, float] | None,
    fallback_shares: dict[str, float],
) -> dict[str, float]:
    """Return owner balances for a retirement bucket using seeded account owners first."""
    total_balance = max(0.0, float(total_balance))
    seeded_person1 = 0.0
    seeded_person2 = 0.0
    if isinstance(seeded_bucket, dict):
        try:
            seeded_person1 = max(0.0, float(seeded_bucket.get("person1", 0.0)))
        except (TypeError, ValueError):
            seeded_person1 = 0.0
        try:
            seeded_person2 = max(0.0, float(seeded_bucket.get("person2", 0.0)))
        except (TypeError, ValueError):
            seeded_person2 = 0.0

    assigned = seeded_person1 + seeded_person2
    if assigned > total_balance and assigned > 0.0:
        scale = total_balance / assigned
        seeded_person1 *= scale
        seeded_person2 *= scale
        assigned = total_balance

    remainder = max(0.0, total_balance - assigned)
    return {
        "person1": seeded_person1 + (remainder * fallback_shares["person1"]),
        "person2": seeded_person2 + (remainder * fallback_shares["person2"]),
    }


def _owner_split_for_bucket(
    owner_bucket: dict[str, float],
    fallback_shares: dict[str, float],
) -> dict[str, float]:
    person1_balance = max(0.0, float(owner_bucket.get("person1", 0.0)))
    person2_balance = max(0.0, float(owner_bucket.get("person2", 0.0)))
    total = person1_balance + person2_balance
    if total > 0:
        return {
            "person1": person1_balance / total,
            "person2": person2_balance / total,
        }
    return dict(fallback_shares)


def _apply_owner_bucket_withdrawal(
    owner_balances: dict[str, dict[str, float]],
    *,
    bucket: str,
    amount: float,
    fallback_shares: dict[str, float],
) -> dict[str, float]:
    if bucket not in {"trad_ira", "roth"}:
        return {"person1": 0.0, "person2": 0.0}

    owner_bucket = owner_balances[bucket]
    available = max(0.0, float(owner_bucket.get("person1", 0.0))) + max(
        0.0, float(owner_bucket.get("person2", 0.0))
    )
    withdrawn = min(max(0.0, float(amount)), available)
    if withdrawn <= 0:
        return {"person1": 0.0, "person2": 0.0}

    split = _owner_split_for_bucket(owner_bucket, fallback_shares)
    person1_withdrawn = min(
        max(0.0, float(owner_bucket.get("person1", 0.0))),
        withdrawn * split["person1"],
    )
    person2_withdrawn = max(0.0, withdrawn - person1_withdrawn)
    person2_withdrawn = min(
        max(0.0, float(owner_bucket.get("person2", 0.0))),
        person2_withdrawn,
    )
    person1_withdrawn = max(0.0, withdrawn - person2_withdrawn)

    owner_bucket["person1"] = max(0.0, float(owner_bucket.get("person1", 0.0)) - person1_withdrawn)
    owner_bucket["person2"] = max(0.0, float(owner_bucket.get("person2", 0.0)) - person2_withdrawn)
    return {"person1": person1_withdrawn, "person2": person2_withdrawn}


def _apply_owner_bucket_addition(
    owner_balances: dict[str, dict[str, float]],
    *,
    bucket: str,
    amount: float,
    fallback_shares: dict[str, float],
) -> dict[str, float]:
    if bucket not in {"trad_ira", "roth"}:
        return {"person1": 0.0, "person2": 0.0}
    added = max(0.0, float(amount))
    if added <= 0:
        return {"person1": 0.0, "person2": 0.0}

    split = _owner_split_for_bucket(owner_balances[bucket], fallback_shares)
    person1_added = added * split["person1"]
    person2_added = max(0.0, added - person1_added)
    owner_balances[bucket]["person1"] = float(owner_balances[bucket].get("person1", 0.0)) + person1_added
    owner_balances[bucket]["person2"] = float(owner_balances[bucket].get("person2", 0.0)) + person2_added
    return {"person1": person1_added, "person2": person2_added}


def _sync_retirement_bucket_totals(
    portfolio: dict[str, float],
    owner_balances: dict[str, dict[str, float]],
) -> None:
    portfolio["trad_ira"] = float(owner_balances["trad_ira"].get("person1", 0.0)) + float(
        owner_balances["trad_ira"].get("person2", 0.0)
    )
    portfolio["roth"] = float(owner_balances["roth"].get("person1", 0.0)) + float(
        owner_balances["roth"].get("person2", 0.0)
    )


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


def _person_event_initial(config: dict, person_key: str) -> str:
    """Return a display initial for synthesized person events."""
    person = config.get(person_key, {}) if isinstance(config.get(person_key), dict) else {}
    name = str(person.get("name", "")).strip()
    if name:
        for ch in name:
            if ch.isalpha():
                return ch.upper()
    return person_key[:1].upper()


def _person_end_of_plan_year(config: dict, person_key: str) -> int | None:
    """Return synced EndOfPlan year for a person from the current runtime config."""
    for event in config.get("events", []):
        if event.get("type") != "EndOfPlan":
            continue
        if str(event.get("person", "")).lower() != person_key:
            continue
        try:
            return int(event["year"])
        except (TypeError, ValueError, KeyError):
            return None
    return None


def _person_event_is_posthumous(event: dict | None, *, death_year: int | None) -> bool:
    """Return whether a person-scoped event falls strictly after EndOfPlan year."""
    if event is None or death_year is None:
        return False
    try:
        event_year = int(event["year"])
    except (TypeError, ValueError, KeyError):
        return False
    return event_year > death_year


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
    for person_key in ("person1", "person2"):
        handled_person_keys.add(person_key)
        person = config.get(person_key)
        death_year = _person_end_of_plan_year(config, person_key)
        if not isinstance(person, dict):
            if (
                person_key in legacy_retire_by_person
                and not _person_event_is_posthumous(
                    legacy_retire_by_person[person_key],
                    death_year=death_year,
                )
            ):
                resolved_events.append(dict(legacy_retire_by_person[person_key]))
            continue

        synthesized = _synthesize_retire_event(
            person_key=person_key,
            person=person,
            person_initial=_person_event_initial(config, person_key),
            legacy_event=legacy_retire_by_person.get(person_key),
            death_year=death_year,
        )
        if synthesized is not None:
            resolved_events.append(synthesized)
            continue

        # Fallback compatibility path: keep a legacy Retire event when
        # person-level fields are incomplete and synthesis is not possible.
        if (
            person_key in legacy_retire_by_person
            and not _person_event_is_posthumous(
                legacy_retire_by_person[person_key],
                death_year=death_year,
            )
        ):
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
    person_initial: str,
    legacy_event: dict | None,
    death_year: int | None,
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
        "label": f"Retirement ({person_initial})",
        "person": person_key,
        "year": retirement_year,
    }

    if _person_event_is_posthumous(event, death_year=death_year):
        return None

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
    for person_key in ("person1", "person2"):
        handled_person_keys.add(person_key)
        person = config.get(person_key)
        death_year = _person_end_of_plan_year(config, person_key)
        if not isinstance(person, dict):
            if (
                person_key in legacy_ss_by_person
                and not _person_event_is_posthumous(
                    legacy_ss_by_person[person_key],
                    death_year=death_year,
                )
            ):
                resolved_events.append(dict(legacy_ss_by_person[person_key]))
            continue

        synthesized = _synthesize_social_security_event(
            person_key=person_key,
            person=person,
            person_initial=_person_event_initial(config, person_key),
            legacy_event=legacy_ss_by_person.get(person_key),
            death_year=death_year,
        )
        if synthesized is not None:
            resolved_events.append(synthesized)
            continue

        # Fallback compatibility path: keep a legacy SocialSecurity event when
        # person-level fields are incomplete and synthesis is not possible.
        if (
            person_key in legacy_ss_by_person
            and not _person_event_is_posthumous(
                legacy_ss_by_person[person_key],
                death_year=death_year,
            )
        ):
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
    person_initial: str,
    legacy_event: dict | None,
    death_year: int | None,
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
        "label": f"SS Begins ({person_initial})",
        "person": person_key,
        "year": start_year,
        "monthly_benefit": monthly_benefit,
    }

    if _person_event_is_posthumous(event, death_year=death_year):
        return None

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


def normalize_expense_funding(event: dict | None) -> str | None:
    """Return normalized special funding behavior for Expense events."""
    funding = str((event or {}).get("funding", "")).strip().lower()
    return "cash_reserve_first" if funding == "cash_reserve_first" else None


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


def _buy_home_property_name(event: dict) -> str:
    """Return the tracked property name created by a BuyHome event."""
    property_name = event.get("property") or event.get("account") or event.get("label")
    if not property_name:
        raise ValueError(
            f"BuyHome event '{event.get('label', '?')}' must define property/account or label"
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
        "accumulation_surplus_order": _normalize_surplus_order(
            section.get("accumulation_surplus_order", DEFAULT_SURPLUS_ORDER)
        ),
        "retirement_surplus_order": _normalize_surplus_order(
            section.get("retirement_surplus_order", DEFAULT_SURPLUS_ORDER)
        ),
        "survivor_surplus_order": _normalize_surplus_order(
            section.get("survivor_surplus_order", DEFAULT_SURPLUS_ORDER)
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


def _spending_shift_phase(event: dict) -> str:
    """Return normalized SpendingShift phase target."""
    phase = str(event.get("phase", "retirement_and_survivor")).strip().lower()
    if phase in {"retirement", "survivor", "retirement_and_survivor"}:
        return phase
    return "retirement_and_survivor"


def _spending_shift_mode(event: dict) -> str:
    """Return normalized SpendingShift mode."""
    return str(event.get("mode", "replace")).strip().lower()


def _event_active_for_year(event: dict, year: int) -> bool:
    """Return whether an event with year/end_year is active in a given year."""
    start = int(event.get("year", year))
    end_raw = event.get("end_year")
    if end_raw is None:
        return year >= start
    end = int(end_raw)
    return start <= year <= end


def resolve_spending_shift_for_year(
    *,
    base_retirement_spend: float,
    base_survivor_spend: float,
    events: list[dict],
    year: int,
    in_survivor_phase: bool,
) -> tuple[float, float]:
    """Apply active SpendingShift events for the current year.

    MVP semantics:
    - mode=replace only
    - shifts retirement and/or survivor baseline spending by phase
    - latest matching active event in config order wins
    """
    retirement_spend = float(base_retirement_spend)
    survivor_spend = float(base_survivor_spend)

    for event in events:
        if event.get("type") != "SpendingShift":
            continue
        if not _event_active_for_year(event, year):
            continue

        phase = _spending_shift_phase(event)
        if in_survivor_phase:
            if phase not in {"survivor", "retirement_and_survivor"}:
                continue
        else:
            if phase not in {"retirement", "retirement_and_survivor"}:
                continue

        mode = _spending_shift_mode(event)
        if mode != "replace":
            raise ValueError(
                f"SpendingShift event '{event.get('label', '?')}' has unsupported mode '{mode}'. Supported: replace"
            )

        if phase in {"retirement", "retirement_and_survivor"} and "retirement_annual" in event:
            retirement_spend = float(event["retirement_annual"])

        if phase in {"survivor", "retirement_and_survivor"}:
            if "survivor_annual" in event:
                survivor_spend = float(event["survivor_annual"])
            elif "survivor_percent_of_retirement" in event:
                survivor_spend = retirement_spend * float(event["survivor_percent_of_retirement"])

    return retirement_spend, survivor_spend


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


def _normalize_401k_contribution_split(raw_split: object) -> dict[str, float] | None:
    """Return normalized trad/Roth 401(k) split weights when configured."""
    if not isinstance(raw_split, dict):
        return None

    weights = {}
    total = 0.0
    for bucket in ("trad_ira", "roth"):
        try:
            weight = max(0.0, float(raw_split.get(bucket, 0.0)))
        except (TypeError, ValueError):
            weight = 0.0
        weights[bucket] = weight
        total += weight

    if total <= 0.0:
        return None
    return {bucket: weight / total for bucket, weight in weights.items()}


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
    - 401(k) -> trad_ira unless annual_401k_contribution_split is configured
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
    split_401k = _normalize_401k_contribution_split(
        person.get("annual_401k_contribution_split")
    )

    breakdown = {"trad_ira": 0.0, "roth": 0.0}
    annual_401k = max(0.0, annual_401k)
    if split_401k is not None:
        for bucket, ratio in split_401k.items():
            breakdown[bucket] += annual_401k * ratio
    else:
        breakdown[bucket_401k] += annual_401k
    breakdown[bucket_ira] += max(0.0, annual_ira)
    return breakdown


def get_phase_withdrawal_settings(
    policy: dict[str, object],
    *,
    both_retired: bool,
    one_deceased: bool,
) -> tuple[float, list[str], list[str]]:
    """Return active cash target, withdrawal order, and surplus order for phase."""
    if one_deceased:
        phase = "survivor"
    elif both_retired:
        phase = "retirement"
    else:
        phase = "accumulation"

    return (
        float(policy.get(f"{phase}_cash_target", 0.0)),
        list(policy.get(f"{phase}_withdrawal_order", DEFAULT_WITHDRAWAL_ORDER)),
        list(policy.get(f"{phase}_surplus_order", DEFAULT_SURPLUS_ORDER)),
    )


def resolve_rmd_settings(config: dict) -> dict[str, object]:
    """Return normalized RMD settings from config.taxes.rmd."""
    taxes = config.get("taxes", {}) if isinstance(config, dict) else {}
    section = taxes.get("rmd", {}) if isinstance(taxes, dict) else {}

    start_age = 73
    try:
        start_age = int(section.get("start_age", 73))
    except (TypeError, ValueError):
        start_age = 73

    factors = dict(UNIFORM_LIFETIME_FACTORS)
    raw_factors = section.get("factors", {})
    if isinstance(raw_factors, dict):
        for raw_age, raw_factor in raw_factors.items():
            try:
                age = int(raw_age)
                factor = float(raw_factor)
            except (TypeError, ValueError):
                continue
            if age > 0 and factor > 0:
                factors[age] = factor

    return {
        "enabled": _as_bool(section.get("enabled"), default=False),
        "start_age": max(1, start_age),
        "factors": factors,
    }


def _birth_year(person: dict) -> int | None:
    """Return birth year from DOB string (YYYY-MM-DD), else None."""
    dob = person.get("dob")
    if not dob:
        return None
    try:
        return int(str(dob).split("-", 1)[0])
    except (TypeError, ValueError):
        return None


def _person_age_in_year(person: dict, year: int) -> int | None:
    """Return a person's age during the target year, else None."""
    birth_year = _birth_year(person)
    if birth_year is None:
        return None
    try:
        return int(year) - birth_year
    except (TypeError, ValueError):
        return None


def _death_year(events: list[dict], person_key: str) -> int | None:
    """Return the person's modeled death year from EndOfPlan events, if any."""
    death_years: list[int] = []
    for event in events:
        if event.get("type") != "EndOfPlan" or str(event.get("person")) != person_key:
            continue
        try:
            death_years.append(int(event["year"]))
        except (TypeError, ValueError, KeyError):
            continue
    return min(death_years) if death_years else None


def _is_deceased_in_year(*, events: list[dict], person_key: str, year: int) -> bool:
    """Return whether the person should be treated as deceased for the model year."""
    death_year = _death_year(events, person_key)
    return death_year is not None and int(year) > death_year


def _social_security_event_for_person(events: list[dict], person_key: str) -> dict | None:
    """Return the first SocialSecurity event for a person, if present."""
    for event in events:
        if event.get("type") == "SocialSecurity" and str(event.get("person")) == person_key:
            return event
    return None


def _survivor_social_security_start_age(person: dict) -> int:
    """Return the survivor-benefit eligibility age for the person."""
    raw_age = person.get("survivor_ss_start_age", 60)
    try:
        return max(0, int(raw_age))
    except (TypeError, ValueError):
        return 60


def _planned_social_security_monthly_benefit(
    *,
    person: dict,
    person_key: str,
    events: list[dict],
) -> float:
    """Return the person's configured or synthesized Social Security monthly benefit."""
    event = _social_security_event_for_person(events, person_key)
    if event is not None:
        try:
            return max(0.0, float(event.get("monthly_benefit", 0.0)))
        except (TypeError, ValueError):
            return 0.0

    monthly_benefit = _resolve_social_security_monthly_benefit(
        person,
        ss_start_age=person.get("ss_start_age"),
    )
    try:
        return max(0.0, float(monthly_benefit or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _planned_social_security_taxable_fraction(
    *,
    person_key: str,
    events: list[dict],
) -> float:
    """Return taxable fraction for the person's configured Social Security benefit."""
    event = _social_security_event_for_person(events, person_key)
    if event is None:
        return 1.0
    return _event_taxable_fraction(event, default=1.0)


def _uniform_lifetime_factor(age: int, factors: dict[int, float]) -> float | None:
    """Return uniform-lifetime divisor for age, clamped to max known age."""
    if not factors:
        return None
    if age in factors:
        return float(factors[age])
    max_age = max(factors)
    if age > max_age:
        return float(factors[max_age])
    return None


def _normalized_household_rmd_shares(
    *,
    person1: dict,
    person2: dict,
    person1_deceased: bool,
    person2_deceased: bool,
) -> dict[str, float]:
    """Return normalized trad-IRA ownership shares for household RMD allocation."""
    if person1_deceased and person2_deceased:
        return {"person1": 0.0, "person2": 0.0}
    if person1_deceased:
        return {"person1": 0.0, "person2": 1.0}
    if person2_deceased:
        return {"person1": 1.0, "person2": 0.0}

    raw_1 = person1.get("rmd_trad_ira_share")
    raw_2 = person2.get("rmd_trad_ira_share")
    try:
        share_1 = max(0.0, float(raw_1)) if raw_1 is not None else 0.0
    except (TypeError, ValueError):
        share_1 = 0.0
    try:
        share_2 = max(0.0, float(raw_2)) if raw_2 is not None else 0.0
    except (TypeError, ValueError):
        share_2 = 0.0

    total = share_1 + share_2
    if total > 0:
        return {
            "person1": share_1 / total,
            "person2": share_2 / total,
        }

    return {"person1": 0.5, "person2": 0.5}


def calculate_household_rmd_required(
    *,
    year: int,
    trad_ira_balance: float,
    person1: dict,
    person2: dict,
    person1_deceased: bool,
    person2_deceased: bool,
    rmd_settings: dict[str, object],
) -> float:
    """Return required household RMD amount for the year.

    Uses per-person ages + ownership shares against household trad_ira balance.
    """
    if not rmd_settings.get("enabled"):
        return 0.0

    trad_ira_balance = max(0.0, float(trad_ira_balance))
    if trad_ira_balance <= 0:
        return 0.0

    factors = dict(rmd_settings.get("factors", {}))
    start_age = int(rmd_settings.get("start_age", 73))
    shares = _normalized_household_rmd_shares(
        person1=person1,
        person2=person2,
        person1_deceased=person1_deceased,
        person2_deceased=person2_deceased,
    )

    total_required = 0.0
    for person_key, person, deceased in (
        ("person1", person1, person1_deceased),
        ("person2", person2, person2_deceased),
    ):
        if deceased:
            continue
        birth_year = _birth_year(person)
        if birth_year is None:
            continue
        age = int(year) - int(birth_year)
        if age < start_age:
            continue
        factor = _uniform_lifetime_factor(age, factors)
        if not factor or factor <= 0:
            continue
        owned_balance = trad_ira_balance * float(shares.get(person_key, 0.0))
        total_required += owned_balance / factor

    return max(0.0, total_required)


def _apply_survivor_social_security(
    *,
    year: int,
    events: list[dict],
    person1: dict,
    person2: dict,
    person1_deceased: bool,
    person2_deceased: bool,
    person1_parts: dict[str, float],
    person2_parts: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    """Adjust income parts for widow/er survivor Social Security rules."""
    if person1_deceased == person2_deceased:
        return person1_parts, person2_parts

    if person1_deceased:
        survivor_key = "person2"
        deceased_key = "person1"
        survivor = person2
        deceased = person1
        survivor_parts = person2_parts.copy()
        other_parts = person1_parts
    else:
        survivor_key = "person1"
        deceased_key = "person2"
        survivor = person1
        deceased = person2
        survivor_parts = person1_parts.copy()
        other_parts = person2_parts

    survivor_age = _person_age_in_year(survivor, year)
    if survivor_age is None:
        return person1_parts, person2_parts
    if survivor_age < _survivor_social_security_start_age(survivor):
        return person1_parts, person2_parts

    death_year = _death_year(events, deceased_key)
    if death_year is None or int(year) <= death_year:
        return person1_parts, person2_parts

    deceased_monthly = _planned_social_security_monthly_benefit(
        person=deceased,
        person_key=deceased_key,
        events=events,
    )
    if deceased_monthly <= 0:
        return person1_parts, person2_parts

    deceased_annual = deceased_monthly * 12.0
    deceased_taxable = deceased_annual * _planned_social_security_taxable_fraction(
        person_key=deceased_key,
        events=events,
    )

    if deceased_annual > survivor_parts["ss_income"]:
        survivor_parts["ss_income"] = deceased_annual
        survivor_parts["ss_taxable_income"] = deceased_taxable
        survivor_parts["cash_income"] = (
            survivor_parts["earned_income"] + survivor_parts["ss_income"]
        )

    if survivor_key == "person2":
        return other_parts, survivor_parts
    return survivor_parts, other_parts


def _apply_forced_rmd_withdrawal(
    portfolio: dict[str, float],
    *,
    required_amount: float,
    assumptions: dict,
) -> tuple[float, float, float]:
    """Apply a forced traditional-account withdrawal to satisfy RMD.

    Returns: (withdrawn_amount, taxable_income_from_withdrawal, shortfall)
    """
    required_amount = max(0.0, float(required_amount))
    available = max(0.0, float(portfolio.get("trad_ira", 0.0)))
    withdrawn = min(required_amount, available)
    if withdrawn > 0:
        portfolio["trad_ira"] = available - withdrawn
        portfolio["cash"] = float(portfolio.get("cash", 0.0)) + withdrawn
    taxable_income = withdrawn * _withdrawal_taxable_fraction("trad_ira", assumptions)
    shortfall = max(0.0, required_amount - withdrawn)
    return withdrawn, taxable_income, shortfall


def _normalize_simulation_settings(config: dict) -> dict[str, object]:
    sim = dict(config.get("simulation", {}))
    mode = str(sim.get("mode", "deterministic")).strip().lower() or "deterministic"
    if mode not in {"deterministic", "monte_carlo"}:
        mode = "deterministic"

    try:
        num_runs = max(1, int(sim.get("num_runs", 250)))
    except (TypeError, ValueError):
        num_runs = 250

    seed = sim.get("seed")
    try:
        seed = int(seed) if seed not in (None, "") else None
    except (TypeError, ValueError):
        seed = None

    try:
        return_volatility = max(0.0, float(sim.get("portfolio_return_volatility", 0.15)))
    except (TypeError, ValueError):
        return_volatility = 0.15

    return {
        "mode": mode,
        "num_runs": num_runs,
        "seed": seed,
        "portfolio_return_volatility": return_volatility,
    }


def _sample_monte_carlo_return_overrides(
    *,
    start_year: int,
    end_year: int,
    mean_return: float,
    volatility: float,
    rng: random.Random,
) -> dict[int, float]:
    overrides: dict[int, float] = {}
    for year in range(start_year, end_year + 1):
        sampled = rng.gauss(mean_return, volatility)
        overrides[year] = max(-0.99, sampled)
    return overrides


def _build_primary_path_from_runs(run_frames: list[pd.DataFrame]) -> pd.DataFrame:
    primary = run_frames[0].copy(deep=True)
    numeric_columns = [
        column for column in primary.columns
        if pd.api.types.is_numeric_dtype(primary[column]) and column != "year"
    ]
    for column in numeric_columns:
        joined = pd.concat(
            [frame[column].reset_index(drop=True) for frame in run_frames],
            axis=1,
        )
        primary[column] = joined.median(axis=1)

    if "year" in primary.columns:
        primary["year"] = run_frames[0]["year"].astype(int)
    return primary


def _build_band_frame(
    run_frames: list[pd.DataFrame],
    *,
    value_columns: tuple[str, ...] = ("total_net_worth", "net_worth"),
    percentiles: tuple[int, ...] = (10, 25, 50, 75, 90),
) -> pd.DataFrame:
    band_df = pd.DataFrame({"year": run_frames[0]["year"].astype(int).tolist()})
    for column in value_columns:
        if column not in run_frames[0].columns:
            continue
        joined = pd.concat(
            [frame[column].reset_index(drop=True) for frame in run_frames],
            axis=1,
        )
        for percentile in percentiles:
            band_df[f"{column}_p{percentile}"] = joined.quantile(
                percentile / 100.0,
                axis=1,
                interpolation="linear",
            )
    return band_df


def _first_depletion_year(df: pd.DataFrame) -> int | None:
    depleted = df[df["net_worth"] < 0]
    if depleted.empty:
        return None
    return int(depleted.iloc[0]["year"])


def _first_retirement_year(config: dict) -> int | None:
    retirement_years: list[int] = []
    for event in config.get("events", []):
        if event.get("type") != "Retire" or not event.get("enabled", False):
            continue
        try:
            retirement_years.append(int(event["year"]))
        except (TypeError, ValueError, KeyError):
            continue
    return min(retirement_years) if retirement_years else None


def _projection_summary(
    *,
    config: dict,
    simulation_settings: dict[str, object],
    primary_df: pd.DataFrame,
    run_frames: list[pd.DataFrame],
    band_df: pd.DataFrame | None,
) -> dict[str, object]:
    retirement_year = _first_retirement_year(config)
    summary: dict[str, object] = {
        "schema_version": PROJECTION_RESULT_SCHEMA_VERSION,
        "mode": simulation_settings["mode"],
        "run_count": len(run_frames),
        "display_path_kind": "deterministic" if len(run_frames) == 1 else "median",
        "start_year": int(primary_df["year"].min()) if not primary_df.empty else None,
        "end_year": int(primary_df["year"].max()) if not primary_df.empty else None,
        "retirement_year": retirement_year,
    }

    if primary_df.empty:
        return summary

    last_row = primary_df.iloc[-1]
    summary["terminal_total_net_worth"] = float(last_row["total_net_worth"])
    summary["terminal_investable_net_worth"] = float(last_row["net_worth"])

    if len(run_frames) == 1:
        return summary

    terminal_values = sorted(float(frame.iloc[-1]["total_net_worth"]) for frame in run_frames)
    depletion_years = [year for year in (_first_depletion_year(frame) for frame in run_frames) if year is not None]
    success_count = sum(1 for frame in run_frames if _first_depletion_year(frame) is None)
    summary["success_rate"] = success_count / len(run_frames)
    summary["failure_rate"] = 1.0 - summary["success_rate"]
    summary["terminal_total_net_worth_p10"] = float(pd.Series(terminal_values).quantile(0.10))
    summary["terminal_total_net_worth_p50"] = float(pd.Series(terminal_values).quantile(0.50))
    summary["terminal_total_net_worth_p90"] = float(pd.Series(terminal_values).quantile(0.90))
    summary["depletion_run_count"] = len(depletion_years)
    if depletion_years:
        depletion_series = pd.Series(sorted(depletion_years))
        summary["first_depletion_year_p10"] = int(round(float(depletion_series.quantile(0.10))))
        summary["first_depletion_year_p50"] = int(round(float(depletion_series.quantile(0.50))))
        summary["first_depletion_year_p90"] = int(round(float(depletion_series.quantile(0.90))))
    else:
        summary["first_depletion_year_p10"] = None
        summary["first_depletion_year_p50"] = None
        summary["first_depletion_year_p90"] = None

    if retirement_year is not None and band_df is not None:
        match = band_df[band_df["year"] == retirement_year]
        if not match.empty:
            row = match.iloc[0]
            for percentile in (10, 50, 90):
                key = f"total_net_worth_p{percentile}"
                if key in row:
                    summary[f"retirement_total_net_worth_p{percentile}"] = float(row[key])

    return summary


def run_projection_result(
    balances: dict[str, float],
    home_value: float = 0.0,
    liability_balances: dict[str, float] | None = None,
    property_values: dict[str, float] | None = None,
    retirement_owner_balances: dict[str, dict[str, float]] | None = None,
    config: dict | None = None,
) -> ProjectionResult:
    config = resolve_runtime_config(config or load_config())
    simulation_settings = _normalize_simulation_settings(config)
    if simulation_settings["mode"] != "monte_carlo":
        yearly_df = _run_projection_yearly(
            balances,
            home_value=home_value,
            liability_balances=liability_balances,
            property_values=property_values,
            retirement_owner_balances=retirement_owner_balances,
            config=config,
        )
        summary = _projection_summary(
            config=config,
            simulation_settings=simulation_settings,
            primary_df=yearly_df,
            run_frames=[yearly_df],
            band_df=None,
        )
        return ProjectionResult(
            mode="deterministic",
            yearly_df=yearly_df,
            summary=summary,
            simulation=simulation_settings,
            band_df=None,
            run_count=1,
            display_path_kind="deterministic",
        )

    sim = config["simulation"]
    assumptions = config["assumptions"]
    mean_return = (
        assumptions["stock_return"] * assumptions["equity_allocation"] +
        assumptions["bond_return"] * (1 - assumptions["equity_allocation"])
    )
    rng = random.Random(simulation_settings["seed"])
    run_frames: list[pd.DataFrame] = []
    for _ in range(int(simulation_settings["num_runs"])):
        overrides = _sample_monte_carlo_return_overrides(
            start_year=int(sim["start_year"]),
            end_year=int(sim["end_year"]),
            mean_return=float(mean_return),
            volatility=float(simulation_settings["portfolio_return_volatility"]),
            rng=rng,
        )
        run_frames.append(
            _run_projection_yearly(
                balances,
                home_value=home_value,
                liability_balances=liability_balances,
                property_values=property_values,
                retirement_owner_balances=retirement_owner_balances,
                config=config,
                annual_return_overrides=overrides,
            )
        )

    primary_df = _build_primary_path_from_runs(run_frames)
    band_df = _build_band_frame(run_frames)
    summary = _projection_summary(
        config=config,
        simulation_settings=simulation_settings,
        primary_df=primary_df,
        run_frames=run_frames,
        band_df=band_df,
    )
    return ProjectionResult(
        mode="monte_carlo",
        yearly_df=primary_df,
        summary=summary,
        simulation=simulation_settings,
        band_df=band_df,
        run_count=len(run_frames),
        display_path_kind="median",
    )


def run_projection(
    balances: dict[str, float],
    home_value: float = 0.0,
    liability_balances: dict[str, float] | None = None,
    property_values: dict[str, float] | None = None,
    retirement_owner_balances: dict[str, dict[str, float]] | None = None,
    config: dict | None = None,
) -> pd.DataFrame:
    return run_projection_result(
        balances,
        home_value=home_value,
        liability_balances=liability_balances,
        property_values=property_values,
        retirement_owner_balances=retirement_owner_balances,
        config=config,
    ).yearly_df


def _run_projection_yearly(
    balances: dict[str, float],
    home_value: float = 0.0,
    liability_balances: dict[str, float] | None = None,
    property_values: dict[str, float] | None = None,
    retirement_owner_balances: dict[str, dict[str, float]] | None = None,
    config: dict | None = None,
    annual_return_overrides: dict[int, float] | None = None,
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

    person1 = config["person1"]
    person2 = config["person2"]
    spending = config["spending"]
    liability_configs = config.get("liabilities", [])
    rmd_settings = resolve_rmd_settings(config)
    retirement_owner_balances, retirement_owner_defaults = _initial_retirement_owner_state(
        portfolio=portfolio,
        person1=person1,
        person2=person2,
        seeded_owner_balances=retirement_owner_balances,
    )

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
        person1_deceased = _is_deceased_in_year(events=events, person_key="person1", year=year)
        person2_deceased = _is_deceased_in_year(events=events, person_key="person2", year=year)

        # ── Apply events for this year ─────────────────────────────────────────
        active_labels = []
        event_cash_flow = 0.0
        cash_preserve_flow = 0.0
        pending_reinvestments: list[tuple[str, float]] = []
        taxable_event_income = 0.0
        reserve_access_expense_total = 0.0
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
                    if (
                        event["amount"] < 0
                        and normalize_expense_funding(event) == "cash_reserve_first"
                    ):
                        reserve_access_expense_total += abs(float(event["amount"]))
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
                    try:
                        purchase_price = float(event.get("price", 0.0))
                    except (TypeError, ValueError):
                        purchase_price = 0.0
                    if purchase_price > 0.0:
                        property_name = _buy_home_property_name(event)
                        property_state[property_name] = purchase_price
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

            elif etype == "SpendingShift":
                if event["year"] == year and should_show_chart_label(event):
                    icon = EVENT_ICONS["SpendingShift"]
                    active_labels.append(f"{icon} {event['label']}")

        mortgage_balance = sum(
            s["balance"] for s in lib_state if s["type"] == "mortgage"
        )

        # ── Income for this year ───────────────────────────────────────────────
        include_taxable_wages = resolve_wage_tax_treatment(config) == "taxable_wages"
        person1_parts = _person_income_components(
            person1,
            year,
            events,
            person_key="person1",
            assumptions=assumptions,
            simulation_start_year=start_year,
            deceased=person1_deceased,
            include_taxable_wages=include_taxable_wages,
        )
        person2_parts = _person_income_components(
            person2,
            year,
            events,
            person_key="person2",
            assumptions=assumptions,
            simulation_start_year=start_year,
            deceased=person2_deceased,
            include_taxable_wages=include_taxable_wages,
        )

        person1_parts, person2_parts = _apply_survivor_social_security(
            year=year,
            events=events,
            person1=person1,
            person2=person2,
            person1_deceased=person1_deceased,
            person2_deceased=person2_deceased,
            person1_parts=person1_parts,
            person2_parts=person2_parts,
        )

        person1_income = person1_parts["cash_income"]
        person2_income    = person2_parts["cash_income"]
        total_income = person1_income + person2_income

        # ── Contributions (pre-retirement only) ────────────────────────────────
        person1_retired = year >= person1["retirement_year"]
        person2_retired = year >= person2["retirement_year"]

        person1_contrib_buckets = (
            {"trad_ira": 0.0, "roth": 0.0}
            if person1_retired
            else _person_retirement_contribution_breakdown(
                person1,
                year=year,
                simulation_start_year=start_year,
                assumptions=assumptions,
            )
        )
        person2_contrib_buckets = (
            {"trad_ira": 0.0, "roth": 0.0}
            if person2_retired
            else _person_retirement_contribution_breakdown(
                person2,
                year=year,
                simulation_start_year=start_year,
                assumptions=assumptions,
            )
        )

        prefunded_contrib_by_person = _empty_retirement_owner_breakdown()
        cash_required_contrib_by_person = _empty_retirement_owner_breakdown()

        person1_prefunded = _take_home_is_net_of_retirement_contributions(person1)
        person2_prefunded = _take_home_is_net_of_retirement_contributions(person2)

        for bucket in ("trad_ira", "roth"):
            if person1_prefunded:
                prefunded_contrib_by_person["person1"][bucket] += person1_contrib_buckets[bucket]
            else:
                cash_required_contrib_by_person["person1"][bucket] += person1_contrib_buckets[bucket]

            if person2_prefunded:
                prefunded_contrib_by_person["person2"][bucket] += person2_contrib_buckets[bucket]
            else:
                cash_required_contrib_by_person["person2"][bucket] += person2_contrib_buckets[bucket]

        prefunded_contrib_buckets = {
            bucket: prefunded_contrib_by_person["person1"][bucket] + prefunded_contrib_by_person["person2"][bucket]
            for bucket in ("trad_ira", "roth")
        }
        cash_required_contrib_buckets = {
            bucket: cash_required_contrib_by_person["person1"][bucket] + cash_required_contrib_by_person["person2"][bucket]
            for bucket in ("trad_ira", "roth")
        }

        total_cash_required_contrib = sum(cash_required_contrib_buckets.values())

        # ── Net cash flow for the year ─────────────────────────────────────────
        target_spend = float(spending.get("retirement_annual", 0.0))
        survivor_spend = resolve_survivor_spending(spending)
        both_retired = person1_retired and person2_retired
        one_deceased = person1_deceased or person2_deceased

        if one_deceased or both_retired:
            target_spend, survivor_spend = resolve_spending_shift_for_year(
                base_retirement_spend=target_spend,
                base_survivor_spend=survivor_spend,
                events=events,
                year=year,
                in_survivor_phase=one_deceased,
            )
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

        rmd_required = calculate_household_rmd_required(
            year=year,
            trad_ira_balance=float(portfolio.get("trad_ira", 0.0)),
            person1=person1,
            person2=person2,
            person1_deceased=person1_deceased,
            person2_deceased=person2_deceased,
            rmd_settings=rmd_settings,
        )

        cash_target, withdrawal_order, surplus_order = get_phase_withdrawal_settings(
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
            person1_parts["taxable_wage_income"] + person2_parts["taxable_wage_income"]
        )
        base_non_ss_taxable_income = taxable_event_income + taxable_wage_income
        total_social_security_income = (
            person1_parts["ss_income"] + person2_parts["ss_income"]
        )
        legacy_ss_taxable_income = (
            person1_parts["ss_taxable_income"] + person2_parts["ss_taxable_income"]
        )

        # Cash flow before any taxes or withdrawal sequencing
        base_net_flow = total_income - annual_spend + event_cash_flow + freed_this_year

        # ── Grow portfolio ─────────────────────────────────────────────────────
        invested_growth_rate = (
            assumptions["stock_return"] * assumptions["equity_allocation"] +
            assumptions["bond_return"] * (1 - assumptions["equity_allocation"])
        )
        if annual_return_overrides and year in annual_return_overrides:
            invested_growth_rate = float(annual_return_overrides[year])
        cash_growth_rate = resolve_cash_growth_rate(assumptions)
        current_total = sum(portfolio.values())
        if current_total > 0:
            grown_portfolio = {
                cat: balance * (
                    1 + (cash_growth_rate if cat == "cash" else invested_growth_rate)
                )
                for cat, balance in portfolio.items()
            }
            grown_retirement_owner_balances = {
                bucket: {
                    person_key: float(retirement_owner_balances[bucket][person_key]) * (1 + invested_growth_rate)
                    for person_key in RETIREMENT_OWNER_KEYS
                }
                for bucket in ("trad_ira", "roth")
            }
        else:
            grown_portfolio = portfolio.copy()
            grown_retirement_owner_balances = _clone_retirement_owner_balances(retirement_owner_balances)

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
        withdrawal_breakdown_by_person = _empty_retirement_owner_breakdown()
        contribution_breakdown = prefunded_contrib_buckets.copy()
        contribution_breakdown_by_person = deepcopy(prefunded_contrib_by_person)
        working_portfolio = grown_portfolio.copy()
        working_retirement_owner_balances = _clone_retirement_owner_balances(grown_retirement_owner_balances)
        rmd_withdrawn = 0.0
        rmd_shortfall = 0.0

        # Iterate because taxable withdrawals themselves increase taxes.
        for _ in range(12):
            working_portfolio = grown_portfolio.copy()
            working_retirement_owner_balances = _clone_retirement_owner_balances(grown_retirement_owner_balances)
            contribution_breakdown = prefunded_contrib_buckets.copy()
            contribution_breakdown_by_person = deepcopy(prefunded_contrib_by_person)
            for person_key in RETIREMENT_OWNER_KEYS:
                for bucket in ("trad_ira", "roth"):
                    amount = prefunded_contrib_by_person[person_key][bucket]
                    if amount <= 0:
                        continue
                    working_portfolio[bucket] = working_portfolio.get(bucket, 0.0) + amount
                    working_retirement_owner_balances[bucket][person_key] = (
                        working_retirement_owner_balances[bucket].get(person_key, 0.0) + amount
                    )

            forced_rmd_withdrawn, forced_rmd_taxable_income, forced_rmd_shortfall = _apply_forced_rmd_withdrawal(
                working_portfolio,
                required_amount=rmd_required,
                assumptions=assumptions,
            )
            rmd_withdrawn = forced_rmd_withdrawn
            rmd_shortfall = forced_rmd_shortfall

            post_tax_flow = base_net_flow + forced_rmd_withdrawn - annual_taxes

            withdrawal_breakdown = _empty_withdrawal_breakdown()
            withdrawal_breakdown_by_person = _empty_retirement_owner_breakdown()
            withdrawal_breakdown["trad_ira"] += forced_rmd_withdrawn
            forced_rmd_owner_withdrawals = _apply_owner_bucket_withdrawal(
                working_retirement_owner_balances,
                bucket="trad_ira",
                amount=forced_rmd_withdrawn,
                fallback_shares=retirement_owner_defaults["trad_ira"],
            )
            for person_key in RETIREMENT_OWNER_KEYS:
                withdrawal_breakdown_by_person[person_key]["trad_ira"] += forced_rmd_owner_withdrawals[person_key]
            withdrawal_taxable_income = forced_rmd_taxable_income

            if post_tax_flow >= 0:
                preserved_cash = min(post_tax_flow, cash_preserve_flow)
                if preserved_cash > 0:
                    working_portfolio["cash"] = working_portfolio.get("cash", 0.0) + preserved_cash

                available_for_contrib = max(0.0, post_tax_flow - preserved_cash)
                contribution_target_by_bucket: dict[str, float] = {}
                for bucket in ("trad_ira", "roth"):
                    target_amount = min(cash_required_contrib_buckets[bucket], available_for_contrib)
                    contribution_target_by_bucket[bucket] = target_amount
                    available_for_contrib -= target_amount

                for bucket in ("trad_ira", "roth"):
                    bucket_total = contribution_target_by_bucket[bucket]
                    if bucket_total <= 0:
                        continue
                    requested_by_person = {
                        person_key: cash_required_contrib_by_person[person_key][bucket]
                        for person_key in RETIREMENT_OWNER_KEYS
                    }
                    requested_total = sum(requested_by_person.values())
                    if requested_total <= 0:
                        continue
                    for person_key in RETIREMENT_OWNER_KEYS:
                        person_amount = bucket_total * (requested_by_person[person_key] / requested_total)
                        if person_amount <= 0:
                            continue
                        working_portfolio[bucket] = working_portfolio.get(bucket, 0.0) + person_amount
                        working_retirement_owner_balances[bucket][person_key] = (
                            working_retirement_owner_balances[bucket].get(person_key, 0.0) + person_amount
                        )
                        contribution_breakdown[bucket] += person_amount
                        contribution_breakdown_by_person[person_key][bucket] += person_amount

                trad_before_surplus = working_portfolio.get("trad_ira", 0.0)
                roth_before_surplus = working_portfolio.get("roth", 0.0)
                _apply_surplus_with_reserve_target(
                    working_portfolio,
                    surplus=available_for_contrib,
                    cash_target=cash_target,
                    excluded_categories={"trad_ira"} if forced_rmd_withdrawn > 0 else None,
                    surplus_order=surplus_order,
                    withdrawal_order=withdrawal_order,
                    protected_cash=preserved_cash,
                )
                trad_surplus_delta = working_portfolio.get("trad_ira", 0.0) - trad_before_surplus
                roth_surplus_delta = working_portfolio.get("roth", 0.0) - roth_before_surplus
                if trad_surplus_delta > 0:
                    _apply_owner_bucket_addition(
                        working_retirement_owner_balances,
                        bucket="trad_ira",
                        amount=trad_surplus_delta,
                        fallback_shares=retirement_owner_defaults["trad_ira"],
                    )
                if roth_surplus_delta > 0:
                    _apply_owner_bucket_addition(
                        working_retirement_owner_balances,
                        bucket="roth",
                        amount=roth_surplus_delta,
                        fallback_shares=retirement_owner_defaults["roth"],
                    )
            else:
                reserve_first_draw = min(
                    max(0.0, reserve_access_expense_total),
                    max(0.0, -post_tax_flow),
                    max(0.0, working_portfolio.get("cash", 0.0)),
                )
                if reserve_first_draw > 0:
                    working_portfolio["cash"] = max(
                        0.0,
                        working_portfolio.get("cash", 0.0) - reserve_first_draw,
                    )
                    withdrawal_breakdown["cash"] += reserve_first_draw
                    post_tax_flow += reserve_first_draw

                extra_taxable_income, unmet_deficit, extra_withdrawal_breakdown = _cover_deficit_with_policy(
                    working_portfolio,
                    deficit=-post_tax_flow,
                    assumptions=assumptions,
                    withdrawal_order=withdrawal_order,
                    cash_target=cash_target,
                )
                withdrawal_taxable_income += extra_taxable_income
                for bucket in WITHDRAWAL_BUCKETS:
                    withdrawal_breakdown[bucket] += extra_withdrawal_breakdown[bucket]
                if extra_withdrawal_breakdown.get("trad_ira", 0.0) > 0:
                    owner_trad_withdrawals = _apply_owner_bucket_withdrawal(
                        working_retirement_owner_balances,
                        bucket="trad_ira",
                        amount=extra_withdrawal_breakdown["trad_ira"],
                        fallback_shares=retirement_owner_defaults["trad_ira"],
                    )
                    for person_key in RETIREMENT_OWNER_KEYS:
                        withdrawal_breakdown_by_person[person_key]["trad_ira"] += owner_trad_withdrawals[person_key]
                if extra_withdrawal_breakdown.get("roth", 0.0) > 0:
                    owner_roth_withdrawals = _apply_owner_bucket_withdrawal(
                        working_retirement_owner_balances,
                        bucket="roth",
                        amount=extra_withdrawal_breakdown["roth"],
                        fallback_shares=retirement_owner_defaults["roth"],
                    )
                    for person_key in RETIREMENT_OWNER_KEYS:
                        withdrawal_breakdown_by_person[person_key]["roth"] += owner_roth_withdrawals[person_key]
                if unmet_deficit > 0:
                    for cat in working_portfolio:
                        working_portfolio[cat] = 0.0
                    working_portfolio["cash"] = -unmet_deficit
                    working_retirement_owner_balances["trad_ira"]["person1"] = 0.0
                    working_retirement_owner_balances["trad_ira"]["person2"] = 0.0
                    working_retirement_owner_balances["roth"]["person1"] = 0.0
                    working_retirement_owner_balances["roth"]["person2"] = 0.0
                else:
                    _apply_surplus_with_reserve_target(
                        working_portfolio,
                        surplus=0.0,
                        cash_target=cash_target,
                        excluded_categories={"trad_ira"} if forced_rmd_withdrawn > 0 else None,
                        surplus_order=surplus_order,
                        withdrawal_order=withdrawal_order,
                        protected_cash=0.0,
                    )

            _sync_retirement_bucket_totals(working_portfolio, working_retirement_owner_balances)

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
        retirement_owner_balances = _clone_retirement_owner_balances(working_retirement_owner_balances)
        for reinvest_target, requested_amount in pending_reinvestments:
            move_amount = min(
                max(0.0, portfolio.get("cash", 0.0)),
                max(0.0, requested_amount),
            )
            if move_amount <= 0:
                continue
            portfolio["cash"] = portfolio.get("cash", 0.0) - move_amount
            portfolio[reinvest_target] = portfolio.get(reinvest_target, 0.0) + move_amount
            if reinvest_target in {"trad_ira", "roth"}:
                _apply_owner_bucket_addition(
                    retirement_owner_balances,
                    bucket=reinvest_target,
                    amount=move_amount,
                    fallback_shares=retirement_owner_defaults[reinvest_target],
                )
        _sync_retirement_bucket_totals(portfolio, retirement_owner_balances)
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
            "person1_income": person1_income,
            "person2_income":    person2_income,
            "taxable_income": taxable_income,
            "taxable_wage_income": taxable_wage_income,
            "annual_taxes":   annual_taxes,
            "annual_federal_taxes": federal_taxes,
            "annual_state_taxes": state_taxes,
            "annual_spend":   annual_spend,
            "freed_payments": freed_this_year,
            "net_flow":       net_flow,
            "rmd_required":   rmd_required,
            "rmd_withdrawn":  rmd_withdrawn,
            "rmd_shortfall":  rmd_shortfall,
            "withdrawal_cash": withdrawal_breakdown["cash"],
            "withdrawal_taxable": withdrawal_breakdown["taxable"],
            "withdrawal_trad_ira": withdrawal_breakdown["trad_ira"],
            "withdrawal_roth": withdrawal_breakdown["roth"],
            "withdrawal_trad_ira_person1": withdrawal_breakdown_by_person["person1"]["trad_ira"],
            "withdrawal_trad_ira_person2": withdrawal_breakdown_by_person["person2"]["trad_ira"],
            "withdrawal_roth_person1": withdrawal_breakdown_by_person["person1"]["roth"],
            "withdrawal_roth_person2": withdrawal_breakdown_by_person["person2"]["roth"],
            "contribution_trad_ira": contribution_breakdown["trad_ira"],
            "contribution_roth": contribution_breakdown["roth"],
            "contribution_trad_ira_person1": contribution_breakdown_by_person["person1"]["trad_ira"],
            "contribution_trad_ira_person2": contribution_breakdown_by_person["person2"]["trad_ira"],
            "contribution_roth_person1": contribution_breakdown_by_person["person1"]["roth"],
            "contribution_roth_person2": contribution_breakdown_by_person["person2"]["roth"],
            "contribution_total": contribution_breakdown["trad_ira"] + contribution_breakdown["roth"],
            "survivor":       one_deceased,
            "event_items":    event_items,
            "events_active":  ", ".join(all_labels) if all_labels else "",
            "taxable":        portfolio["taxable"],
            "trad_ira":       portfolio["trad_ira"],
            "trad_ira_person1": retirement_owner_balances["trad_ira"]["person1"],
            "trad_ira_person2": retirement_owner_balances["trad_ira"]["person2"],
            "roth":           portfolio["roth"],
            "roth_person1": retirement_owner_balances["roth"]["person1"],
            "roth_person2": retirement_owner_balances["roth"]["person2"],
            "cash":           portfolio["cash"],
        })

    return pd.DataFrame(rows)


def _person_income_components(
    person: dict,
    year: int,
    events: list,
    *,
    person_key: str,
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


def _normalize_surplus_order(order) -> list[str]:
    """Return validated surplus routing preferences across investable non-cash buckets."""
    valid_steps = {"taxable", "trad_ira", "roth"}
    if not isinstance(order, list):
        return list(DEFAULT_SURPLUS_ORDER)

    normalized: list[str] = []
    for step in order:
        step = str(step).strip()
        if step in valid_steps and step not in normalized:
            normalized.append(step)

    return normalized or list(DEFAULT_SURPLUS_ORDER)


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


def _surplus_fallback_bucket(
    *,
    portfolio: dict[str, float],
    surplus_order: list[str] | None,
    withdrawal_order: list[str] | None,
    excluded_categories: set[str],
) -> str | None:
    """Return fallback non-cash bucket for surplus when proportional routing has no receivers.

    Priority:
    1) configured surplus_order (phase-specific)
    2) reverse withdrawal order (legacy mirror behavior)
    3) static default order
    """
    if surplus_order:
        for step in surplus_order:
            if step not in {"taxable", "trad_ira", "roth"}:
                continue
            if step in excluded_categories:
                continue
            if step in portfolio:
                return step

    if withdrawal_order:
        for step in reversed(withdrawal_order):
            if step not in WITHDRAWAL_BUCKETS:
                continue
            if step == "cash":
                continue
            if step in excluded_categories:
                continue
            if step in portfolio:
                return step

    for bucket in DEFAULT_SURPLUS_ORDER:
        if bucket in portfolio and bucket not in excluded_categories:
            return bucket

    return None


def _apply_surplus_with_reserve_target(
    portfolio: dict[str, float],
    surplus: float,
    cash_target: float,
    excluded_categories: set[str] | None = None,
    surplus_order: list[str] | None = None,
    withdrawal_order: list[str] | None = None,
    protected_cash: float = 0.0,
) -> None:
    """Refill cash floor first, then invest surplus and sweep excess cash above that floor.

    `protected_cash` reserves an additional amount above `cash_target` that should
    remain in cash for this year (e.g., explicitly-preserved SellHome proceeds).
    """
    if excluded_categories is None:
        excluded_categories = set()

    cash_floor = max(0.0, cash_target) + max(0.0, protected_cash)

    remaining = max(0.0, float(surplus))
    current_cash = portfolio.get("cash", 0.0)

    refill = min(max(0.0, cash_floor - current_cash), remaining)
    current_cash += refill
    portfolio["cash"] = current_cash
    remaining -= refill

    excess_cash = max(0.0, current_cash - cash_floor)
    if excess_cash > 0:
        portfolio["cash"] = current_cash - excess_cash
        remaining += excess_cash

    if remaining <= 0:
        return

    positive_non_cash_total = sum(
        balance
        for category, balance in portfolio.items()
        if category != "cash" and category not in excluded_categories and balance > 0
    )
    if positive_non_cash_total <= 0:
        fallback_bucket = _surplus_fallback_bucket(
            portfolio=portfolio,
            surplus_order=surplus_order,
            withdrawal_order=withdrawal_order,
            excluded_categories=excluded_categories,
        )
        if fallback_bucket is not None:
            portfolio[fallback_bucket] = portfolio.get(fallback_bucket, 0.0) + remaining
        else:
            portfolio["cash"] = portfolio.get("cash", 0.0) + remaining
        return

    for category, balance in list(portfolio.items()):
        if category != "cash" and category not in excluded_categories and balance > 0:
            portfolio[category] += remaining * (balance / positive_non_cash_total)
