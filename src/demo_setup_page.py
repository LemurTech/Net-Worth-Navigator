"""
demo_setup_page.py — Build a static read-only setup page for the demo.

This generates a self-contained HTML page showing a scenario's configuration
as a read-only form styled to resemble the real NWN setup panel, with tabs
and input-like field borders.  No JavaScript for saving or backend interaction.
"""

from html import escape
from pathlib import Path


def _fmt(val, default="") -> str:
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
    if val is None:
        return default
    try:
        return f"{float(val) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _fmt_dollar(val, default="") -> str:
    if val is None:
        return default
    try:
        v = float(val)
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    except (TypeError, ValueError):
        return str(val)


def _input_style(mono: bool = False) -> str:
    """Style string that makes a field look like a disabled text input."""
    font = "font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px" if mono else "font-size:14px"
    return (
        f"padding:8px 12px;border:1px solid #334155;border-radius:8px;"
        f"background:rgba(15,23,37,0.5);color:#e5edf7;{font};"
        f"font-variant-numeric:tabular-nums;min-height:18px"
    )


_STYLES = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 20px; background: #0b1220; color: #e5edf7;
         caret-color: transparent; }
  html { background: #0b1220; }
  * { outline: none; box-sizing: border-box; }
  .page-header { display: flex; align-items: center; justify-content: space-between;
                 margin-bottom: 20px; padding-bottom: 12px;
                 border-bottom: 1px solid #243142; flex-wrap: wrap; gap: 8px; }
  .page-header .controls { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .page-title { font-size: 22px; font-weight: 700; margin: 0; }
  .back-link { color: #7dd3fc; font-size: 13px; font-weight: 600;
               text-decoration: none; white-space: nowrap; }
  .back-link:hover { color: #fff; }
  @media (max-width: 600px) {
    .page-header { flex-direction: column; align-items: flex-start; }
    .page-header .controls { width: 100%; justify-content: space-between; }
  }
  .version-tag { font-size: 11px; color: #64748b; font-weight: 400;
                 margin-left: 8px; letter-spacing: 0.03em; }
  .scenario-select { background: #1e293b; color: #e5edf7; border: 1px solid #475569;
                     border-radius: 6px; padding: 6px 10px; font-size: 13px;
                     font-family: inherit; cursor: pointer; min-width: 180px; }

  /* ── Tab bar ─────────────────────────────────────────────────── */
  .tab-bar { display: flex; gap: 0; border-bottom: 2px solid #243142;
             margin-bottom: 16px; }
  .tab-bar label { padding: 10px 18px; border: none; cursor: pointer;
                   font-size: 14px; color: #93a4ba; border-bottom: 3px solid transparent;
                   margin-bottom: -2px; transition: color .15s; user-select: none; }
  .tab-bar label:hover { color: #cbd5e1; }
  .tab-content { display: none; }

  /* Radio hack: show tab content when its radio is checked */
  .tab-radio { display: none; }
  #tab-r0:checked ~ .tab-bar label[for="tab-r0"],
  #tab-r1:checked ~ .tab-bar label[for="tab-r1"],
  #tab-r2:checked ~ .tab-bar label[for="tab-r2"],
  #tab-r3:checked ~ .tab-bar label[for="tab-r3"] {
    color: #f8fafc; border-bottom-color: #7dd3fc; }
  #tab-r0:checked ~ #tab-c0 { display: block; }
  #tab-r1:checked ~ #tab-c1 { display: block; }
  #tab-r2:checked ~ #tab-c2 { display: block; }
  #tab-r3:checked ~ #tab-c3 { display: block; }

  /* ── Section card ─────────────────────────────────────────────── */
  .section-card { background: #111827; border-radius: 8px;
                  border: 1px solid #243142; margin-bottom: 14px;
                  padding: 16px; }
  .section-card h3 { margin: 0 0 12px; font-size: 15px; color: #f8fafc;
                     padding-bottom: 8px; border-bottom: 1px solid #243142;
                     font-weight: 600; }
  .field-row { display: flex; flex-wrap: wrap; gap: 10px 16px; margin-bottom: 10px; }
  .field { flex: 1 1 180px; min-width: 140px; display: flex; flex-direction: column; }
  .field-label { font-size: 11px; color: #94a3b8; font-weight: 600;
                 letter-spacing: 0.04em; text-transform: uppercase;
                 display: block; margin-bottom: 4px; }
  .field-value { padding: 8px 12px; border: 1px solid #334155; border-radius: 8px;
                 background: rgba(15,23,37,0.5); color: #e5edf7; font-size: 14px;
                 font-variant-numeric: tabular-nums; min-height: 18px; line-height: 1.4; }
  .field-value.mono { font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
                      font-size: 13px; }
  .field-note { font-size: 11px; color: #64748b; margin-top: 4px; }
  .toml-box { background: rgba(15,23,37,0.5); border-radius: 8px;
              border: 1px solid #334155; padding: 12px;
              font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
              font-size: 12px; line-height: 1.5; color: #cbd5e1;
              overflow-x: auto; white-space: pre; }
  .data-source-badge { display: inline-block; padding: 4px 12px;
                       border-radius: 99px; font-size: 11px; font-weight: 600;
                       background: #1e293b; color: #94a3b8;
                       border: 1px solid #475569; }
"""


def build_demo_setup_page(
    *, config_path: Path, output_path: Path, slug: str,
    scenario_options: list[tuple[str, str]] | None = None,
    setup_relbase: str = "./scenarios/",
    back_relbase: str = "./",
) -> None:
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
    taxes = config.get("taxes", {}) or {}
    ds_mode = data_source.get("mode", "monarch")
    household_type = scenario.get("household_type", "couple" if person2 else "single")

    scenario_name = escape(scenario.get("name", slug))
    scenario_desc = escape(scenario.get("description", "")) or '<span style="color:#64748b;font-style:italic">No description</span>'

    # ── Person fields helper ──────────────────────────────────────────
    def _person_row(p: dict, label: str) -> str:
        name = escape(p.get("name", label))
        dob = p.get("dob", "")
        birth_year = str(dob).split("-")[0] if dob else ""
        life_exp = _fmt(p.get("life_expectancy"))
        retire = _fmt(p.get("retirement_year"))
        ss_age = _fmt(p.get("ss_start_age"))
        income = _fmt_dollar(p.get("annual_take_home"))
        gross = _fmt_dollar(p.get("gross_income"))
        contrib = _fmt_pct(p.get("retirement_contribution_percent"))
        return f"""
    <div class="field-row">
      <div class="field"><span class="field-label">Name</span><div class="field-value">{name}</div></div>
      <div class="field"><span class="field-label">Birth Year</span><div class="field-value">{birth_year}</div></div>
      <div class="field"><span class="field-label">Life Expectancy</span><div class="field-value">{life_exp}</div></div>
      <div class="field"><span class="field-label">Retirement Year</span><div class="field-value">{retire}</div></div>
      <div class="field"><span class="field-label">SS Start Age</span><div class="field-value">{ss_age}</div></div>
      <div class="field"><span class="field-label">Take-Home Pay</span><div class="field-value">{income}</div></div>
      <div class="field"><span class="field-label">Gross Income</span><div class="field-value">{gross}</div></div>
      <div class="field"><span class="field-label">Contribution</span><div class="field-value">{contrib}</div></div>
    </div>"""

    people_html = _person_row(person1, "person1")
    if person2:
        people_html += '<hr style="border:none;border-top:1px solid #243142;margin:8px 0">'
        people_html += _person_row(person2, "person2")

    equity_alloc = _fmt_pct(assumptions.get("equity_allocation"))
    stock_ret = _fmt_pct(assumptions.get("stock_return"))
    bond_ret = _fmt_pct(assumptions.get("bond_return"))
    inflation = _fmt_pct(assumptions.get("inflation"))
    start_year = _fmt(sim.get("start_year"))
    end_year = _fmt(sim.get("end_year"))
    real_dollar = sim.get("real_dollar_basis", False)
    render_modes = escape(", ".join(sim.get("render_modes", [])))
    state_tax = escape(taxes.get("table_set", ""))
    spending_ret = _fmt_dollar(spending.get("retirement_annual"))
    debt_handling = escape(spending.get("debt_service_handling", "")) or "—"
    cash_acc = _fmt_dollar(withdrawal.get("accumulation_cash_target"))
    cash_ret = _fmt_dollar(withdrawal.get("retirement_cash_target"))
    cash_sur = _fmt_dollar(withdrawal.get("survivor_cash_target"))

    taxable = _fmt_dollar(synthetic.get("taxable"))
    trad_ira = _fmt_dollar(synthetic.get("trad_ira"))
    roth = _fmt_dollar(synthetic.get("roth"))
    cash = _fmt_dollar(synthetic.get("cash"))
    home_value = _fmt_dollar(synthetic.get("home_value"))

    # ── Scenario selector dropdown ──────────────────────────────────
    selector_html = ""
    if scenario_options:
        def _option_tag(s, n):
            sel = " selected" if s == slug else ""
            return f'<option value="{setup_relbase}{s}/setup.html"{sel}>{escape(n)}</option>'
        opts = "".join(_option_tag(s, n) for s, n in scenario_options)
        selector_html = f'<select class="scenario-select" onchange="window.location.href=this.value">{opts}</select>'

    real_dollar_text = "Enabled (start-year dollars)" if real_dollar else "Disabled (nominal dollars)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NWN Demo — Scenario Setup</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111827'/%3E%3Cg fill='none' stroke='%237dd3fc' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6,22 10,18 15,20 20,12 26,7'/%3E%3C/g%3E%3Cg fill='%2338bdf8' opacity='0.35'%3E%3Crect x='5' y='23' width='3' height='5' rx='0.8'/%3E%3Crect x='9' y='21' width='3' height='7' rx='0.8'/%3E%3Crect x='14' y='22' width='3' height='6' rx='0.8'/%3E%3Crect x='19' y='16' width='3' height='12' rx='0.8'/%3E%3Crect x='24' y='14' width='3' height='14' rx='0.8'/%3E%3C/g%3E%3C/svg%3E">
  <style>{_STYLES}</style>
</head>
<body>

<div class="page-header">
  <div>
    <h1 class="page-title">Scenario Setup <span class="version-tag">read-only demo</span></h1>
  </div>
  <div class="controls">
    <a class="back-link" href="{back_relbase}projection.html?scenario={escape(slug)}">← Back to projection</a>
    {selector_html}
  </div>
</div>

<!-- ── Tab radio buttons (CSS-only) ────────────────────────────── -->
<input type="radio" name="tabs" class="tab-radio" id="tab-r0" checked>
<input type="radio" name="tabs" class="tab-radio" id="tab-r1">
<input type="radio" name="tabs" class="tab-radio" id="tab-r2">

<div class="tab-bar">
  <label for="tab-r0">Metadata</label>
  <label for="tab-r1">Accounts</label>
  <label for="tab-r2">Raw TOML</label>
</div>

<!-- ══════════════════ TAB: METADATA ═══════════════════════════ -->
<div class="tab-content" id="tab-c0">

<div class="section-card">
  <h3>Scenario</h3>
  <div class="field-row">
    <div class="field" style="flex:2 1 300px"><span class="field-label">Plan Name</span><div class="field-value">{scenario_name}</div></div>
  </div>
  <div class="field-row">
    <div class="field" style="flex:2 1 300px"><span class="field-label">Description</span><div class="field-value">{scenario_desc}</div></div>
  </div>
  <div class="field-row">
    <div class="field"><span class="field-label">Slug</span><div class="field-value mono">{escape(slug)}</div></div>
    <div class="field"><span class="field-label">Household Type</span><div class="field-value">{escape(household_type)}</div></div>
  </div>
</div>

<div class="section-card">
  <h3>People</h3>
  {people_html}
</div>

<div class="section-card">
  <h3>Investment Assumptions</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Stock Return</span><div class="field-value">{stock_ret}</div></div>
    <div class="field"><span class="field-label">Bond Return</span><div class="field-value">{bond_ret}</div></div>
    <div class="field"><span class="field-label">Inflation</span><div class="field-value">{inflation}</div></div>
    <div class="field"><span class="field-label">Equity Allocation</span><div class="field-value">{equity_alloc}</div></div>
  </div>
  <div class="field-row">
    <div class="field"><span class="field-label">Projection Window</span><div class="field-value">{start_year} – {end_year}</div></div>
    <div class="field"><span class="field-label">Render Modes</span><div class="field-value">{render_modes}</div></div>
    <div class="field"><span class="field-label">State Tax</span><div class="field-value">{state_tax}</div></div>
    <div class="field"><span class="field-label">Real-Dollar Display</span><div class="field-value">{real_dollar_text}</div></div>
  </div>
</div>

<div class="section-card">
  <h3>Spending & Withdrawals</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Retirement Spending</span><div class="field-value">{spending_ret}</div></div>
    <div class="field"><span class="field-label">Debt Handling</span><div class="field-value">{debt_handling}</div></div>
  </div>
  <div class="field-row">
    <div class="field"><span class="field-label">Cash Target (Accumulation)</span><div class="field-value">{cash_acc}</div></div>
    <div class="field"><span class="field-label">Cash Target (Retirement)</span><div class="field-value">{cash_ret}</div></div>
    <div class="field"><span class="field-label">Cash Target (Survivor)</span><div class="field-value">{cash_sur}</div></div>
  </div>
</div>

</div><!-- /#tab-c0 -->

<!-- ══════════════════ TAB: ACCOUNTS ═══════════════════════════ -->
<div class="tab-content" id="tab-c1">

<div class="section-card">
  <h3>Data Source</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Mode</span><div><span class="data-source-badge">{escape(ds_mode)}</span></div></div>
  </div>
</div>

<div class="section-card">
  <h3>Starting Balances</h3>
  <div class="field-row">
    <div class="field"><span class="field-label">Taxable</span><div class="field-value">{taxable}</div></div>
    <div class="field"><span class="field-label">Traditional IRA</span><div class="field-value">{trad_ira}</div></div>
    <div class="field"><span class="field-label">Roth</span><div class="field-value">{roth}</div></div>
    <div class="field"><span class="field-label">Cash</span><div class="field-value">{cash}</div></div>
    <div class="field"><span class="field-label">Home Value</span><div class="field-value">{home_value}</div></div>
  </div>
</div>

</div><!-- /#tab-c1 -->

<!-- ══════════════════ TAB: RAW TOML ═══════════════════════════ -->
<div class="tab-content" id="tab-c2">

<div class="section-card">
  <h3>Raw Configuration</h3>
  <div class="toml-box">{escape(raw_toml)}</div>
  <div class="field-note">This is a read-only demo. Configuration is for reference only.</div>
</div>

</div><!-- /#tab-c2 -->

</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
