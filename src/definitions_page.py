"""Build the static definitions/help page for Net Worth Navigator."""

from __future__ import annotations

from html import escape
from pathlib import Path


DEFINITION_SECTIONS: list[dict[str, object]] = [
    {
        "title": "Scenario And Display",
        "intro": "High-level metadata that names the scenario and controls how it appears in the selector and chart chrome.",
        "items": [
            {
                "key": "[scenario].name",
                "summary": "Human-friendly scenario name shown in the shell and editor.",
            },
            {
                "key": "[scenario].slug",
                "summary": "Stable file-safe id used in URLs, output folders, and editor routing.",
            },
            {
                "key": "[scenario].description",
                "summary": "Short plain-English description of what is different about the scenario.",
            },
            {
                "key": "[scenario].is_default",
                "summary": "Marks the scenario the public selector should open first.",
                "options": ["`true` = default starting scenario", "`false` = alternate scenario"],
            },
            {
                "key": "[display].projection_title",
                "summary": "Subtitle text shown in the projection page header/chart title area.",
            },
        ],
    },
    {
        "title": "Data Source And Synthetic Start",
        "intro": "Controls where year-0 balances come from. Most real household scenarios use Monarch data; demo/share-safe scenarios use synthetic balances.",
        "items": [
            {
                "key": "[data_source].mode",
                "summary": "Choose whether the scenario starts from live/cached Monarch balances or explicit synthetic amounts.",
                "options": ["`monarch` = live or cached classified account balances", "`synthetic` = balances come from `[synthetic_start]`"],
            },
            {
                "key": "[synthetic_start].taxable / trad_ira / roth / cash",
                "summary": "Starting investable balances for synthetic scenarios.",
            },
            {
                "key": "[synthetic_start].home_value / vehicles / other",
                "summary": "Starting non-investable rollups for synthetic scenarios.",
            },
            {
                "key": "[synthetic_start.property_values]",
                "summary": "Optional named real-estate balances so future `SellHome` events can target a specific property.",
            },
            {
                "key": "[synthetic_start.liability_balances]",
                "summary": "Optional named starting liability balances keyed to `[[liabilities]].name`.",
            },
            {
                "key": "[synthetic_start.retirement_owner_balances]",
                "summary": "Optional owner split for starting traditional/Roth balances when one combined number is not good enough.",
            },
            {
                "key": "[synthetic_start].taxable_cost_basis",
                "summary": "Optional explicit starting cost basis inside the synthetic taxable account.",
            },
            {
                "key": "[synthetic_start].roth_contribution_basis",
                "summary": "Optional explicit starting Roth contribution basis, separate from Roth earnings.",
            },
        ],
    },
    {
        "title": "Simulation",
        "intro": "Controls the time range and which engine mode is rendered.",
        "items": [
            {
                "key": "[simulation].start_year / end_year",
                "summary": "Projection window used by the yearly model.",
            },
            {
                "key": "[simulation].clamp_start_year",
                "summary": "When true and balance data has a known as-of date newer than start_year, the projection start is auto-adjusted forward to match the data year. Set to false to disable.",
                "options": ["`true` (default)", "`false`"],
            },
            {
                "key": "[simulation].real_dollar_basis",
                "summary": "When true, all chart and table figures are shown in start-year purchasing power (deflated by cumulative inflation). False (default) shows nominal future-year values.",
                "options": ["`false` (default) — nominal dollars", "`true` — deflated to start-year dollars"],
            },
            {
                "key": "[simulation].render_modes",
                "summary": "Which pre-rendered modes the scenario shell should build and expose.",
                "options": ["`deterministic`", "`historical`", "`monte_carlo`"],
            },
            {
                "key": "[simulation].mode",
                "summary": "Single-run compatibility setting; the renderer overrides this per mode when batch rendering multiple outputs.",
                "options": ["`deterministic` = one straight-line run", "`historical` = rolling historical return windows", "`monte_carlo` = randomized annual return paths"],
            },
            {
                "key": "[simulation].num_runs",
                "summary": "Number of Monte Carlo runs to simulate.",
            },
            {
                "key": "[simulation].seed",
                "summary": "Optional random seed so Monte Carlo results are repeatable.",
            },
            {
                "key": "[simulation].portfolio_return_volatility",
                "summary": "Annual return variability used by Monte Carlo around the blended stock/bond return.",
            },
            {
                "key": "[simulation].historical_returns_path",
                "summary": "CSV file with `year,return` columns used to create rolling historical return sequences.",
            },
        ],
    },
    {
        "title": "Stochastic Success Rules",
        "intro": "Used by both Monte Carlo and historical modes to decide whether a run counts as a success or failure.",
        "items": [
            {
                "key": "[monte_carlo.success].failure_mode",
                "summary": "Main failure rule for stochastic reporting.",
                "options": [
                    "`net_worth_below_zero` = fail once total net worth drops below zero",
                    "`liquid_depletion` = fail when investable liquid assets are exhausted",
                    "`spending_shortfall` = fail when required spending is not fully funded",
                    "`preserve_home_equity` = fail when the plan needs to consume protected home equity",
                    "`custom` = compare one output column against a threshold",
                ],
            },
            {
                "key": "[monte_carlo.success].minimum_spending_funded_ratio",
                "summary": "Funding threshold used by `spending_shortfall` mode. `1.0` means fully funded.",
            },
            {
                "key": "[monte_carlo.success].allow_home_equity_for_spending",
                "summary": "Whether home equity can count as available funding in success calculations.",
            },
            {
                "key": "[monte_carlo.success].allow_debt_for_spending",
                "summary": "Whether going negative / borrowing can still count as funded in success calculations.",
            },
            {
                "key": "[monte_carlo.success].failure_grace_period_months",
                "summary": "Lets a run experience temporary pressure before it becomes a true failure.",
            },
            {
                "key": "[monte_carlo.success].custom_failure_column / operator / threshold",
                "summary": "Advanced custom comparator used only when `failure_mode = \"custom\"`.",
            },
        ],
    },
    {
        "title": "People",
        "intro": "Each household member gets an independent profile. `person1` and `person2` are the canonical keys used across the app.",
        "items": [
            {
                "key": "[personX].name",
                "summary": "Display name used in tables, legends, and synthesized event labels.",
            },
            {
                "key": "[personX].dob",
                "summary": "Date of birth used for age labels, end-of-plan timing, and RMD age checks.",
            },
            {
                "key": "[personX].life_expectancy",
                "summary": "Modeled terminal age, not a prediction.",
            },
            {
                "key": "[personX].retirement_year",
                "summary": "First model year in which wage income stops for that person.",
            },
            {
                "key": "[personX].annual_take_home",
                "summary": "Annual wage cashflow input. Usually treated as net cash unless taxes are switched to `taxable_wages` mode.",
            },
            {
                "key": "[personX].annual_take_home_is_net_of_retirement_contributions",
                "summary": "Use `true` when 401(k)/similar payroll contributions are already excluded from take-home pay.",
            },
            {
                "key": "[personX].annual_take_home_real_raise",
                "summary": "Real wage growth above inflation.",
            },
            {
                "key": "[personX].annual_401k_contribution",
                "summary": "Total annual workplace retirement contribution input for that person.",
            },
            {
                "key": "[personX].annual_401k_contribution_extra_increase",
                "summary": "Additional annual growth applied to the 401(k) contribution path beyond the wage-growth path.",
            },
            {
                "key": "[personX].contribution_method",
                "summary": "401(k) contribution method: `flat` (default) or `percent_of_gross`. In `percent_of_gross` mode, contributions are computed from gross_income × retirement_contribution_percent.",
            },
            {
                "key": "[personX].gross_income",
                "summary": "Gross annual income used for percentage-based 401(k) contribution computation. Only used when `contribution_method = \"percent_of_gross\"`.",
            },
            {
                "key": "[personX].gross_income_annual_increase_percent",
                "summary": "Combined annual gross income increase (COLA + performance + merit) as a decimal. Example: 0.05 = 5% annual increase.",
            },
            {
                "key": "[personX].retirement_contribution_percent",
                "summary": "401(k) contribution as a percentage of gross income. Example: 0.12 = 12% of gross.",
            },
            {
                "key": "[personX].retirement_contribution_annual_increase_percent",
                "summary": "Annual percentage-point increase in 401(k) contribution rate (auto-escalation). Example: 0.02 = increase contribution rate by 2 percentage points each year.",
            },
            {
                "key": "[personX].retirement_contribution_max_percent",
                "summary": "Maximum contribution percentage cap. The contribution rate stops escalating once it reaches this value. Example: 0.18 = never exceed 18% of gross income.",
            },
            {
                "key": "[personX].annual_401k_employer_match",
                "summary": "Flat annual employer 401(k) match dollar amount. Used when `annual_401k_employer_match_mode = \"flat\"` (default).",
            },
            {
                "key": "[personX].annual_401k_employer_match_mode",
                "summary": "Employer match mode: `flat` (default) or `percent_of_gross`. In percent mode, the employer matches `match_rate` of employee contributions up to `match_max_percent` of gross income.",
            },
            {
                "key": "[personX].annual_401k_employer_match_rate",
                "summary": "Percentage of employee contribution the employer matches. Example: 0.50 = 50 cents per dollar contributed.",
            },
            {
                "key": "[personX].annual_401k_employer_match_max_percent",
                "summary": "Maximum percentage of gross income the employer will match. Example: 0.06 = match applies only to the first 6% of salary contributed.",
            },
            {
                "key": "[personX].annual_ira_contribution",
                "summary": "Direct IRA contribution modeled as a cash outflow plus deposit into `trad_ira` or `roth`.",
            },
            {
                "key": "[personX].annual_401k_contribution_bucket / annual_ira_contribution_bucket",
                "summary": "Optional simple routing override for retirement contributions.",
                "options": ["`trad_ira`", "`roth`"],
            },
            {
                "key": "[personX].annual_401k_contribution_split",
                "summary": "Optional proportional split for one bundled workplace plan spanning traditional and Roth dollars.",
            },
            {
                "key": "[personX].rmd_trad_ira_share",
                "summary": "Share of the household traditional balance attributed to that person for RMD math.",
            },
            {
                "key": "[personX].ss_start_age",
                "summary": "Age when that person starts Social Security in the synthesized runtime config.",
            },
            {
                "key": "[personX].social_security_benefits",
                "summary": "Age-to-monthly-benefit lookup used by the runtime Social Security event builder.",
            },
        ],
    },
    {
        "title": "Spending",
        "intro": "Baseline living-expense controls outside of one-off events.",
        "items": [
            {
                "key": "[spending].retirement_annual",
                "summary": "Household retirement spending target.",
            },
            {
                "key": "[spending].survivor_percent_of_retirement",
                "summary": "Survivor spending target expressed as a share of the couple retirement target.",
            },
            {
                "key": "[spending].spending_basis",
                "summary": "How to interpret the retirement/spending targets over time.",
                "options": ["`real` = today’s dollars, then CPI-adjusted", "`nominal` = fixed nominal amounts"],
            },
            {
                "key": "[spending].pre_retirement_spending",
                "summary": "Optional explicit pre-retirement annual spending target. Highest-precedence control.",
            },
            {
                "key": "[spending].annual_savings_override",
                "summary": "Optional explicit pre-retirement savings target when you want to derive spending from savings rather than the default implied math.",
            },
        ],
    },
    {
        "title": "Withdrawal Policy",
        "intro": "Controls how NWN preserves cash reserves, covers deficits, and routes surplus cash in each life phase.",
        "items": [
            {
                "key": "[withdrawal_policy].*_cash_target",
                "summary": "Target cash reserve for `accumulation`, `retirement`, and `survivor` phases.",
            },
            {
                "key": "[withdrawal_policy].*_withdrawal_order",
                "summary": "Bucket order used to cover deficits in each phase.",
                "options": [
                    "`cash_above_target` = only spend cash above the reserve floor",
                    "`taxable` = withdraw from taxable brokerage",
                    "`trad_ira` = withdraw from pre-tax retirement assets",
                    "`roth` = withdraw from Roth assets",
                    "`cash_below_target` = break the reserve itself only as a last resort",
                ],
            },
            {
                "key": "[withdrawal_policy].*_surplus_order",
                "summary": "Where extra cash should be reinvested after the reserve is full.",
                "options": ["`taxable`", "`roth`", "`trad_ira`"],
            },
        ],
    },
    {
        "title": "Taxes And RMD",
        "intro": "Ordinary-income-focused household tax controls plus optional Required Minimum Distribution settings.",
        "items": [
            {
                "key": "[taxes].enabled",
                "summary": "Turns the bracket-based tax engine on or off.",
            },
            {
                "key": "[taxes].table_set",
                "summary": "Shared tax reference dataset loaded from `config/tax_tables/`.",
            },
            {
                "key": "[taxes].*_filing_status",
                "summary": "Federal/state filing status to use in `pre_retirement`, `retirement`, and `survivor` phases.",
                "options": ["`single`", "`married_joint`", "`head_of_household` when supported by the table set"],
            },
            {
                "key": "[taxes].wage_tax_treatment",
                "summary": "How wage income should enter the tax model.",
                "options": ["`net_cash` = wages stay as after-tax cashflow only", "`taxable_wages` = wages are treated as taxable income"],
            },
            {
                "key": "[taxes.rmd].enabled",
                "summary": "Force RMD withdrawals from traditional retirement balances when age thresholds are met.",
            },
            {
                "key": "[taxes.rmd].start_age",
                "summary": "Starting age for RMD enforcement.",
            },
            {
                "key": "[taxes.rmd.factors]",
                "summary": "Optional age-to-divisor overrides for the lifetime table.",
            },
        ],
    },
    {
        "title": "Market And Economic Assumptions",
        "intro": "Return, inflation, and simplified fallback-tax assumptions used by the yearly engine.",
        "items": [
            {
                "key": "[assumptions].stock_return / bond_return / equity_allocation",
                "summary": "Defines the blended investable return path used in deterministic mode and as the center of stochastic mode.",
            },
            {
                "key": "[assumptions].inflation",
                "summary": "CPI assumption used for real-dollar spending growth and some other inflation-linked paths.",
            },
            {
                "key": "[assumptions].cash_return",
                "summary": "Separate growth rate for cash balances so reserves do not inherit the stock/bond blend.",
            },
            {
                "key": "[assumptions].real_estate_appreciation",
                "summary": "Home/property appreciation assumption, independent from CPI.",
            },
            {
                "key": "[assumptions].real_estate_sale_fee_rate",
                "summary": "Default transaction-cost assumption for `SellHome` events.",
            },
            {
                "key": "[assumptions].effective_tax_rate_pre_retirement / effective_tax_rate_post_retirement",
                "summary": "Legacy fallback tax rates used only when the bracket-based tax engine is disabled/incomplete.",
            },
            {
                "key": "[assumptions].taxable_withdrawal_taxable_fraction",
                "summary": "Legacy fallback only. If no explicit taxable basis seed is given, this implies the starting cost-basis share of the taxable account.",
            },
            {
                "key": "[assumptions].trad_ira_withdrawal_taxable_fraction",
                "summary": "Taxable share of traditional-account withdrawals. Usually `1.0`.",
            },
            {
                "key": "[assumptions].initial_taxable_cost_basis_fraction",
                "summary": "Optional direct opening assumption for how much of the taxable account is cost basis.",
            },
            {
                "key": "[assumptions].initial_roth_contribution_basis_fraction",
                "summary": "Optional opening assumption for how much of the Roth balance is contribution basis rather than earnings.",
            },
        ],
    },
    {
        "title": "Accounts Metadata",
        "intro": "Maps live Monarch account names into NWN’s simplified model buckets and lets you add better opening metadata where needed.",
        "items": [
            {
                "key": "[accounts]",
                "summary": "Main account-classification block keyed by exact Monarch account name.",
            },
            {
                "key": "Category strings",
                "summary": "Simple classification for one account.",
                "options": ["`taxable`", "`trad_ira`", "`roth`", "`cash`", "`real_estate`", "`vehicle`", "`liability`", "`ignore`"],
            },
            {
                "key": "{ category = \"...\", owner = \"...\" }",
                "summary": "Inline-table form used when you need owner attribution or extra metadata.",
                "options": ["`owner = \"person1\"`", "`owner = \"person2\"`"],
            },
            {
                "key": "opening_balance_split",
                "summary": "Splits one live account across multiple investable buckets at year 0.",
            },
            {
                "key": "basis_fraction",
                "summary": "Optional taxable-account metadata: share of the starting taxable balance treated as cost basis.",
            },
            {
                "key": "roth_contribution_basis_fraction",
                "summary": "Optional Roth-account metadata: share of the starting Roth balance treated as contribution basis.",
            },
            {
                "key": "[accounts].disabled",
                "summary": "Exact account names to exclude without deleting the underlying category mapping.",
            },
        ],
    },
    {
        "title": "Events",
        "intro": "Discrete scenario changes. Each `[[events]]` item has `enabled`, `type`, `label`, and then type-specific fields.",
        "items": [
            {
                "key": "Common event fields",
                "summary": "Use `enabled = true/false` to toggle, keep `label` human-friendly, and prefer exact years over prose.",
            },
            {
                "key": "Retire",
                "summary": "Stops a person’s wage income from its `year` onward.",
                "options": ["Fields: `person`, `year`"],
            },
            {
                "key": "SocialSecurity",
                "summary": "Adds Social Security income for a person from its `year` onward.",
                "options": ["Fields: `person`, `year`, `monthly_benefit`", "Optional: `taxable`, `taxable_fraction`"],
            },
            {
                "key": "Expense",
                "summary": "One-time outflow.",
                "options": [
                    "Fields: `year`, `amount` (usually negative)",
                    "`expense_kind = \"mandatory\" | \"discretionary\"`",
                    "`funding = \"cash_reserve_first\"` to let this event break reserve protection first",
                ],
            },
            {
                "key": "Income",
                "summary": "One-time or bounded extra income stream.",
                "options": ["Fields: `year`, `amount`", "Optional: `end_year`, `taxable`, `taxable_fraction`"],
            },
            {
                "key": "BuyHome",
                "summary": "Uses cash for a purchase and, when `price` is supplied, creates/updates a tracked property.",
                "options": ["Fields: `year`, `down_payment`, `price`", "Optional: `property`, `mortgage_rate`, `term_years`"],
            },
            {
                "key": "SellHome",
                "summary": "Converts a named property into net cash proceeds and can optionally reinvest some or all of it.",
                "options": ["Fields: `year`, `property`", "Optional: `liability_names`, `sale_fee_rate`, `reinvest_to`, `reinvest_fraction`"],
            },
            {
                "key": "NewJob / CareerBreak / Education / Marriage / SpendingShift",
                "summary": "Additional event types for job changes, pauses, tuition, informational life events, and baseline-spending regime changes.",
            },
            {
                "key": "ContributionChange",
                "summary": "Override one or more per-person contribution amounts starting from a given year. "
                           "Useful for modelling a mid-scenario step-up or step-down in 401(k) or IRA contributions "
                           "(e.g. restoring full 401(k) contributions after an early mortgage payoff).",
                "options": [
                    "Required: `year`, `person` (`person1` or `person2`)",
                    "Optional: `annual_401k_contribution` — new absolute dollar amount",
                    "Optional: `annual_ira_contribution` — new absolute dollar amount",
                    "Optional: `annual_401k_employer_match` — new employer match dollar amount (flat mode)",
                    "Optional: `annual_401k_contribution_delta` — relative dollar change (+/-) to 401(k) contribution",
                    "Optional: `annual_ira_contribution_delta` — relative dollar change (+/-) to IRA contribution",
                    "Optional: `annual_401k_employer_match_delta` — relative dollar change (+/-) to employer match",
                    "Optional: `annual_401k_employer_match_mode` — \"flat\" or \"percent_of_gross\"",
                    "Optional: `annual_401k_employer_match_rate` — match rate as decimal (e.g. 0.50 = 50% match)",
                    "Optional: `annual_401k_employer_match_max_percent` — max salary % matched (e.g. 0.06)",
                    "Optional: `gross_income` — new gross income for percentage-based contributions",
                    "Optional: `gross_income_annual_increase_percent` — new gross income increase rate",
                    "Optional: `retirement_contribution_percent` — new contribution percentage",
                    "Optional: `retirement_contribution_annual_increase_percent` — new escalation rate",
                    "Optional: `retirement_contribution_max_percent` — new percentage cap",
                    "Multiple events for the same person are applied in year order; later years win",
                ],
            },
            {
                "key": "Recurring controls",
                "summary": "Repeat a compatible event without copying it many times.",
                "options": ["`repeat_every_years`", "`repeat_until_year`", "`repeat_count`", "`chart_first_occurrence_only` for decluttering labels"],
            },
        ],
    },
]


def build_definitions_page_html(
    *,
    editor_url: str = "/finances/config/setup",
    projection_url: str = "/finances/projection.html",
) -> str:
    nav_links = "".join(
        f"<a href='#{_slugify(section['title'])}'>{escape(str(section['title']))}</a>"
        for section in DEFINITION_SECTIONS
    )
    sections_html = "".join(_render_section(section) for section in DEFINITION_SECTIONS)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Net Worth Navigator Definitions</title>
  <style>
    :root {{
      --bg: #08111d;
      --panel: rgba(15, 23, 37, 0.92);
      --panel-2: #111827;
      --text: #e5edf7;
      --muted: #9fb2c8;
      --border: #243142;
      --accent: #7dd3fc;
      --accent-2: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(14,165,233,.16), transparent 30%),
        linear-gradient(180deg, #08111d, #0b1220 48%, #08111d);
      line-height: 1.5;
    }}
    .page {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .hero {{
      display: grid;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: .08em;
      font-size: 12px;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(32px, 5vw, 54px);
      line-height: 0.98;
      letter-spacing: -0.04em;
    }}
    .lead {{
      margin: 0;
      max-width: 860px;
      color: var(--muted);
      font-size: 16px;
    }}
    .hero-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--border);
      text-decoration: none;
      color: var(--text);
      background: var(--panel);
      font-size: 14px;
      font-weight: 600;
    }}
    .btn.primary {{
      background: linear-gradient(180deg, #1fb6ff, #0b8fd0);
      border-color: rgba(125, 211, 252, 0.8);
      color: #06111d;
    }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 12px 0 16px;
      margin-bottom: 12px;
      background: linear-gradient(180deg, rgba(8,17,29,.98), rgba(8,17,29,.88), rgba(8,17,29,0));
      backdrop-filter: blur(6px);
    }}
    .nav a {{
      display: inline-flex;
      align-items: center;
      padding: 7px 11px;
      border-radius: 999px;
      border: 1px solid rgba(125, 211, 252, 0.12);
      background: rgba(17,24,39,0.8);
      color: var(--muted);
      text-decoration: none;
      font-size: 12px;
      white-space: nowrap;
    }}
    .nav a:hover {{ color: var(--text); border-color: var(--accent); }}
    .section {{
      margin-bottom: 18px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: 0 18px 40px rgba(0,0,0,.24);
    }}
    .section-head {{
      padding: 18px 20px 12px;
      border-bottom: 1px solid var(--border);
      background:
        linear-gradient(180deg, rgba(17,24,39,0.98), rgba(17,24,39,0.78)),
        radial-gradient(circle at top right, rgba(125,211,252,.18), transparent 28%);
    }}
    .section-head h2 {{
      margin: 0 0 6px;
      font-size: 24px;
      letter-spacing: -0.03em;
    }}
    .section-head p {{
      margin: 0;
      color: var(--muted);
      max-width: 860px;
    }}
    .defs {{
      display: grid;
      gap: 0;
    }}
    .def {{
      display: grid;
      grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
      gap: 14px;
      padding: 16px 20px;
      border-top: 1px solid rgba(36,49,66,.7);
    }}
    .def:first-child {{ border-top: none; }}
    .term {{
      color: #d8ecff;
      font-weight: 700;
      font-size: 14px;
      line-height: 1.35;
    }}
    .term code {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 7px;
      background: #0b1220;
      color: #d8ecff;
      overflow-wrap: anywhere;
    }}
    .detail p {{
      margin: 0;
      color: var(--text);
    }}
    .options {{
      margin: 10px 0 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 6px;
    }}
    .options li {{
      padding: 9px 10px;
      border-radius: 10px;
      background: rgba(8,17,29,0.65);
      color: #d3dfed;
      border: 1px solid rgba(36,49,66,.55);
      font-size: 13px;
    }}
    .options code {{
      color: #d8ecff;
      background: rgba(17,24,39,0.9);
      padding: 1px 5px;
      border-radius: 5px;
    }}
    .foot {{
      margin-top: 24px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 820px) {{
      .def {{
        grid-template-columns: 1fr;
      }}
      .page {{
        padding: 22px 14px 36px;
      }}
      .section-head {{
        padding: 16px 16px 12px;
      }}
      .def {{
        padding: 14px 16px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="eyebrow">Net Worth Navigator Reference</div>
      <h1>Definitions And Options</h1>
      <p class="lead">This page is the plain-English companion to the scenario TOML files. It groups parameters by purpose, explains what each one is for, and calls out the most important option values without forcing the config files themselves to become a handbook.</p>
      <div class="hero-actions">
        <a class="btn primary" href="{escape(projection_url)}" target="_blank" rel="noreferrer">Open Projection</a>
        <a class="btn" href="{escape(editor_url)}" target="_blank" rel="noreferrer">Open Config Editor</a>
      </div>
    </section>
    <nav class="nav">{nav_links}</nav>
    {sections_html}
    <div class="foot">Keep the TOML concise. Put durable explanation here, then link to this page from the shell, editor, and scenario pages.</div>
  </div>
</body>
</html>"""


def write_definitions_page(
    output_path: Path,
    *,
    editor_url: str = "/finances/config/setup",
    projection_url: str = "/finances/projection.html",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_definitions_page_html(
            editor_url=editor_url,
            projection_url=projection_url,
        ),
        encoding="utf-8",
    )


def _render_section(section: dict[str, object]) -> str:
    title = escape(str(section["title"]))
    intro = escape(str(section.get("intro", "")))
    items = "".join(_render_item(item) for item in section.get("items", []))
    return (
        f"<section class='section' id='{_slugify(str(section['title']))}'>"
        f"<div class='section-head'><h2>{title}</h2><p>{intro}</p></div>"
        f"<div class='defs'>{items}</div></section>"
    )


def _render_item(item: dict[str, object]) -> str:
    term = escape(str(item["key"]))
    summary = escape(str(item["summary"]))
    options = item.get("options") or []
    options_html = ""
    if options:
        options_html = "<ul class='options'>" + "".join(
            f"<li>{_inline_code_markup(str(option))}</li>" for option in options
        ) + "</ul>"
    return (
        "<div class='def'>"
        f"<div class='term'><code>{term}</code></div>"
        f"<div class='detail'><p>{summary}</p>{options_html}</div>"
        "</div>"
    )


def _slugify(text: str) -> str:
    return (
        text.lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "-")
    )


def _inline_code_markup(text: str) -> str:
    escaped = escape(text)
    parts = escaped.split("`")
    if len(parts) == 1:
        return escaped
    rendered: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            rendered.append(f"<code>{part}</code>")
        else:
            rendered.append(part)
    return "".join(rendered)
