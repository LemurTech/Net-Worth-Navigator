"""
tables.py — Build HTML tables for the Accounts and Cash Flow tabs.

Each function returns a self-contained HTML string ready to embed
in the tabbed page wrapper produced by charts.py.
"""
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
        return [subset.loc[y, field] if y in subset.index else 0.0 for y in years]

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
