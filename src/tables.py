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
        key for key in ("matthew", "weny")
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


def _kv_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><th>{escape(label)}</th><td>{value}</td></tr>"
        for label, value in rows
    )
    return f"<table class='assumptions-table assumptions-kv'><tbody>{body}</tbody></table>"


def build_assumptions_summary(config: dict) -> str:
    """Return a formatted HTML summary of the current modeling assumptions."""
    people_rows = []
    for person_key in _person_keys(config):
        person = config.get(person_key, {})
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

        people_rows.append(
            "<tr>"
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
        ("Stock return", _fmt_percent(assumptions.get("stock_return"))),
        ("Bond return", _fmt_percent(assumptions.get("bond_return"))),
        ("Inflation", _fmt_percent(assumptions.get("inflation"))),
        ("Real estate appreciation", _fmt_percent(assumptions.get("real_estate_appreciation"))),
        ("Equity allocation", _fmt_percent(assumptions.get("equity_allocation"))),
        ("Real estate sale fee rate", _fmt_percent(assumptions.get("real_estate_sale_fee_rate"))),
    ]

    spending = config.get("spending", {})
    spending_rows = [
        ("Retirement annual", _fmt_currency(spending.get("retirement_annual"))),
        ("Survivor annual", _fmt_currency(spending.get("survivor_annual"))),
    ]

    withdrawal_policy = config.get("withdrawal_policy", {})
    withdrawal_rows = [
        ("Accumulation cash target", _fmt_currency(withdrawal_policy.get("accumulation_cash_target"))),
        ("Retirement cash target", _fmt_currency(withdrawal_policy.get("retirement_cash_target"))),
        ("Survivor cash target", _fmt_currency(withdrawal_policy.get("survivor_cash_target"))),
    ]

    return (
        "<div class='assumptions-wrap'>"
        "<div class='assumptions-note'>Current planning assumptions from <code>config.toml</code>.</div>"
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

def build_accounts_table(df: pd.DataFrame) -> str:
    """
    Net Worth table: assets at top, liabilities below, home equity and
    total net worth at the bottom.
    """
    years  = _display_years(df)
    subset = df[df["year"].isin(years)].set_index("year")

    def col(field: str) -> list[float]:
        return [subset.loc[y, field] if y in subset.index else 0.0 for y in years]

    rows = []
    rows.append("<tr class='section'><th colspan='100'>Assets</th></tr>")
    rows.append(_data_row("Traditional IRA / 401k", col("trad_ira"),  indent=True))
    rows.append(_data_row("Roth",                    col("roth"),      indent=True))
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

def build_cashflow_table(df: pd.DataFrame) -> str:
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

    # ── Income ────────────────────────────────────────────────────────────────
    rows.append("<tr class='section'><th colspan='100'>Income</th></tr>")
    rows.append(_data_row("Person 1 earned income",  col("matthew_income"), indent=True))
    rows.append(_data_row("Person 2 earned income",     col("weny_income"),    indent=True))

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
            subset.loc[y, "matthew_income"]
            + subset.loc[y, "weny_income"]
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
