"""
demo_setup_page.py — Build a static read-only setup page for the demo.

This generates a self-contained HTML page showing a scenario's configuration
as a read-only form.  All inputs are disabled; there is no JavaScript for
saving or backend interaction.  The page is designed to be served from the
gh-pages demo alongside the sample projections.
"""

from html import escape
from pathlib import Path


def _fmt(val, default="") -> str:
    """Format a TOML value for display."""
    if val is None:
        return default
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".")
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


def _fmt_pct(val, default="") -> str:
    """Format a decimal as percentage for display."""
    if val is None:
        return default
    try:
        return f"{float(val) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _fmt_dollar(val, default="") -> str:
    """Format a number as dollar amount."""
    if val is None:
        return default
    try:
        v = float(val)
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    except (TypeError, ValueError):
        return str(val)


_STYLES = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 20px; background: #0b1220; color: #e5edf7; }
  .page-header { display: flex; align-items: center; justify-content: space-between;
                 margin-bottom: 20px; padding-bottom: 12px;
                 border-bottom: 1px solid #243142; }
  .page-title { font-size: 22px; font-weight: 700; margin: 0; }
  .page-subtitle { font-size: 13px; color: #9fb2c8; margin: 2px 0 0; }
  .back-link { color: #7dd3fc; font-size: 13px; font-weight: 600;
               text-decoration: none; }
  .back-link:hover { color: #fff; }
  .version-tag { font-size: 11px; color: #64748b; font-weight: 400;
                 margin-left: 8px; letter-spacing: 0.03em; }
  .config-section { background: #111827; border-radius: 8px;
                    border: 1px solid #243142; margin-bottom: 14px;
                    padding: 16px; }
  .config-section h3 { margin: 0 0 12px; font-size: 15px; color: #f8fafc;
                       padding-bottom: 8px; border-bottom: 1px solid #243142; }
  .field-row { display: flex; flex-wrap: wrap; gap: 10px 16px; margin-bottom: 8px; }
  .field { flex: 1 1 180px; min-width: 140px; }
  .field-label { font-size: 11px; color: #9fb2c8; font-weight: 600;
                 letter-spacing: 0.03em; text-transform: uppercase;
                 display: block; margin-bottom: 2px; }
  .field-value { font-size: 14px; color: #e5edf7; padding: 4px 0;
                 font-variant-numeric: tabular-nums; }
  .field-note { font-size: 11px; color: #64748b; margin-top: 1px; }
  .toml-box { background: #0f1725; border-radius: 6px; border: 1px solid #243142;
              padding: 12px; font-family: 'SF Mono', 'Fira Code', monospace;
              font-size: 12px; line-height: 1.5; color: #cbd5e1;
              overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
  .toml-box .comment { color: #64748b; font-style: italic; }
  .data-source-badge { display: inline-block; padding: 2px 10px;
                       border-radius: 99px; font-size: 11px; font-weight: 600;
                       background: #1e293b; color: #94a3b8;
                       border: 1px solid #475569; }
"""


def build_demo_setup_page(*, config_path: Path, output_path: Path, slug: str) -> None:
    """Generate a static read-only setup page from a scenario TOML file."""
    import tomllib

    raw_toml = config_path.read_text(encoding="utf-8")
    config = tomllib.loads(raw_toml)

    scenario = config.get("scenario", {}) or {}
    sim = config.get("simulation", {}) or {}
    person1 = config.get("person1", {}) or {}
    person2 = config.get("person2", {}) or {}
    spending = config.get("spending", {}) or {}
    assumptions = config.get("assumptions", {}) or {}
    withdrawal = config.get("withdrawal_policy", {}) or {}
    data_source = config.get("data_source", {}) or {}
    synthetic = config.get("synthetic_start", {}) or {}
    ds_mode = data_source.get("mode", "monarch")
    household_type = scenario.get("household_type", "couple" if person2 else "single")

    # ── People section ────────────────────────────────────────────────────
    def _person_fields(p: dict, key: str) -> str:
        name = p.get("name", key)
        dob = p.get("dob", "")
        birth_year = str(dob).split("-")[0] if dob else ""
        life_exp = p.get("life_expectancy", "")
        retire = p.get("retirement_year", "")
        ss_age = p.get("ss_start_age", "")
        income = p.get("annual_take_home", "")
        gross = p.get("gross_income", "")
        contrib_pct = _fmt_pct(p.get("retirement_contribution_percent"))
        return f"""
    <div class="field-row">
      <div class="field"><span class="field-label">Name</span><div class="field-value">{escape(name)}</div></div>
      <div class="field"><span class="field-label">Birth Year</span><div class="field-value">{escape(birth_year)}</div></div>
      <div class="field"><span class="field-label">Life Expectancy</span><div class="field-value">{_fmt(life_exp)}</div></div>
      <div class="field"><span class="field-label">Retirement Year</span><div class="field-value">{_fmt(retire)}</div></div>
      <div class="field"><span class="field-label">SS Start Age</span><div class="field-value">{_fmt(ss_age)}</div></div>
      <div class="field"><span class="field-label">Annual Take-Home</span><div class="field-value">{_fmt_dollar(income)}</div></div>
      <div class="field"><span class="field-label">Gross Income</span><div class="field-value">{_fmt_dollar(gross)}</div></div>
      <div class="field"><span class="field-label">Contribution %</span><div class="field-value">{contrib_pct}</div></div>
    </div>"""

    people_html = _person_fields(person1, "person1")
    if person2:
        people_html += '<hr style="border:none;border-top:1px solid #243142;margin:8px 0">'
        people_html += _person_fields(person2, "person2")

    # ── Investment assumptions ──────────────────────────────────────────
    equity_alloc = assumptions.get("equity_allocation", "")
    stock_ret = assumptions.get("stock_return", "")
    bond_ret = assumptions.get("bond_return", "")
    inflation = assumptions.get("inflation", "")
    start_year = sim.get("start_year", "")
    end_year = sim.get("end_year", "")
    real_dollar = sim.get("real_dollar_basis", False)
    render_modes = sim.get("render_modes", [])
    state_tax = config.get("taxes", {}).get("table_set", "")
    spending_retirement = spending.get("retirement_annual", "")
    debt_handling = spending.get("debt_service_handling", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NWN Demo — Scenario Setup</title>
  <style>{_STYLES}</style>
</head>
<body>

<div class="page-header">
  <div>
    <h1 class="page-title">Scenario Setup <span class="version-tag">read-only demo</span></h1>
    <p class="page-subtitle">{escape(scenario.get("name", slug))}</p>
  </div>
  <a class="back-link" href="./projection.html?scenario={escape(slug)}">← Back to projection</a>
</div>

<div class="config-section">
  <h3>Data Source</h3>
  <div class="field-row">
    <div class="field">
      <span class="field-label">Mode</span>
      <div><span class="data-source-badge">{escape(ds_mode)}</span></div>
    </div>
    {f'<div class="field"><span class="field-label">State Tax</span><div class="field-value">{escape(state_tax)}</div></div>' if state_tax else ''}
    {('<div class="field"><span class="field-label">Real-Dollar Display</span><div class="field-value">' + ('Enabled (start-year dollars)' if real_dollar else 'Disabled (nominal dollars)') + '</div></div>')}
  </div>
</div>

<div class="config-section">
  <h3>Household</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Type</span><div class="field-value">{escape(household_type)}</div></div>
    <div class="field"><span class="field-label">Render Modes</span><div class="field-value">{escape(", ".join(render_modes))}</div></div>
    <div class="field"><span class="field-label">Projection Window</span><div class="field-value">{_fmt(start_year)} – {_fmt(end_year)}</div></div>
  </div>
  {people_html}
</div>

<div class="config-section">
  <h3>Investment Assumptions</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Stock Return</span><div class="field-value">{_fmt_pct(stock_ret)}</div></div>
    <div class="field"><span class="field-label">Bond Return</span><div class="field-value">{_fmt_pct(bond_ret)}</div></div>
    <div class="field"><span class="field-label">Inflation</span><div class="field-value">{_fmt_pct(inflation)}</div></div>
    <div class="field"><span class="field-label">Equity Allocation</span><div class="field-value">{_fmt_pct(equity_alloc)}</div></div>
  </div>
</div>

<div class="config-section">
  <h3>Spending & Withdrawals</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Retirement Spending</span><div class="field-value">{_fmt_dollar(spending_retirement)}</div></div>
    <div class="field"><span class="field-label">Debt Handling</span><div class="field-value">{escape(debt_handling) if debt_handling else '—'}</div></div>
  </div>
  <div class="field-row">
    <div class="field"><span class="field-label">Cash Target (Accumulation)</span><div class="field-value">{_fmt_dollar(withdrawal.get("accumulation_cash_target"))}</div></div>
    <div class="field"><span class="field-label">Cash Target (Retirement)</span><div class="field-value">{_fmt_dollar(withdrawal.get("retirement_cash_target"))}</div></div>
    <div class="field"><span class="field-label">Cash Target (Survivor)</span><div class="field-value">{_fmt_dollar(withdrawal.get("survivor_cash_target"))}</div></div>
  </div>
</div>

<div class="config-section">
  <h3>Starting Balances <span class="data-source-badge" style="font-size:10px">{escape(ds_mode)}</span></h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Taxable</span><div class="field-value">{_fmt_dollar(synthetic.get("taxable"))}</div></div>
    <div class="field"><span class="field-label">Traditional IRA</span><div class="field-value">{_fmt_dollar(synthetic.get("trad_ira"))}</div></div>
    <div class="field"><span class="field-label">Roth</span><div class="field-value">{_fmt_dollar(synthetic.get("roth"))}</div></div>
    <div class="field"><span class="field-label">Cash</span><div class="field-value">{_fmt_dollar(synthetic.get("cash"))}</div></div>
    <div class="field"><span class="field-label">Home Value</span><div class="field-value">{_fmt_dollar(synthetic.get("home_value"))}</div></div>
  </div>
</div>

<div class="config-section">
  <h3>Raw Configuration</h3>
  <div class="toml-box">{escape(raw_toml)}</div>
  <div class="field-note" style="margin-top:6px">This is a read-only demo. The configuration shown here is for reference only.</div>
</div>

</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
