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


def _fmt(value: float) -> str:
    """Format a dollar value: negative in red, positive normal."""
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
    event_label_set: dict[str, list[float]] = {}
    for y in years:
        if y not in subset.index:
            continue
        for label, amount in (subset.loc[y, "event_items"] or []):
            if label not in event_label_set:
                event_label_set[label] = [0.0] * len(years)
            idx = years.index(y)
            event_label_set[label][idx] += amount

    rows = []

    # ── Income ────────────────────────────────────────────────────────────────
    rows.append("<tr class='section'><th colspan='100'>Income</th></tr>")
    rows.append(_data_row("Person 1 earned income",  col("matthew_income"), indent=True))
    rows.append(_data_row("Person 2 earned income",     col("weny_income"),    indent=True))

    # Freed liability payments as income-side items
    freed = col("freed_payments")
    if any(v != 0 for v in freed):
        rows.append(_data_row("Freed loan payments",  freed, indent=True))

    total_income = [
        (subset.loc[y, "matthew_income"] + subset.loc[y, "weny_income"]
         + subset.loc[y, "freed_payments"])
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

    for label, amounts in event_label_set.items():
        if any(a < 0 for a in amounts):
            # Outflow event
            rows.append(_data_row(label, amounts, indent=True))
        # Income events shown in income section above via event_items totals

    total_expenses = [
        -(subset.loc[y, "annual_spend"] +
          sum(a for _, a in (subset.loc[y, "event_items"] or []) if a < 0))
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
