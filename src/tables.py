"""
tables.py — Build HTML tables and summary panels for Net Worth Navigator.

Each function returns a self-contained HTML string ready to embed
in the tabbed page wrapper produced by charts.py.
"""
from html import escape

import pandas as pd


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _display_years(df: pd.DataFrame) -> list[int]:
    """Return all years in the projection for yearly-tick column display."""
    return df["year"].tolist()


def _event_item_parts(item) -> tuple[str, float, str | None, str | None]:
    """Normalize legacy tuple items and current dict items."""
    if isinstance(item, dict):
        return (
            str(item.get("label", "")),
            float(item.get("amount", 0.0)),
            item.get("event_type"),
            item.get("expense_kind"),
        )
    label, amount = item
    return str(label), float(amount), None, None


def _fmt(value: float) -> str:

    if pd.isna(value) or value == 0:
        return "<td class='zero'>—</td>"
    color = "neg" if value < 0 else ""
    return f"<td class='{color}'>${value:>12,.0f}</td>"


def _fmt_currency(value) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.0f}"


def _fmt_percent(value) -> str:
    try:
        pct = float(value) * 100.0
    except (TypeError, ValueError):
        return "—"
    text = f"{pct:.1f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _fmt_401k_split(value) -> str:
    if not isinstance(value, dict):
        return "—"
    try:
        trad = max(0.0, float(value.get("trad_ira", 0.0)))
        roth = max(0.0, float(value.get("roth", 0.0)))
    except (TypeError, ValueError):
        return "—"
    total = trad + roth
    if total <= 0:
        return "—"
    trad_pct = (trad / total) * 100.0
    roth_pct = (roth / total) * 100.0
    trad_text = f"{trad_pct:.1f}".rstrip("0").rstrip(".")
    roth_text = f"{roth_pct:.1f}".rstrip("0").rstrip(".")
    return f"{trad_text}% trad / {roth_text}% Roth"


def _resolve_survivor_annual(spending: dict) -> float:
    retirement_annual = float(spending.get("retirement_annual", 0.0))
    survivor_ratio = spending.get("survivor_percent_of_retirement")
    if survivor_ratio is not None:
        try:
            return retirement_annual * float(survivor_ratio)
        except (TypeError, ValueError):
            pass
    try:
        return float(spending.get("survivor_annual", round(retirement_annual * 0.70)))
    except (TypeError, ValueError):
        return 0.0


def _birth_year(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        return int(str(dob).split("-", 1)[0])
    except (TypeError, ValueError):
        return None


def _age_from_year(dob: str | None, target_year) -> int | None:
    birth_year = _birth_year(dob)
    if birth_year is None:
        return None
    try:
        return int(target_year) - birth_year
    except (TypeError, ValueError):
        return None


def _fmt_age_year(age, year) -> str:
    if age is None and year in (None, ""):
        return "—"
    if age is None:
        return str(year)
    if year in (None, ""):
        return str(age)
    return f"{age} (→ {year})"


def _person_keys(config: dict) -> list[str]:
    preferred = [
        key for key in ("person1", "person2")
        if isinstance(config.get(key), dict)
        and any(field in config[key] for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    extras = [
        key for key, value in config.items()
        if key not in preferred
        and isinstance(value, dict)
        and any(field in value for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    return preferred + extras


def _person_display_name(config: dict | None, person_key: str) -> str:
    if isinstance(config, dict):
        person = config.get(person_key, {})
        if isinstance(person, dict):
            name = str(person.get("name", "")).strip()
            if name:
                return name
    if person_key.startswith("person") and person_key[6:].isdigit():
        return f"Person {person_key[6:]}"
    return person_key.replace("_", " ").title()


def _kv_table(rows: list[tuple]) -> str:
    rendered_rows = []
    for row in rows:
        if len(row) == 2:
            label, value = row
            row_class = ""
        else:
            label, value, row_class = row
        cls_attr = f" class='{escape(str(row_class))}'" if row_class else ""
        rendered_rows.append(f"<tr{cls_attr}><th>{escape(str(label))}</th><td>{value}</td></tr>")
    body = "".join(rendered_rows)
    return f"<table class='assumptions-table assumptions-kv'><tbody>{body}</tbody></table>"


def build_assumptions_summary(
    config: dict,
    scenario=None,
    baseline_config: dict | None = None,
) -> str:
    """Return a formatted HTML summary of the current modeling assumptions."""
    baseline_assumptions = (
        baseline_config.get("assumptions", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("assumptions"), dict)
        else {}
    )
    baseline_spending = (
        baseline_config.get("spending", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("spending"), dict)
        else {}
    )
    baseline_withdrawal_policy = (
        baseline_config.get("withdrawal_policy", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("withdrawal_policy"), dict)
        else {}
    )

    changed_count = 0

    def _diff_row(label: str, value, baseline_value, formatter) -> tuple[str, str, str]:
        nonlocal changed_count
        changed = baseline_config is not None and value != baseline_value
        if changed:
            changed_count += 1
        return (label, formatter(value), "param-diff" if changed else "")

    people_rows = []
    for person_key in _person_keys(config):
        person = config.get(person_key, {})
        baseline_person = (
            baseline_config.get(person_key, {})
            if isinstance(baseline_config, dict) and isinstance(baseline_config.get(person_key), dict)
            else {}
        )

        name = person.get("name") or person_key.replace("_", " ").title()
        dob = person.get("dob") or "—"

        life_expectancy = person.get("life_expectancy")
        birth_year = _birth_year(person.get("dob"))
        end_year = None
        if birth_year is not None and life_expectancy not in (None, ""):
            try:
                end_year = birth_year + int(life_expectancy)
            except (TypeError, ValueError):
                end_year = None

        retirement_year = person.get("retirement_year")
        retirement_age = _age_from_year(person.get("dob"), retirement_year)

        ss_start_age = person.get("ss_start_age")
        ss_start_year = None
        if birth_year is not None and ss_start_age not in (None, ""):
            try:
                ss_start_year = birth_year + int(ss_start_age)
            except (TypeError, ValueError):
                ss_start_year = None

        row_changed = baseline_config is not None and (
            person.get("dob") != baseline_person.get("dob")
            or person.get("life_expectancy") != baseline_person.get("life_expectancy")
            or person.get("retirement_year") != baseline_person.get("retirement_year")
            or person.get("ss_start_age") != baseline_person.get("ss_start_age")
        )
        if row_changed:
            changed_count += 1
        row_cls = " class='param-diff'" if row_changed else ""

        people_rows.append(
            f"<tr{row_cls}>"
            f"<td>{escape(str(name))}</td>"
            f"<td>{escape(str(dob))}</td>"
            f"<td>{escape(_fmt_age_year(life_expectancy, end_year))}</td>"
            f"<td>{escape(_fmt_age_year(retirement_age, retirement_year))}</td>"
            f"<td>{escape(_fmt_age_year(ss_start_age, ss_start_year))}</td>"
            "</tr>"
        )

    people_body = "".join(people_rows) if people_rows else "<tr><td colspan='5'>No people configured.</td></tr>"
    people_html = (
        "<table class='assumptions-table assumptions-people'>"
        "<thead><tr>"
        "<th>Person</th><th>Birthdate</th><th>Projected lifespan</th>"
        "<th>Retirement age</th><th>Social Security start age</th>"
        "</tr></thead>"
        f"<tbody>{people_body}</tbody>"
        "</table>"
    )

    assumptions = config.get("assumptions", {})
    market_rows = [
        _diff_row("Stock return", assumptions.get("stock_return"), baseline_assumptions.get("stock_return"), _fmt_percent),
        _diff_row("Bond return", assumptions.get("bond_return"), baseline_assumptions.get("bond_return"), _fmt_percent),
        _diff_row("Inflation", assumptions.get("inflation"), baseline_assumptions.get("inflation"), _fmt_percent),
        _diff_row(
            "Real estate appreciation",
            assumptions.get("real_estate_appreciation"),
            baseline_assumptions.get("real_estate_appreciation"),
            _fmt_percent,
        ),
        _diff_row(
            "Equity allocation",
            assumptions.get("equity_allocation"),
            baseline_assumptions.get("equity_allocation"),
            _fmt_percent,
        ),
        _diff_row(
            "Real estate sale fee rate",
            assumptions.get("real_estate_sale_fee_rate"),
            baseline_assumptions.get("real_estate_sale_fee_rate"),
            _fmt_percent,
        ),
    ]

    spending = config.get("spending", {})
    spending_rows = [
        _diff_row(
            "Retirement annual",
            spending.get("retirement_annual"),
            baseline_spending.get("retirement_annual"),
            _fmt_currency,
        ),
        _diff_row(
            "Survivor % of retirement",
            spending.get("survivor_percent_of_retirement", 0.70),
            baseline_spending.get("survivor_percent_of_retirement", 0.70),
            _fmt_percent,
        ),
        _diff_row(
            "Survivor annual",
            _resolve_survivor_annual(spending),
            _resolve_survivor_annual(baseline_spending),
            _fmt_currency,
        ),
    ]

    withdrawal_policy = config.get("withdrawal_policy", {})
    withdrawal_rows = [
        _diff_row(
            "Accumulation cash target",
            withdrawal_policy.get("accumulation_cash_target"),
            baseline_withdrawal_policy.get("accumulation_cash_target"),
            _fmt_currency,
        ),
        _diff_row(
            "Retirement cash target",
            withdrawal_policy.get("retirement_cash_target"),
            baseline_withdrawal_policy.get("retirement_cash_target"),
            _fmt_currency,
        ),
        _diff_row(
            "Survivor cash target",
            withdrawal_policy.get("survivor_cash_target"),
            baseline_withdrawal_policy.get("survivor_cash_target"),
            _fmt_currency,
        ),
    ]

    baseline_note = (
        f" <strong>{changed_count}</strong> field(s) differ from baseline default scenario."
        if baseline_config is not None
        else ""
    )
    default_diff_checked = bool(
        baseline_config is not None
        and scenario is not None
        and not bool(getattr(scenario, "is_default", False))
    )
    checked_attr = " checked" if default_diff_checked else ""
    filter_toolbar = (
        "<div class='scenario-diff-toolbar'>"
        f"<label><input type='checkbox' id='assumptions-diff-only-toggle'{checked_attr} /> Show only differences</label>"
        "</div>"
        if baseline_config is not None
        else ""
    )

    return (
        "<div class='assumptions-wrap'>"
        "<div class='assumptions-note'>Current planning assumptions from the active scenario config."
        f"{baseline_note}</div>"
        f"{filter_toolbar}"
        "<div class='assumptions-grid'>"
        "<section class='assumption-card assumption-card-wide'>"
        "<h3>Persons</h3>"
        f"{people_html}"
        "</section>"
        "<section class='assumption-card'>"
        "<h3>Market assumptions</h3>"
        f"{_kv_table(market_rows)}"
        "</section>"
        "<section class='assumption-card'>"
        "<h3>Spending</h3>"
        "<p class='assumption-subtitle'>Annual values in today's dollars.</p>"
        f"{_kv_table(spending_rows)}"
        "</section>"
        "<section class='assumption-card'>"
        "<h3>Withdrawal policy</h3>"
        "<p class='assumption-subtitle'>Configured cash reserve targets by phase.</p>"
        f"{_kv_table(withdrawal_rows)}"
        "</section>"
        "</div>"
        "</div>"
    )


def _fmt_bool(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "—"


def _fmt_list(values) -> str:
    if not isinstance(values, list):
        return "—"
    return " → ".join(escape(str(v)) for v in values) if values else "(empty)"


def _owner_share_pair(person1_amount, person2_amount) -> tuple[str, str]:
    try:
        person1 = max(0.0, float(person1_amount))
        person2 = max(0.0, float(person2_amount))
    except (TypeError, ValueError):
        return ("—", "—")
    total = person1 + person2
    if total <= 0:
        return ("—", "—")
    return (f"{(person1 / total) * 100.0:.1f}%", f"{(person2 / total) * 100.0:.1f}%")


def _owner_share_snapshot_rows(config: dict, projection_df: pd.DataFrame | None) -> list[tuple[str, str, str]]:
    if projection_df is None or projection_df.empty:
        return []
    required_cols = {
        "year",
        "trad_ira_person1",
        "trad_ira_person2",
        "roth_person1",
        "roth_person2",
    }
    if not required_cols.issubset(set(projection_df.columns)):
        return []

    snapshot_years: list[tuple[str, int]] = []
    retirement_years: list[int] = []
    for person_key in _person_keys(config):
        year = config.get(person_key, {}).get("retirement_year")
        if year in (None, ""):
            continue
        try:
            retirement_years.append(int(year))
        except (TypeError, ValueError):
            continue
    if retirement_years:
        snapshot_years.append((f"Retirement year ({min(retirement_years)})", min(retirement_years)))

    try:
        end_year = int(projection_df["year"].max())
        snapshot_years.append((f"End year ({end_year})", end_year))
    except (TypeError, ValueError):
        pass

    seen_years: set[int] = set()
    rows: list[tuple[str, str, str]] = []
    for label_prefix, year in snapshot_years:
        if year in seen_years:
            continue
        seen_years.add(year)
        match = projection_df[projection_df["year"] == year]
        if match.empty:
            continue
        row = match.iloc[0]
        trad_p1 = row.get("trad_ira_person1", 0.0)
        trad_p2 = row.get("trad_ira_person2", 0.0)
        roth_p1 = row.get("roth_person1", 0.0)
        roth_p2 = row.get("roth_person2", 0.0)
        combined_p1, combined_p2 = _owner_share_pair((trad_p1 or 0.0) + (roth_p1 or 0.0), (trad_p2 or 0.0) + (roth_p2 or 0.0))
        trad_share_p1, trad_share_p2 = _owner_share_pair(trad_p1, trad_p2)
        roth_share_p1, roth_share_p2 = _owner_share_pair(roth_p1, roth_p2)
        rows.extend([
            (f"{label_prefix} — Combined retirement ownership", combined_p1, combined_p2),
            (f"{label_prefix} — Traditional IRA / 401k ownership", trad_share_p1, trad_share_p2),
            (f"{label_prefix} — Roth ownership", roth_share_p1, roth_share_p2),
        ])
    return rows


def _owner_share_snapshot_table(config: dict, projection_df: pd.DataFrame | None) -> str:
    rows = _owner_share_snapshot_rows(config, projection_df)
    if not rows:
        return ""

    person1_name = _person_display_name(config, "person1")
    person2_name = _person_display_name(config, "person2")
    body = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(person1_pct)}</td><td>{escape(person2_pct)}</td></tr>"
        for label, person1_pct, person2_pct in rows
    )
    return (
        "<table class='assumptions-table assumptions-people always-visible-table ownership-snapshot-table'>"
        "<thead><tr>"
        "<th>Snapshot</th>"
        f"<th>{escape(person1_name)}</th>"
        f"<th>{escape(person2_name)}</th>"
        "</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )


def _events_enabled_metrics(events) -> dict[str, int]:
    if not isinstance(events, list):
        return {"Enabled events": 0, "Recurring-enabled events": 0}

    enabled = [e for e in events if isinstance(e, dict) and bool(e.get("enabled", False))]
    by_type: dict[str, int] = {}
    recurring = 0
    for event in enabled:
        etype = str(event.get("type", "Unknown"))
        by_type[etype] = by_type.get(etype, 0) + 1
        if any(k in event for k in ("repeat_every_years", "repeat_until_year", "repeat_count")):
            recurring += 1

    metrics: dict[str, int] = {
        "Enabled events": len(enabled),
        "Recurring-enabled events": recurring,
    }
    for etype in sorted(by_type):
        metrics[etype] = by_type[etype]
    return metrics


def build_scenario_parameters_summary(
    config: dict,
    scenario=None,
    baseline_config: dict | None = None,
    projection_df: pd.DataFrame | None = None,
    projection_result=None,
) -> str:
    """Return a detailed scenario-parameter summary for audit/comparison."""
    scenario_cfg = config.get("scenario", {}) if isinstance(config.get("scenario"), dict) else {}
    simulation = config.get("simulation", {}) if isinstance(config.get("simulation"), dict) else {}
    taxes = config.get("taxes", {}) if isinstance(config.get("taxes"), dict) else {}
    rmd = taxes.get("rmd", {}) if isinstance(taxes.get("rmd"), dict) else {}
    wp = config.get("withdrawal_policy", {}) if isinstance(config.get("withdrawal_policy"), dict) else {}

    baseline_scenario_cfg = (
        baseline_config.get("scenario", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("scenario"), dict)
        else {}
    )
    baseline_simulation = (
        baseline_config.get("simulation", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("simulation"), dict)
        else {}
    )
    baseline_taxes = (
        baseline_config.get("taxes", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("taxes"), dict)
        else {}
    )
    baseline_rmd = baseline_taxes.get("rmd", {}) if isinstance(baseline_taxes.get("rmd"), dict) else {}
    baseline_wp = (
        baseline_config.get("withdrawal_policy", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("withdrawal_policy"), dict)
        else {}
    )

    changed_count = 0

    def _diff_row(label: str, value, baseline_value, formatter) -> tuple[str, str, str]:
        nonlocal changed_count
        changed = baseline_config is not None and value != baseline_value
        if changed:
            changed_count += 1
        return (label, formatter(value), "param-diff" if changed else "")

    def _fmt_text(value) -> str:
        if value in (None, ""):
            return "—"
        return escape(str(value))

    scenario_rows = [
        _diff_row("Scenario name", scenario_cfg.get("name"), baseline_scenario_cfg.get("name"), _fmt_text),
        _diff_row("Scenario slug", scenario_cfg.get("slug"), baseline_scenario_cfg.get("slug"), _fmt_text),
        _diff_row(
            "Scenario description",
            scenario_cfg.get("description"),
            baseline_scenario_cfg.get("description"),
            _fmt_text,
        ),
        _diff_row("Start year", simulation.get("start_year"), baseline_simulation.get("start_year"), _fmt_text),
        _diff_row("End year", simulation.get("end_year"), baseline_simulation.get("end_year"), _fmt_text),
        _diff_row("Simulation mode", simulation.get("mode", "deterministic"), baseline_simulation.get("mode", "deterministic"), _fmt_text),
        _diff_row("Simulation runs", simulation.get("num_runs", 250), baseline_simulation.get("num_runs", 250), _fmt_text),
        _diff_row("Simulation seed", simulation.get("seed"), baseline_simulation.get("seed"), _fmt_text),
        _diff_row(
            "Portfolio return volatility",
            simulation.get("portfolio_return_volatility", 0.15),
            baseline_simulation.get("portfolio_return_volatility", 0.15),
            _fmt_percent,
        ),
        _diff_row(
            "Historical returns path",
            simulation.get("historical_returns_path"),
            baseline_simulation.get("historical_returns_path"),
            _fmt_text,
        ),
    ]
    if scenario is not None:
        scenario_rows.extend([
            ("Config path", f"<code>{escape(str(getattr(scenario, 'config_path', '—')))}</code>", ""),
            ("Marked default", _fmt_bool(getattr(scenario, "is_default", None)), ""),
        ])

    tax_rows = [
        _diff_row("Tax model enabled", taxes.get("enabled"), baseline_taxes.get("enabled"), _fmt_bool),
        _diff_row("Tax table set", taxes.get("table_set"), baseline_taxes.get("table_set"), _fmt_text),
        _diff_row(
            "Wage tax treatment",
            taxes.get("wage_tax_treatment"),
            baseline_taxes.get("wage_tax_treatment"),
            _fmt_text,
        ),
        _diff_row(
            "Pre-retirement filing",
            taxes.get("pre_retirement_filing_status"),
            baseline_taxes.get("pre_retirement_filing_status"),
            _fmt_text,
        ),
        _diff_row(
            "Retirement filing",
            taxes.get("retirement_filing_status"),
            baseline_taxes.get("retirement_filing_status"),
            _fmt_text,
        ),
        _diff_row(
            "Survivor filing",
            taxes.get("survivor_filing_status"),
            baseline_taxes.get("survivor_filing_status"),
            _fmt_text,
        ),
        _diff_row("RMD enabled", rmd.get("enabled"), baseline_rmd.get("enabled"), _fmt_bool),
        _diff_row("RMD start age", rmd.get("start_age"), baseline_rmd.get("start_age"), _fmt_text),
    ]

    policy_rows = [
        _diff_row(
            "Accumulation cash target",
            wp.get("accumulation_cash_target"),
            baseline_wp.get("accumulation_cash_target"),
            _fmt_currency,
        ),
        _diff_row(
            "Retirement cash target",
            wp.get("retirement_cash_target"),
            baseline_wp.get("retirement_cash_target"),
            _fmt_currency,
        ),
        _diff_row(
            "Survivor cash target",
            wp.get("survivor_cash_target"),
            baseline_wp.get("survivor_cash_target"),
            _fmt_currency,
        ),
        _diff_row(
            "Accumulation withdrawal order",
            wp.get("accumulation_withdrawal_order"),
            baseline_wp.get("accumulation_withdrawal_order"),
            _fmt_list,
        ),
        _diff_row(
            "Retirement withdrawal order",
            wp.get("retirement_withdrawal_order"),
            baseline_wp.get("retirement_withdrawal_order"),
            _fmt_list,
        ),
        _diff_row(
            "Survivor withdrawal order",
            wp.get("survivor_withdrawal_order"),
            baseline_wp.get("survivor_withdrawal_order"),
            _fmt_list,
        ),
        _diff_row(
            "Accumulation surplus order",
            wp.get("accumulation_surplus_order"),
            baseline_wp.get("accumulation_surplus_order"),
            _fmt_list,
        ),
        _diff_row(
            "Retirement surplus order",
            wp.get("retirement_surplus_order"),
            baseline_wp.get("retirement_surplus_order"),
            _fmt_list,
        ),
        _diff_row(
            "Survivor surplus order",
            wp.get("survivor_surplus_order"),
            baseline_wp.get("survivor_surplus_order"),
            _fmt_list,
        ),
    ]

    person_cards = []
    for person_key in _person_keys(config):
        person = config.get(person_key, {})
        baseline_person = (
            baseline_config.get(person_key, {})
            if isinstance(baseline_config, dict) and isinstance(baseline_config.get(person_key), dict)
            else {}
        )
        name = person.get("name") or person_key.replace("_", " ").title()
        person_rows = [
            _diff_row("Take-home (annual)", person.get("annual_take_home"), baseline_person.get("annual_take_home"), _fmt_currency),
            _diff_row(
                "Take-home already net of retirement contributions",
                person.get("annual_take_home_is_net_of_retirement_contributions"),
                baseline_person.get("annual_take_home_is_net_of_retirement_contributions"),
                _fmt_bool,
            ),
            _diff_row(
                "Take-home real raise",
                person.get("annual_take_home_real_raise"),
                baseline_person.get("annual_take_home_real_raise"),
                _fmt_percent,
            ),
            _diff_row(
                "401k contribution (annual)",
                person.get("annual_401k_contribution"),
                baseline_person.get("annual_401k_contribution"),
                _fmt_currency,
            ),
            _diff_row(
                "401k extra increase",
                person.get("annual_401k_contribution_extra_increase"),
                baseline_person.get("annual_401k_contribution_extra_increase"),
                _fmt_percent,
            ),
            _diff_row(
                "401k contribution split",
                person.get("annual_401k_contribution_split"),
                baseline_person.get("annual_401k_contribution_split"),
                _fmt_401k_split,
            ),
            _diff_row(
                "IRA contribution (annual)",
                person.get("annual_ira_contribution"),
                baseline_person.get("annual_ira_contribution"),
                _fmt_currency,
            ),
            _diff_row(
                "Survivor SS start age",
                person.get("survivor_ss_start_age"),
                baseline_person.get("survivor_ss_start_age"),
                _fmt_text,
            ),
            _diff_row(
                "401k contribution bucket override",
                person.get("annual_401k_contribution_bucket"),
                baseline_person.get("annual_401k_contribution_bucket"),
                _fmt_text,
            ),
            _diff_row(
                "IRA contribution bucket override",
                person.get("annual_ira_contribution_bucket"),
                baseline_person.get("annual_ira_contribution_bucket"),
                _fmt_text,
            ),
            _diff_row(
                "RMD trad_ira share",
                person.get("rmd_trad_ira_share"),
                baseline_person.get("rmd_trad_ira_share"),
                _fmt_text,
            ),
        ]
        person_cards.append(
            "<section class='assumption-card'>"
            f"<h3>{escape(str(name))} parameters</h3>"
            f"{_kv_table(person_rows)}"
            "</section>"
        )

    event_metrics = _events_enabled_metrics(config.get("events", []))
    baseline_event_metrics = (
        _events_enabled_metrics(baseline_config.get("events", []))
        if isinstance(baseline_config, dict)
        else {}
    )
    event_rows = [
        _diff_row(label, value, baseline_event_metrics.get(label), lambda v: escape(str(v)))
        for label, value in event_metrics.items()
    ]
    ownership_snapshot_table = _owner_share_snapshot_table(config, projection_df)
    monte_carlo_cfg = config.get("monte_carlo", {}) if isinstance(config.get("monte_carlo"), dict) else {}
    success_cfg = monte_carlo_cfg.get("success", {}) if isinstance(monte_carlo_cfg.get("success"), dict) else {}
    baseline_monte_carlo_cfg = (
        baseline_config.get("monte_carlo", {})
        if isinstance(baseline_config, dict) and isinstance(baseline_config.get("monte_carlo"), dict)
        else {}
    )
    baseline_success_cfg = (
        baseline_monte_carlo_cfg.get("success", {})
        if isinstance(baseline_monte_carlo_cfg.get("success"), dict)
        else {}
    )
    success_rows = [
        _diff_row("Failure mode", success_cfg.get("failure_mode"), baseline_success_cfg.get("failure_mode"), _fmt_text),
        _diff_row(
            "Minimum spending funded ratio",
            success_cfg.get("minimum_spending_funded_ratio", 1.0),
            baseline_success_cfg.get("minimum_spending_funded_ratio", 1.0),
            _fmt_percent,
        ),
        _diff_row(
            "Allow home equity for spending",
            success_cfg.get("allow_home_equity_for_spending", False),
            baseline_success_cfg.get("allow_home_equity_for_spending", False),
            _fmt_bool,
        ),
        _diff_row(
            "Allow debt for spending",
            success_cfg.get("allow_debt_for_spending", False),
            baseline_success_cfg.get("allow_debt_for_spending", False),
            _fmt_bool,
        ),
        _diff_row(
            "Failure grace period (months)",
            success_cfg.get("failure_grace_period_months", 0),
            baseline_success_cfg.get("failure_grace_period_months", 0),
            _fmt_text,
        ),
    ]
    simulation_result_card = ""
    if projection_result is not None and getattr(projection_result, "mode", "deterministic") in {"monte_carlo", "historical"}:
        summary = getattr(projection_result, "summary", {}) or {}
        mode_label = "Monte Carlo" if getattr(projection_result, "mode", "deterministic") == "monte_carlo" else "Historical sequence"
        simulation_rows = [
            ("Display path", escape(str(summary.get("display_path_kind", "median")))),
            ("Run count", escape(str(summary.get("run_count", "—")))),
            ("Failure mode", escape(str(summary.get("failure_mode", "—")))),
            ("Success rate", _fmt_percent(summary.get("success_rate", 0.0))),
            ("Median end net worth", _fmt_currency(summary.get("terminal_total_net_worth_p50"))),
            ("P10 end net worth", _fmt_currency(summary.get("terminal_total_net_worth_p10"))),
            ("P90 end net worth", _fmt_currency(summary.get("terminal_total_net_worth_p90"))),
            ("Median first failure year", escape(str(summary.get("first_failure_year_p50", "No failure")))),
            ("Retirement P50 net worth", _fmt_currency(summary.get("retirement_total_net_worth_p50"))),
        ]
        simulation_result_card = (
            "<section class='assumption-card'>"
            "<h3>Simulation results</h3>"
            f"<p class='assumption-subtitle'>{escape(mode_label)} summary metrics from the current rendered run.</p>"
            f"{_kv_table(simulation_rows)}"
            "</section>"
        )

    tax_result_card = ""
    if projection_df is not None and not projection_df.empty and "annual_taxes" in projection_df.columns:
        peak_tax_row = projection_df.loc[projection_df["annual_taxes"].idxmax()]
        latest_tax_row = projection_df.iloc[-1]
        tax_rows = [
            ("Peak total modeled tax", _fmt_currency(peak_tax_row.get("annual_taxes"))),
            ("Peak tax year", escape(str(int(peak_tax_row.get("year", 0)))) if pd.notna(peak_tax_row.get("year")) else "—"),
            ("Peak federal tax", _fmt_currency(peak_tax_row.get("annual_federal_taxes"))),
            ("Peak state tax", _fmt_currency(peak_tax_row.get("annual_state_taxes"))),
            ("Latest tax phase", escape(str(latest_tax_row.get("tax_phase", "—")))),
            ("Latest filing status", escape(str(latest_tax_row.get("tax_filing_status", "—")))),
            ("Latest other taxable income", _fmt_currency(latest_tax_row.get("other_taxable_income"))),
            ("Latest taxable income", _fmt_currency(latest_tax_row.get("taxable_income"))),
            ("Latest federal deduction", _fmt_currency(latest_tax_row.get("federal_standard_deduction"))),
            ("Latest federal taxable after deduction", _fmt_currency(latest_tax_row.get("federal_taxable_after_deduction"))),
            ("Latest federal effective rate", _fmt_percent(latest_tax_row.get("federal_effective_rate"))),
            ("Latest taxable Social Security", _fmt_currency(latest_tax_row.get("taxable_social_security_income"))),
            ("Latest Social Security taxable fraction", _fmt_percent(latest_tax_row.get("social_security_taxable_fraction"))),
            ("Latest provisional income", _fmt_currency(latest_tax_row.get("social_security_provisional_income"))),
            ("Latest state deduction", _fmt_currency(latest_tax_row.get("state_standard_deduction"))),
            ("Latest state taxable before deduction", _fmt_currency(latest_tax_row.get("state_taxable_before_deduction"))),
            ("Latest state taxable income", _fmt_currency(latest_tax_row.get("state_taxable_income"))),
            ("Latest state effective rate", _fmt_percent(latest_tax_row.get("state_effective_rate"))),
        ]
        tax_result_card = (
            "<section class='assumption-card'>"
            "<h3>Tax output snapshot</h3>"
            "<p class='assumption-subtitle'>Modeled tax outputs from the current rendered path.</p>"
            f"{_kv_table(tax_rows)}"
            "</section>"
        )

    person_cards_html = "".join(person_cards)
    baseline_note = (
        f" <strong>{changed_count}</strong> field(s) differ from baseline default scenario."
        if baseline_config is not None
        else ""
    )
    default_diff_checked = bool(
        baseline_config is not None
        and scenario is not None
        and not bool(getattr(scenario, "is_default", False))
    )
    checked_attr = " checked" if default_diff_checked else ""
    filter_toolbar = (
        "<div class='scenario-diff-toolbar'>"
        f"<label><input type='checkbox' id='scenario-diff-only-toggle'{checked_attr} /> Show only differences</label>"
        "</div>"
        if baseline_config is not None
        else ""
    )
    ownership_card_html = (
        "<section class='assumption-card assumption-card-wide keep-visible-in-diff'>"
        "<h3>Retirement ownership snapshots</h3>"
        "<p class='assumption-subtitle'>Owner split at first retirement year and at end-of-plan.</p>"
        f"{ownership_snapshot_table}"
        "</section>"
        if ownership_snapshot_table
        else ""
    )

    return (
        "<div class='assumptions-wrap'>"
        "<div class='assumptions-note'>Detailed parameters that distinguish this scenario run."
        f"{baseline_note}</div>"
        f"{filter_toolbar}"
        "<div class='assumptions-grid'>"
        "<section class='assumption-card'>"
        "<h3>Scenario metadata</h3>"
        f"{_kv_table(scenario_rows)}"
        "</section>"
        "<section class='assumption-card'>"
        "<h3>Tax and RMD controls</h3>"
        f"{_kv_table(tax_rows)}"
        "</section>"
        "<section class='assumption-card assumption-card-wide'>"
        "<h3>Withdrawal policy (full)</h3>"
        f"{_kv_table(policy_rows)}"
        "</section>"
        f"{person_cards_html}"
        "<section class='assumption-card'>"
        "<h3>Enabled events summary</h3>"
        f"{_kv_table(event_rows)}"
        "</section>"
        "<section class='assumption-card'>"
        "<h3>Stochastic success rules</h3>"
        f"{_kv_table(success_rows)}"
        "</section>"
        f"{tax_result_card}"
        f"{simulation_result_card}"
        f"{ownership_card_html}"
        "</div>"
        "</div>"
    )


def _header_row(years: list[int]) -> str:
    cells = "".join(f"<th>{y}</th>" for y in years)
    return f"<tr><th class='rowlabel'>Account</th>{cells}</tr>"


def _data_row(label: str, values: list[float], indent: bool = False,
              bold: bool = False, separator: bool = False) -> str:
    cls_parts = []
    if indent:   cls_parts.append("indent")
    if bold:     cls_parts.append("total")
    if separator: cls_parts.append("sep")
    cls = " ".join(cls_parts)
    tag = "th" if bold else "td"
    cells = "".join(_fmt(v) for v in values)
    return f"<tr class='{cls}'><{tag} class='rowlabel'>{label}</{tag}>{cells}</tr>"


# ── Accounts table ─────────────────────────────────────────────────────────────

def build_accounts_table(df: pd.DataFrame, config: dict | None = None) -> str:
    """
    Net Worth table: assets at top, liabilities below, home equity and
    total net worth at the bottom.
    """
    years  = _display_years(df)
    subset = df[df["year"].isin(years)].set_index("year")

    def col(field: str) -> list[float]:
        return [subset.loc[y, field] if y in subset.index else 0.0 for y in years]

    rows = []
    person1_name = _person_display_name(config, "person1")
    person2_name = _person_display_name(config, "person2")
    rows.append("<tr class='section'><th colspan='100'>Assets</th></tr>")
    rows.append(_data_row("Traditional IRA / 401k", col("trad_ira"),  indent=True))
    if "trad_ira_person1" in subset.columns:
        rows.append(_data_row(f"Traditional IRA / 401k — {person1_name}", col("trad_ira_person1"), indent=True))
    if "trad_ira_person2" in subset.columns:
        rows.append(_data_row(f"Traditional IRA / 401k — {person2_name}", col("trad_ira_person2"), indent=True))
    rows.append(_data_row("Roth",                    col("roth"),      indent=True))
    if "roth_person1" in subset.columns:
        rows.append(_data_row(f"Roth — {person1_name}", col("roth_person1"), indent=True))
    if "roth_person2" in subset.columns:
        rows.append(_data_row(f"Roth — {person2_name}", col("roth_person2"), indent=True))
    rows.append(_data_row("Taxable",                 col("taxable"),   indent=True))
    rows.append(_data_row("Cash",                    col("cash"),      indent=True))
    rows.append(_data_row("Investable Portfolio",
                          [sum(subset.loc[y, c] for c in ["trad_ira","roth","taxable","cash"])
                           if y in subset.index else 0.0 for y in years],
                          bold=True))

    rows.append("<tr class='section'><th colspan='100'>Home</th></tr>")
    rows.append(_data_row("Home Value",   col("home_value"), indent=True))
    rows.append(_data_row("Mortgage",
                          [-subset.loc[y, "mortgage"] if y in subset.index else 0.0
                           for y in years],
                          indent=True))
    rows.append(_data_row("Home Equity",  col("home_equity"), bold=True))

    rows.append("<tr class='section sep'><th colspan='100'>Net Worth</th></tr>")
    rows.append(_data_row("Total Net Worth", col("total_net_worth"), bold=True))

    header = _header_row(years)
    body   = "\n".join(rows)
    return f"<table class='datatable'><thead>{header}</thead><tbody>{body}</tbody></table>"


# ── Cash Flow table ────────────────────────────────────────────────────────────

def build_cashflow_table(df: pd.DataFrame, config: dict | None = None) -> str:
    """
    Cash flow table: income sources at top, expenses below.
    Shows all modeled income and expense streams per year.
    """
    years  = _display_years(df)
    subset = df[df["year"].isin(years)].set_index("year")

    def col(field: str) -> list[float]:
        return [
            subset.loc[y, field] if (y in subset.index and field in subset.columns) else 0.0
            for y in years
        ]

    # Collect all unique event labels that appear across the displayed years
    event_map: dict[str, dict] = {}
    for y in years:
        if y not in subset.index:
            continue
        for item in (subset.loc[y, "event_items"] or []):
            label, amount, event_type, expense_kind = _event_item_parts(item)
            if label not in event_map:
                event_map[label] = {
                    "amounts": [0.0] * len(years),
                    "event_type": event_type,
                    "expense_kind": expense_kind,
                }
            idx = years.index(y)
            event_map[label]["amounts"][idx] += amount
            if event_map[label].get("event_type") is None:
                event_map[label]["event_type"] = event_type
            if event_map[label].get("expense_kind") is None:
                event_map[label]["expense_kind"] = expense_kind

    rows = []
    person1_name = _person_display_name(config, "person1")
    person2_name = _person_display_name(config, "person2")

    # ── Income ────────────────────────────────────────────────────────────────
    rows.append("<tr class='section'><th colspan='100'>Income</th></tr>")
    person_income_columns = sorted(
        [
            field for field in subset.columns
            if field.startswith("person") and field.endswith("_income")
        ]
    )
    for field in person_income_columns:
        person_key = field.removesuffix("_income")
        if person_key == "person1":
            person_name = person1_name
        elif person_key == "person2":
            person_name = person2_name
        else:
            person_name = _person_display_name(config, person_key)
        label = f"{person_name} earned income"
        rows.append(_data_row(label, col(field), indent=True))

    # Freed liability payments as income-side items
    freed = col("freed_payments")
    if any(v != 0 for v in freed):
        rows.append(_data_row("Freed loan payments",  freed, indent=True))

    for label, meta in event_map.items():
        amounts = meta["amounts"]
        if any(a > 0 for a in amounts):
            rows.append(_data_row(label, amounts, indent=True))

    total_income = [
        (
            sum(float(subset.loc[y, field]) for field in person_income_columns)
            + subset.loc[y, "freed_payments"]
            + sum(_event_item_parts(item)[1] for item in (subset.loc[y, "event_items"] or []) if _event_item_parts(item)[1] > 0)
        )
        if y in subset.index else 0.0
        for y in years
    ]
    rows.append(_data_row("Total Income", total_income, bold=True))

    # ── Portfolio funding / withdrawals ───────────────────────────────────────
    portfolio_funding_rows = [
        ("Cash reserve drawdown", col("withdrawal_cash")),
        ("Taxable withdrawals", col("withdrawal_taxable")),
        ("Traditional IRA / 401k withdrawals", col("withdrawal_trad_ira")),
        ("Required minimum distributions (RMD)", col("rmd_withdrawn")),
        ("Roth withdrawals", col("withdrawal_roth")),
    ]
    shown_portfolio_rows = [
        (label, amounts)
        for label, amounts in portfolio_funding_rows
        if any(v != 0 for v in amounts)
    ]
    if shown_portfolio_rows:
        rows.append("<tr class='section sep'><th colspan='100'>Portfolio Funding / Withdrawals</th></tr>")
        for label, amounts in shown_portfolio_rows:
            rows.append(_data_row(label, amounts, indent=True))
        total_portfolio_funding = [
            (
                subset.loc[y, "withdrawal_cash"]
                + subset.loc[y, "withdrawal_taxable"]
                + subset.loc[y, "withdrawal_trad_ira"]
                + subset.loc[y, "withdrawal_roth"]
            )
            if y in subset.index else 0.0
            for y in years
        ]
        rows.append(_data_row("Total Portfolio Funding", total_portfolio_funding, bold=True))

    # ── Retirement contributions (owner split when available) ─────────────────
    contribution_rows = [
        ("Traditional IRA / 401k contributions", col("contribution_trad_ira")),
        ("Roth contributions", col("contribution_roth")),
        (f"Traditional IRA / 401k contributions — {person1_name}", col("contribution_trad_ira_person1")),
        (f"Traditional IRA / 401k contributions — {person2_name}", col("contribution_trad_ira_person2")),
        (f"Roth contributions — {person1_name}", col("contribution_roth_person1")),
        (f"Roth contributions — {person2_name}", col("contribution_roth_person2")),
    ]
    shown_contribution_rows = [
        (label, amounts)
        for label, amounts in contribution_rows
        if any(v != 0 for v in amounts)
    ]
    if shown_contribution_rows:
        rows.append("<tr class='section sep'><th colspan='100'>Retirement Contributions</th></tr>")
        for label, amounts in shown_contribution_rows:
            rows.append(_data_row(label, amounts, indent=True))
        rows.append(_data_row("Total Retirement Contributions", col("contribution_total"), bold=True))

    # ── Expenses ──────────────────────────────────────────────────────────────
    rows.append("<tr class='section sep'><th colspan='100'>Expenses</th></tr>")
    rows.append(_data_row("Living expenses",
                          [-subset.loc[y, "annual_spend"] if y in subset.index else 0.0
                           for y in years],
                          indent=True))

    taxes = [
        -subset.loc[y, "annual_taxes"] if y in subset.index else 0.0
        for y in years
    ]
    if any(v != 0 for v in taxes):
        federal_taxes = [
            -subset.loc[y, "annual_federal_taxes"]
            if (y in subset.index and "annual_federal_taxes" in subset.columns) else 0.0
            for y in years
        ]
        state_taxes = [
            -subset.loc[y, "annual_state_taxes"]
            if (y in subset.index and "annual_state_taxes" in subset.columns) else 0.0
            for y in years
        ]
        if any(v != 0 for v in federal_taxes):
            rows.append(_data_row("Federal ordinary-income tax", federal_taxes, indent=True))
        if any(v != 0 for v in state_taxes):
            rows.append(_data_row("State income tax", state_taxes, indent=True))
        rows.append(_data_row("Modeled tax on retirement/event inflows", taxes, indent=True))

    mandatory_expense_events = []
    discretionary_expense_events = []
    other_outflow_events = []
    for label, meta in event_map.items():
        amounts = meta["amounts"]
        if not any(a < 0 for a in amounts):
            continue
        if meta.get("event_type") == "Expense":
            if meta.get("expense_kind") == "discretionary":
                discretionary_expense_events.append((label, amounts))
            else:
                mandatory_expense_events.append((label, amounts))
        else:
            other_outflow_events.append((label, amounts))

    if mandatory_expense_events:
        rows.append("<tr class='section'><th colspan='100'>Mandatory event expenses</th></tr>")
        for label, amounts in mandatory_expense_events:
            rows.append(_data_row(label, amounts, indent=True))

    if discretionary_expense_events:
        rows.append("<tr class='section'><th colspan='100'>Discretionary event expenses</th></tr>")
        for label, amounts in discretionary_expense_events:
            rows.append(_data_row(label, amounts, indent=True))

    if other_outflow_events:
        rows.append("<tr class='section'><th colspan='100'>Other event outflows</th></tr>")
        for label, amounts in other_outflow_events:
            rows.append(_data_row(label, amounts, indent=True))

    total_expenses = [
        -(
            subset.loc[y, "annual_spend"]
            + subset.loc[y, "annual_taxes"]
            + sum(_event_item_parts(item)[1] for item in (subset.loc[y, "event_items"] or []) if _event_item_parts(item)[1] < 0)
        )
        if y in subset.index else 0.0
        for y in years
    ]
    rows.append(_data_row("Total Expenses", total_expenses, bold=True))

    # ── Net ───────────────────────────────────────────────────────────────────
    rows.append("<tr class='section sep'><th colspan='100'>Net</th></tr>")
    rows.append(_data_row("Net Cash Flow", col("net_flow"), bold=True))

    header = _header_row(years)
    body   = "\n".join(rows)
    return f"<table class='datatable'><thead>{header}</thead><tbody>{body}</tbody></table>"


def build_portfolio_table(df: pd.DataFrame, config: dict | None = None) -> str:
    """Projected investable-portfolio balances for the Portfolio tab."""
    years = _display_years(df)
    subset = df[df["year"].isin(years)].set_index("year")

    def col(field: str) -> list[float]:
        return [
            subset.loc[y, field] if (y in subset.index and field in subset.columns) else 0.0
            for y in years
        ]

    rows = []
    person1_name = _person_display_name(config, "person1")
    person2_name = _person_display_name(config, "person2")

    rows.append("<tr class='section'><th colspan='100'>Projected Balances</th></tr>")
    rows.append(_data_row("Taxable", col("taxable"), indent=True))
    rows.append(_data_row("Traditional IRA / 401k", col("trad_ira"), indent=True))
    if "trad_ira_person1" in subset.columns:
        rows.append(_data_row(f"Traditional IRA / 401k — {person1_name}", col("trad_ira_person1"), indent=True))
    if "trad_ira_person2" in subset.columns:
        rows.append(_data_row(f"Traditional IRA / 401k — {person2_name}", col("trad_ira_person2"), indent=True))
    rows.append(_data_row("Roth", col("roth"), indent=True))
    if "roth_person1" in subset.columns:
        rows.append(_data_row(f"Roth — {person1_name}", col("roth_person1"), indent=True))
    if "roth_person2" in subset.columns:
        rows.append(_data_row(f"Roth — {person2_name}", col("roth_person2"), indent=True))
    rows.append(
        _data_row(
            "Total Investable Portfolio",
            [
                sum(
                    float(subset.loc[y, field])
                    for field in ("taxable", "trad_ira", "roth")
                    if field in subset.columns
                )
                if y in subset.index else 0.0
                for y in years
            ],
            bold=True,
            separator=True,
        )
    )

    header = _header_row(years)
    body = "\n".join(rows)
    return f"<table class='datatable'><thead>{header}</thead><tbody>{body}</tbody></table>"
