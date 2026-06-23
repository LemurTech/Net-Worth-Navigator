"""tax_model.py — Typed yearly tax contracts and calculators for NWN."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.oregon_tax_2025 import OREGON_2025_TAX_TABLE, OREGON_2025_RATE_CHARTS

DEFAULT_TAX_FILING_STATUS = {
    "pre_retirement": "married_joint",
    "retirement": "married_joint",
    "survivor": "single",
}

VALID_FILING_STATUSES = {"single", "married_joint", "head_of_household"}


@dataclass
class FederalTaxSystem:
    """Normalized federal tax configuration for a single projection year."""

    mode: str
    phase: str
    filing_status: str | None = None
    standard_deduction: float = 0.0
    brackets: list[dict] = field(default_factory=list)
    social_security: dict[str, object] = field(default_factory=dict)
    rate: float = 0.0


@dataclass
class StateTaxSystem:
    """Normalized state tax configuration for a single projection year."""

    enabled: bool = False
    name: str = ""
    filing_status: str = "married_joint"
    standard_deduction: float = 0.0
    tax_social_security: bool = False


@dataclass
class YearlyTaxInputs:
    """Structured taxable-flow inputs for one modeled year."""

    non_ss_taxable_income: float
    social_security_income: float
    withdrawal_taxable_income: float
    legacy_ss_taxable_income: float
    federal_system: FederalTaxSystem
    state_system: StateTaxSystem

    @property
    def other_taxable_income(self) -> float:
        return max(0.0, float(self.non_ss_taxable_income) + float(self.withdrawal_taxable_income))


@dataclass
class YearlyTaxOutputs:
    """Structured tax outputs for one modeled year."""

    total_taxes: float
    taxable_income: float
    federal_taxes: float
    state_taxes: float
    taxable_social_security_income: float
    state_taxable_income: float
    non_ss_taxable_income: float
    withdrawal_taxable_income: float
    other_taxable_income: float
    federal_standard_deduction: float
    federal_taxable_after_deduction: float
    federal_effective_rate: float
    state_standard_deduction: float
    state_taxable_before_deduction: float
    state_effective_rate: float
    social_security_taxable_fraction: float
    social_security_provisional_income: float
    state_social_security_taxed: bool


def _tax_phase(*, both_retired: bool, one_deceased: bool) -> str:
    if one_deceased:
        return "survivor"
    if both_retired:
        return "retirement"
    return "pre_retirement"


def resolve_tax_system(
    config: dict,
    *,
    assumptions: dict,
    both_retired: bool,
    one_deceased: bool,
) -> FederalTaxSystem:
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
        return FederalTaxSystem(
            mode="brackets",
            phase=phase,
            filing_status=filing_status,
            standard_deduction=standard_deduction,
            brackets=brackets,
            social_security=dict(taxes.get("social_security", {})),
        )

    return FederalTaxSystem(
        mode="effective_rate",
        phase=phase,
        rate=float(
            assumptions["effective_tax_rate_post_retirement"]
            if both_retired else assumptions["effective_tax_rate_pre_retirement"]
        ),
    )


def resolve_state_tax_system(
    config: dict,
    *,
    filing_status: str,
) -> StateTaxSystem:
    """Return the active state tax system, if any."""
    state = config.get("taxes", {}).get("state", {})
    if not state.get("enabled"):
        return StateTaxSystem()

    state_name = str(state.get("name", "")).strip().lower()
    filing_status = filing_status if filing_status in VALID_FILING_STATUSES else "married_joint"

    if state_name == "oregon":
        return StateTaxSystem(
            enabled=True,
            name="oregon",
            filing_status=filing_status,
            standard_deduction=float(state.get("standard_deduction", {}).get(filing_status, 0.0)),
            tax_social_security=bool(state.get("tax_social_security", False)),
        )

    return StateTaxSystem()


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


def _estimate_federal_taxes(inputs: YearlyTaxInputs) -> tuple[float, float, float, float, float, float, float]:
    """Return federal tax details for the year."""
    other_taxable_income = inputs.other_taxable_income
    taxable_ss_income = 0.0
    provisional_income = 0.0
    standard_deduction = 0.0
    if inputs.federal_system.mode == "brackets":
        standard_deduction = float(inputs.federal_system.standard_deduction)
        provisional_income = max(0.0, other_taxable_income) + (max(0.0, inputs.social_security_income) * 0.5)
        taxable_ss_income = calculate_social_security_taxable_income(
            social_security_income=max(0.0, inputs.social_security_income),
            other_taxable_income=other_taxable_income,
            filing_status=str(inputs.federal_system.filing_status or "married_joint"),
            social_security_config=dict(inputs.federal_system.social_security),
        )
        taxable_income = other_taxable_income + taxable_ss_income
        federal_taxes = calculate_progressive_tax(
            taxable_income=taxable_income,
            standard_deduction=standard_deduction,
            brackets=list(inputs.federal_system.brackets),
        )
    else:
        taxable_income = max(0.0, other_taxable_income + inputs.legacy_ss_taxable_income)
        federal_taxes = taxable_income * float(inputs.federal_system.rate)
        taxable_ss_income = inputs.legacy_ss_taxable_income
        standard_deduction = 0.0
        provisional_income = max(0.0, other_taxable_income) + (max(0.0, inputs.social_security_income) * 0.5)
    taxable_after_deduction = max(0.0, taxable_income - standard_deduction)
    effective_rate = 0.0 if taxable_income <= 0 else federal_taxes / taxable_income
    ss_fraction = 0.0 if inputs.social_security_income <= 0 else taxable_ss_income / max(0.0, inputs.social_security_income)
    return (
        federal_taxes,
        taxable_income,
        taxable_ss_income,
        standard_deduction,
        taxable_after_deduction,
        effective_rate,
        provisional_income,
    )


def estimate_annual_taxes(*, inputs: YearlyTaxInputs) -> YearlyTaxOutputs:
    """Estimate annual federal+state taxes and return a structured yearly result."""
    (
        federal_taxes,
        taxable_income,
        taxable_ss_income,
        federal_standard_deduction,
        federal_taxable_after_deduction,
        federal_effective_rate,
        social_security_provisional_income,
    ) = _estimate_federal_taxes(inputs)
    state_taxes, state_taxable_income, state_taxable_before_deduction = estimate_state_taxes(
        non_ss_taxable_income=inputs.other_taxable_income,
        social_security_taxable_income=taxable_ss_income,
        state_tax_system=inputs.state_system,
    )
    total_taxes = federal_taxes + state_taxes
    state_effective_rate = 0.0 if state_taxable_before_deduction <= 0 else state_taxes / state_taxable_before_deduction
    social_security_taxable_fraction = (
        0.0 if inputs.social_security_income <= 0 else taxable_ss_income / max(0.0, inputs.social_security_income)
    )
    return YearlyTaxOutputs(
        total_taxes=total_taxes,
        taxable_income=taxable_income,
        federal_taxes=federal_taxes,
        state_taxes=state_taxes,
        taxable_social_security_income=taxable_ss_income,
        state_taxable_income=state_taxable_income,
        non_ss_taxable_income=max(0.0, float(inputs.non_ss_taxable_income)),
        withdrawal_taxable_income=max(0.0, float(inputs.withdrawal_taxable_income)),
        other_taxable_income=inputs.other_taxable_income,
        federal_standard_deduction=federal_standard_deduction,
        federal_taxable_after_deduction=federal_taxable_after_deduction,
        federal_effective_rate=federal_effective_rate,
        state_standard_deduction=float(inputs.state_system.standard_deduction),
        state_taxable_before_deduction=state_taxable_before_deduction,
        state_effective_rate=state_effective_rate,
        social_security_taxable_fraction=social_security_taxable_fraction,
        social_security_provisional_income=social_security_provisional_income,
        state_social_security_taxed=bool(inputs.state_system.tax_social_security),
    )


def estimate_state_taxes(
    *,
    non_ss_taxable_income: float,
    social_security_taxable_income: float,
    state_tax_system: StateTaxSystem,
) -> tuple[float, float, float]:
    """Estimate state tax from modeled taxable inflows."""
    if not state_tax_system.enabled:
        return 0.0, 0.0, 0.0
    if state_tax_system.name != "oregon":
        return 0.0, 0.0, 0.0

    filing_status = str(state_tax_system.filing_status or "married_joint")
    state_taxable_before_deduction = max(0.0, non_ss_taxable_income)
    if state_tax_system.tax_social_security:
        state_taxable_before_deduction += max(0.0, social_security_taxable_income)
    state_taxable_income = max(0.0, state_taxable_before_deduction - float(state_tax_system.standard_deduction))
    return (
        calculate_oregon_state_tax(
            taxable_income=state_taxable_income,
            filing_status=filing_status,
        ),
        state_taxable_income,
        state_taxable_before_deduction,
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
