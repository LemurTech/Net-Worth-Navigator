"""Generate static, read-only Scenario Setup pages for the public demo."""

from __future__ import annotations

from html import escape
from pathlib import Path


def _text(value, default: str = "—") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return " → ".join(str(item).replace("_", " ") for item in value) or default
    return str(value)


def _money(value, default: str = "—") -> str:
    if value is None or value == "":
        return default
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return _text(value, default)
    return f"${amount:,.0f}" if amount >= 0 else f"-${abs(amount):,.0f}"


def _percent(value, default: str = "—") -> str:
    if value is None or value == "":
        return default
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return _text(value, default)


def _event_for(config: dict, event_type: str, person: str) -> dict | None:
    for event in config.get("events", []) or []:
        if (
            event.get("type") == event_type
            and event.get("person") == person
            and event.get("enabled", True)
        ):
            return event
    return None


def _event_age(person: dict, event: dict | None) -> int | None:
    if not event:
        return None
    if event.get("age") is not None:
        try:
            return int(event["age"])
        except (TypeError, ValueError):
            return None
    try:
        return int(event["year"]) - int(str(person.get("dob", "")).split("-")[0])
    except (TypeError, ValueError):
        return None


def _field(label: str, value: str, note: str = "") -> str:
    note_html = f'<div class="note">{escape(note)}</div>' if note else ""
    return (
        '<div class="field"><div class="label">'
        f"{escape(label)}</div><div class=\"value\">{escape(value)}</div>{note_html}</div>"
    )


def _fields(items: list[tuple[str, str, str]]) -> str:
    return '<div class="field-grid">' + "".join(_field(*item) for item in items) + "</div>"


def _section(title: str, content: str, hint: str = "") -> str:
    hint_html = f'<div class="hint">{escape(hint)}</div>' if hint else ""
    if title.startswith("Advanced:"):
        return (
            '<details class="section advanced"><summary><span>▼ '
            f'{escape(title)}</span><span class="summary-note">Read-only details</span></summary>'
            f'<div class="advanced-body">{content}{hint_html}</div></details>'
        )
    return f'<section class="section"><h3>{escape(title)}</h3>{content}{hint_html}</section>'


def _person_title(person: dict, fallback: str) -> str:
    return str(person.get("name") or fallback.replace("person", "Person ").title())


def _person_income(person: dict, title: str) -> str:
    pct = _percent
    blocks = [
        _section("Employment", _fields([
            ("Take-Home Pay", _money(person.get("annual_take_home")), "Annual net-cash wage input"),
            ("Real Raise", pct(person.get("annual_take_home_real_raise")), "Above inflation"),
            ("Pay Is Net of Contributions", _text(person.get("annual_take_home_is_net_of_retirement_contributions")), ""),
        ]), "Take-home pay is anchored at the simulation start year and grows forward. Mark it net of contributions to avoid subtracting payroll savings twice."),
    ]
    method = str(person.get("contribution_method") or "flat")
    contribution_items = [("Contribution Method", method.replace("_", " "), "")]
    if method == "percent_of_gross":
        contribution_items += [
            ("Gross Income", _money(person.get("gross_income")), "Used for contribution math"),
            ("Gross Income Growth", pct(person.get("gross_income_annual_increase_percent")), "Annual percentage growth"),
            ("Starting Contribution Rate", pct(person.get("retirement_contribution_percent")), "Percent of gross income"),
            ("Annual Rate Increase", pct(person.get("retirement_contribution_annual_increase_percent")), "Percentage points per year"),
            ("Maximum Contribution Rate", pct(person.get("retirement_contribution_max_percent")), ""),
        ]
    else:
        contribution_items += [
            ("Annual 401(k) Contribution", _money(person.get("annual_401k_contribution")), ""),
            ("Annual Extra Increase", _money(person.get("annual_401k_contribution_extra_increase")), ""),
        ]
    blocks.append(_section("Retirement Contributions", _fields(contribution_items), "Percent-of-gross rates are shares of gross income. Annual rate increases are percentage points, not percent growth."))
    match_mode = str(person.get("annual_401k_employer_match_mode") or "flat")
    match_items = [("Employer Match Method", match_mode.replace("_", " "), "")]
    if match_mode == "percent_of_gross":
        match_items += [
            ("Match Rate", pct(person.get("annual_401k_employer_match_rate")), "Match on each contributed dollar"),
            ("Maximum Eligible Pay", pct(person.get("annual_401k_employer_match_max_percent")), ""),
        ]
    else:
        match_items.append(("Annual Employer Match", _money(person.get("annual_401k_employer_match")), ""))
    match_items += [
        ("Annual IRA Contribution", _money(person.get("annual_ira_contribution")), ""),
        ("401(k) Routing", _text(person.get("annual_401k_contribution_bucket")), ""),
        ("IRA Routing", _text(person.get("annual_ira_contribution_bucket")), ""),
        ("401(k) Split: Traditional", pct((person.get("annual_401k_contribution_split") or {}).get("trad_ira")), ""),
        ("401(k) Split: Roth", pct((person.get("annual_401k_contribution_split") or {}).get("roth")), ""),
        ("Traditional Balance Share", pct(person.get("rmd_trad_ira_share")), "Used for RMD math"),
        ("Roth Balance Share", pct(person.get("roth_share")), "Fallback when account owner is unspecified"),
    ]
    blocks.append(_section("Employer Match, Routing & Ownership", _fields(match_items), "A split override routes each 401(k) contribution proportionally. Account-level owners take precedence over these household fallback shares."))
    return f'<div class="person-block"><h2>{escape(title)}</h2>{"".join(blocks)}</div>'


EVENT_ICONS = {
    "EndOfPlan": "💀", "Retire": "🎉", "SocialSecurity": "🏛️",
    "Expense": "💸", "Income": "💰", "BuyHome": "🏠", "SellHome": "🏷️",
    "NewJob": "💼", "CareerBreak": "⏸️", "Education": "🎓",
    "Marriage": "💍", "SpendingShift": "📊", "ContributionChange": "📈",
}


def _event_card(event: dict) -> str:
    label = str(event.get("label") or event.get("type") or "Event")
    event_type = str(event.get("type") or "Event")
    enabled = bool(event.get("enabled", True))
    icon = EVENT_ICONS.get(event_type, "•")
    details = []
    money_keys = {"amount", "annual_cost", "annual_income", "down_payment", "price"}
    percent_keys = {"sale_fee_rate", "reinvest_fraction", "taxable_fraction"}
    for key, value in event.items():
        if key in {"label", "type", "enabled"}:
            continue
        display = _money(value) if key in money_keys else _percent(value) if key in percent_keys else _text(value)
        details.append(_field(key.replace("_", " ").title(), display))
    state = "Enabled" if enabled else "Disabled"
    return (
        '<article class="event-card"><div class="event-icon" aria-hidden="true">'
        f'{icon}</div><div class="event-main"><div class="event-head"><div><strong>'
        f"{escape(label)}</strong><span>{escape(event_type)}</span></div>"
        f'<span class="badge {"disabled" if not enabled else ""}">{state}</span></div>'
        f'<div class="field-grid">{"".join(details)}</div></div></article>'
    )


_STYLES = """
:root { --bg:#0b1220; --panel:#111827; --panel2:#0f1725; --text:#e5edf7; --muted:#9fb2c8; --border:#243142; --accent:#7dd3fc; }
* { box-sizing:border-box; } html,body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
body { padding:20px; } .page { max-width:1280px; margin:auto; } .top { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; border-bottom:1px solid var(--border); padding-bottom:14px; }
h1 { margin:0; font-size:22px; } h2 { font-size:15px; margin:0 0 12px; padding:10px 0; border-top:1px solid var(--border); border-bottom:1px solid var(--border); } h3 { margin:0 0 12px; font-size:14px; }
.controls { display:flex; gap:10px; align-items:center; flex-wrap:wrap; } .link,.scenario-select { border:1px solid var(--border); border-radius:8px; background:#162234; color:var(--text); padding:7px 10px; font:600 13px inherit; text-decoration:none; }
.scenario-select { min-width:185px; cursor:pointer; } .readonly { margin:14px 0; padding:14px 16px; border:1px solid rgba(125,211,252,.35); background:linear-gradient(135deg,rgba(14,165,233,.15),rgba(15,23,37,.7)); border-radius:10px; color:var(--muted); font-size:13px; line-height:1.45; } .readonly strong { color:var(--text); display:block; font-size:14px; margin-bottom:3px; } .demo-cues { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; } .demo-cue { border:1px solid #334155; border-radius:999px; padding:4px 8px; font-size:11px; color:#cbd5e1; background:rgba(15,23,37,.65); }
.tabs { display:flex; overflow-x:auto; border-bottom:2px solid var(--border); margin-bottom:16px; } .tab { appearance:none; border:0; border-bottom:3px solid transparent; background:transparent; color:var(--muted); padding:11px 14px; white-space:nowrap; cursor:pointer; font:600 13px inherit; } .tab.active { color:var(--text); border-bottom-color:var(--accent); }
.tab-panel { display:none; } .tab-panel.active { display:block; } .section { border:1px solid var(--border); border-radius:10px; background:var(--panel); padding:16px; margin-bottom:14px; } .field-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:11px 14px; } .field { min-width:0; } .label { color:var(--muted); text-transform:uppercase; letter-spacing:.04em; font-size:10px; font-weight:700; margin-bottom:4px; } .value { background:var(--panel2); border:1px solid #334155; padding:8px 10px; min-height:35px; border-radius:7px; font-size:13px; overflow-wrap:anywhere; } .note,.hint { color:var(--muted); font-size:11px; line-height:1.4; margin-top:5px; } .hint { margin-top:11px; } .advanced { padding:0; } .advanced summary { display:flex; justify-content:space-between; gap:10px; cursor:pointer; padding:13px 16px; color:var(--accent); font-size:13px; font-weight:700; list-style:none; } .advanced summary::-webkit-details-marker { display:none; } .advanced-body { border-top:1px solid var(--border); padding:16px; } .summary-note { color:var(--muted); font-size:11px; font-weight:500; }
.person-block { border:1px solid var(--border); border-radius:10px; padding:15px; margin-bottom:14px; } .person-block h2:first-child { border-top:0; padding-top:0; } .table-wrap { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:13px; } th,td { border-bottom:1px solid var(--border); padding:8px 10px; text-align:left; } th { color:var(--muted); font-size:11px; text-transform:uppercase; } td.num { text-align:right; font-variant-numeric:tabular-nums; }
.event-card { border:1px solid var(--border); border-radius:9px; padding:13px; margin-bottom:10px; background:var(--panel2); display:flex; gap:12px; } .event-icon { width:34px; height:34px; display:grid; place-items:center; flex:0 0 auto; border-radius:9px; background:rgba(125,211,252,.11); border:1px solid rgba(125,211,252,.2); font-size:18px; } .event-main { min-width:0; flex:1; } .event-head { display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:11px; } .event-head strong { display:block; font-size:14px; } .event-head span { color:var(--muted); font-size:12px; } .badge { border:1px solid rgba(74,222,128,.45); color:#86efac; background:rgba(34,197,94,.1); border-radius:999px; padding:3px 8px; font-size:11px; white-space:nowrap; } .badge.disabled { color:#cbd5e1; border-color:#475569; background:#1e293b; }
pre { margin:0; padding:13px; overflow:auto; white-space:pre; background:var(--panel2); border:1px solid #334155; border-radius:8px; color:#cbd5e1; font-size:12px; line-height:1.5; } @media(max-width:600px) { body { padding:12px; } .top { align-items:flex-start; } .controls { width:100%; } .scenario-select { flex:1; min-width:0; } }
"""


def build_demo_setup_page(
    *, config_path: Path, output_path: Path, slug: str,
    scenario_options: list[tuple[str, str]] | None = None,
    setup_relbase: str = "./scenarios/", back_relbase: str = "./",
) -> None:
    import tomllib

    raw_toml = config_path.read_text(encoding="utf-8")
    config = tomllib.loads(raw_toml)
    scenario = config.get("scenario", {}) or {}
    person1 = config.get("person1", {}) or {}
    person2 = config.get("person2", {}) or {}
    sim = config.get("simulation", {}) or {}
    spending = config.get("spending", {}) or {}
    taxes = config.get("taxes", {}) or {}
    rmd = taxes.get("rmd", {}) or {}
    assumptions = config.get("assumptions", {}) or {}
    withdrawal = config.get("withdrawal_policy", {}) or {}
    synthetic = config.get("synthetic_start", {}) or {}
    household_type = scenario.get("household_type", "couple" if person2 else "single")
    people = [("person1", person1)] + ([("person2", person2)] if person2 else [])

    def event_year(kind: str, key: str) -> str:
        event = _event_for(config, kind, key)
        return _text(event.get("year") if event else None)

    people_metadata = []
    for key, person in people:
        people_metadata += [
            (f"{_person_title(person, key)} Birth Date", _text(person.get("dob")), ""),
            (f"{_person_title(person, key)} Retirement Year", event_year("Retire", key), "From Retire event"),
            (f"{_person_title(person, key)} End of Plan", event_year("EndOfPlan", key), "From EndOfPlan event"),
        ]
    metadata = _section("Scenario", _fields([
        ("Plan Name", _text(scenario.get("name"), slug), ""),
        ("Description", _text(scenario.get("description")), ""),
        ("Slug", slug, ""), ("Household Type", _text(household_type), ""),
    ])) + _section("People & Plan Boundary", _fields(people_metadata))
    metadata += _section("Plan Start / End", _fields([
        ("Start Year", _text(sim.get("start_year")), ""), ("End Year", _text(sim.get("end_year")), ""),
        ("Auto-Advance to Data Date", _text(sim.get("clamp_start_year", True)), ""),
        ("Value Basis", _text(sim.get("value_basis", "nominal")), ""),
    ]))
    metadata += _section("Cash Targets", _fields([
        ("Accumulation", _money(withdrawal.get("accumulation_cash_target")), ""),
        ("Retirement", _money(withdrawal.get("retirement_cash_target")), ""),
        ("Survivor", _money(withdrawal.get("survivor_cash_target")) if person2 else "Not applicable", ""),
    ]), "Cash reserves cover expenses outside normal spending. Accumulation applies while either partner works, retirement after both retire, and survivor after one partner dies.")
    metadata += _section("Market Assumptions", _fields([
        ("Stock Return", _percent(assumptions.get("stock_return")), ""), ("Bond Return", _percent(assumptions.get("bond_return")), ""),
        ("Inflation", _percent(assumptions.get("inflation")), ""), ("Equity Allocation", _percent(assumptions.get("equity_allocation")), ""),
        ("State Tax Table", _text(taxes.get("table_set")), ""),
    ]), "These are long-run annual assumptions, not guarantees. Equity allocation is the model's stock share of the investable portfolio; the rest is bonds.")
    metadata += _section("Advanced: Withdrawal & Surplus Priorities", _fields([
        ("Accumulation Withdrawal", _text(withdrawal.get("accumulation_withdrawal_order")), ""),
        ("Retirement Withdrawal", _text(withdrawal.get("retirement_withdrawal_order")), ""),
        ("Survivor Withdrawal", _text(withdrawal.get("survivor_withdrawal_order")), ""),
        ("Accumulation Surplus", _text(withdrawal.get("accumulation_surplus_order")), ""),
        ("Retirement Surplus", _text(withdrawal.get("retirement_surplus_order")), ""),
        ("Survivor Surplus", _text(withdrawal.get("survivor_surplus_order")), ""),
    ]))
    metadata += _section("Advanced: Spending, Taxes & Assumptions", _fields([
        ("Retirement Annual Spending", _money(spending.get("retirement_annual")), ""), ("Survivor Percent", _percent(spending.get("survivor_percent_of_retirement")), ""),
        ("Survivor Annual", _money(spending.get("survivor_annual")), ""), ("Spending Basis", _text(spending.get("spending_basis")), ""),
        ("Bracket Tax Model", _text(taxes.get("enabled")), ""), ("Pre-Retirement Filing", _text(taxes.get("pre_retirement_filing_status")), ""),
        ("Retirement Filing", _text(taxes.get("retirement_filing_status")), ""), ("Survivor Filing", _text(taxes.get("survivor_filing_status")), ""),
        ("Wage Treatment", _text(taxes.get("wage_tax_treatment")), ""), ("Force RMDs", _text(rmd.get("enabled")), ""),
        ("RMD Start Age", _text(rmd.get("start_age")), ""), ("Cash Return", _percent(assumptions.get("cash_return")), ""),
        ("Real Estate Appreciation", _percent(assumptions.get("real_estate_appreciation")), ""), ("Home Sale Fee Rate", _percent(assumptions.get("real_estate_sale_fee_rate")), ""),
        ("Effective Pre-Retirement Tax", _percent(assumptions.get("effective_tax_rate_pre_retirement")), ""), ("Effective Retired Tax", _percent(assumptions.get("effective_tax_rate_post_retirement")), ""),
        ("Taxable Withdrawal Gain", _percent(assumptions.get("taxable_withdrawal_taxable_fraction")), ""), ("Traditional Withdrawal Taxable", _percent(assumptions.get("trad_ira_withdrawal_taxable_fraction")), ""),
        ("Initial Taxable Basis", _percent(assumptions.get("initial_taxable_cost_basis_fraction")), ""), ("Initial Roth Basis", _percent(assumptions.get("initial_roth_contribution_basis_fraction")), ""),
    ]), "Survivor Annual overrides Survivor Percent when both are set. The bracket tax model falls back to effective tax rates only when it is disabled or has no resolved bracket set.")
    mc = (config.get("monte_carlo", {}) or {}).get("success", {}) or {}
    metadata += _section("Advanced: Simulation & Monte Carlo", _fields([
        ("Render Modes", _text(sim.get("render_modes")), ""), ("Runs", _text(sim.get("num_runs")), ""),
        ("Seed", _text(sim.get("seed")), ""), ("Portfolio Volatility", _percent(sim.get("portfolio_return_volatility")), ""),
        ("Historical Return Sequence", _text(sim.get("historical_returns_path")), ""), ("Failure Mode", _text(mc.get("failure_mode")), ""),
        ("Minimum Spending Funded", _percent(mc.get("minimum_spending_funded_ratio")), ""), ("Allow Home Equity", _text(mc.get("allow_home_equity_for_spending")), ""),
        ("Allow Debt", _text(mc.get("allow_debt_for_spending")), ""), ("Grace Period Months", _text(mc.get("failure_grace_period_months")), ""),
        ("Custom Failure Column", _text(mc.get("custom_failure_column")), ""), ("Custom Operator", _text(mc.get("custom_failure_operator")), ""),
        ("Custom Threshold", _text(mc.get("custom_failure_threshold")), ""),
    ]), "Each selected mode renders a separate projection. The failure rule defines what counts as an unsuccessful stochastic run.")

    social_parts = []
    for key, person in people:
        ss = _event_for(config, "SocialSecurity", key)
        social_parts.append(f'<div class="person-block"><h2>{escape(_person_title(person, key))}</h2>' + _section("Claiming", _fields([
            ("Claiming Age", _text(_event_age(person, ss)), "Derived from SocialSecurity event"),
            ("Claim Year", _text(ss.get("year") if ss else None), ""),
            ("Survivor Claiming Age", _text(person.get("survivor_ss_start_age")) if person2 else "Not applicable", ""),
        ]), "Monthly benefits come from SSA.gov estimates. The Social Security event resolves its claim year to the matching age-table benefit; the flat benefit is used only when this table is empty.") + '<div class="table-wrap"><table><thead><tr><th>Claiming Age</th><th>Monthly Benefit</th></tr></thead><tbody>' + "".join(
            f'<tr><td>{escape(str(age))}</td><td class="num">{escape(_money(benefit))}</td></tr>'
            for age, benefit in sorted((person.get("social_security_benefits") or {}).items(), key=lambda item: int(item[0]))
        ) + "</tbody></table></div></div>")
    social = "".join(social_parts)

    income = "".join(_person_income(person, _person_title(person, key)) for key, person in people)
    liabilities = config.get("liabilities", []) or []
    liability_rows = "".join(
        '<tr>' + "".join(f'<td>{escape(value)}</td>' for value in [
            _text(item.get("name")), _text(item.get("type")), _percent(item.get("annual_rate")), _money(item.get("monthly_base")), _money(item.get("monthly_escrow")), _money(item.get("monthly_extra")), _money((synthetic.get("liability_balances") or {}).get(item.get("name"))),
        ]) + "</tr>" for item in liabilities
    ) or '<tr><td colspan="7">No liabilities configured.</td></tr>'
    balance_items = [(label, _money(synthetic.get(key)), "") for label, key in [
        ("Taxable", "taxable"), ("Traditional IRA / 401(k)", "trad_ira"), ("Roth", "roth"), ("Cash", "cash"),
        ("Taxable Cost Basis", "taxable_cost_basis"), ("Roth Contribution Basis", "roth_contribution_basis"),
        ("Home Value", "home_value"), ("Vehicles", "vehicles"), ("Other", "other"),
    ]]
    property_items = [(name, _money(value), "") for name, value in (synthetic.get("property_values") or {}).items()]
    accounts = _section("Data Source", _fields([("Mode", _text((config.get("data_source") or {}).get("mode")), "")]), "This sample uses manual-entry balances. Live Monarch and CSV modes have the same Setup surface but add account classification and import controls in the full app.")
    accounts += _section("Manual Starting Balances", _fields(balance_items), "Cost-basis fields are optional opening-balance seeds used to model taxable gains and Roth contribution basis.")
    accounts += _section("Property Values", _fields(property_items or [("Properties", "None configured", "")]))
    accounts += _section("Liabilities", '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Annual Rate</th><th>Monthly Payment</th><th>Escrow</th><th>Extra</th><th>Starting Balance</th></tr></thead><tbody>' + liability_rows + "</tbody></table></div>", "Loans are amortized year by year. In manual-entry scenarios, starting balances are keyed by the liability name shown above.")

    events = sorted(config.get("events", []) or [], key=lambda event: (not event.get("enabled", True), event.get("year", event.get("start_year", 9999)), event.get("type", "")))
    events_html = '<div class="readonly"><strong>Life events drive the projection timeline.</strong>These cards use the same type icons as the live Setup Panel. In the full app they can be sorted, added, edited, disabled, or deleted; this demo intentionally presents a static snapshot.</div>' + ("".join(_event_card(event) for event in events) or '<div class="section">No events configured.</div>')

    selector = ""
    if scenario_options:
        options = "".join(
            f'<option value="{escape(setup_relbase + option_slug + "/setup.html")}"{" selected" if option_slug == slug else ""}>{escape(option_name)}</option>'
            for option_slug, option_name in scenario_options
        )
        selector = f'<select class="scenario-select" onchange="window.location.href=this.value">{options}</select>'
    tabs = [("metadata", "Metadata", metadata), ("social-security", "Social Security", social), ("income", "Income & Contributions", income), ("accounts", "Accounts", accounts), ("events", "Events", events_html), ("toml", "Raw TOML", f"<section class=\"section\"><pre>{escape(raw_toml)}</pre></section>")]
    tab_buttons = "".join(f'<button class="tab{" active" if i == 0 else ""}" data-tab="{ident}">{escape(label)}</button>' for i, (ident, label, _) in enumerate(tabs))
    tab_panels = "".join(f'<div class="tab-panel{" active" if i == 0 else ""}" id="tab-{ident}">{content}</div>' for i, (ident, _, content) in enumerate(tabs))
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NWN Demo — Scenario Setup</title><style>{_STYLES}</style></head><body><main class="page"><header class="top"><h1>Scenario Setup</h1><div class="controls"><a class="link" href="{escape(back_relbase)}projection.html?scenario={escape(slug)}">Back to projection</a>{selector}</div></header><div class="readonly"><strong>Read-only public demo — a complete Setup Panel snapshot.</strong>Explore the same six configuration areas, values, helper guidance, event vocabulary, and advanced controls used by the live product. Tabs and advanced disclosures work locally in your browser; this public copy never saves, renders, or contacts an API. Clone a scenario in the full app to make changes.<div class="demo-cues"><span class="demo-cue">◉ Static sample data</span><span class="demo-cue">▣ Six setup sections</span><span class="demo-cue">⌄ Advanced details</span><span class="demo-cue">✦ No-write safe</span></div></div><nav class="tabs" aria-label="Scenario Setup sections">{tab_buttons}</nav>{tab_panels}</main><script>document.querySelectorAll('.tab').forEach(button=>button.addEventListener('click',()=>{{document.querySelectorAll('.tab,.tab-panel').forEach(item=>item.classList.remove('active'));button.classList.add('active');document.getElementById('tab-'+button.dataset.tab).classList.add('active');}}));</script></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
