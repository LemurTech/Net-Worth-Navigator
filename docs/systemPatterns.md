# System Patterns — Net Worth Navigator

**Last Review:** 2026-06-22

## Architectural Overview

```
Monarch MCP (live balances)
        ↓
monarch_bridge.py
  → classifies accounts: taxable / trad_ira / roth / cash
  → returns dict of {account_type: balance}
        ↓
model.py (simulation engine)
  → reads config.toml via tomllib
  → anchors year-0 balances from monarch_bridge
  → deterministic core iterates year by year from simulation_start to max(life_expectancy)
  → applies: income, contributions, growth, events, retirement transitions, SS income
  → wraps outputs in ProjectionResult: deterministic yearly path or Monte Carlo median path + percentile bands + summary metrics
        ↓
charts.py
  → receives ProjectionResult-compatible output
  → produces deterministic charts or Monte Carlo probability-band charts
  → writes self-contained output/projection.html
        ↓
run.py
  → orchestrates the above
  → copies output to /srv/web-projects/finances/
  → sets correct file permissions
```

## Patterns & Conventions

- **Config is the single source of truth for assumptions.** No rates, ages, or amounts are hardcoded in source files. Scenario-specific controls live in `config.toml`, and shared tax reference data now loads from `config/tax_tables/` through a shared config loader.
- **Events are typed.** Each `[[events]]` entry has a `type` field that determines how it impacts the model. Event types have defined property schemas.
- **Events are togglable.** Every event has `enabled = true/false`. Disabling never requires deleting the entry.
- **Monarch bridge is the live anchor.** Year 0 balances come from Monarch. All prior-year assumptions are overridden by live data on each run.
- **Withdrawal behavior is phase-aware.** The model uses `[withdrawal_policy]` to select cash reserve targets and withdrawal order separately for accumulation, retirement, and survivor phases.
- **Tax behavior is phase-aware too.** The model can now choose filing status by lifecycle phase and apply bracket-based federal ordinary-income tax from `[taxes]`, with effective-rate fallback retained for compatibility.
- **RMD behavior is configurable and tax-coupled.** Optional `taxes.rmd` settings can force annual traditional-account withdrawals from IRS life-expectancy factors, and those forced withdrawals feed both modeled cash flow and taxable-income calculations.
- **State tax treatment is Oregon-specific for now.** The model uses the official 2025 OR-40 tax table for Oregon taxable income under $50,000 and the official rate-chart formulas above that.
- **Wage tax treatment is explicit and configurable.** `taxes.wage_tax_treatment` controls whether `annual_take_home` stays cashflow-only (`net_cash`) or enters ordinary-income taxation (`taxable_wages`). Default scenario currently uses `net_cash` to match Monarch semantics.
- **Pre-retirement income growth is modeled as an approximation on wage inputs.** `annual_take_home` can grow each year from inflation plus `annual_take_home_real_raise`, and 401(k) contributions can grow from that same path plus `annual_401k_contribution_extra_increase`.
- **Pre-retirement spending has explicit precedence controls.** The model resolves spending as: `pre_retirement_spending` → `annual_savings_override` → implied `income - contributions`, with inflation indexing when `spending_basis = "real"`.
- **Retirement contributions route to explicit buckets before surplus allocation.** 401(k)/IRA contributions are deposited into `trad_ira`/`roth` (default routing with optional per-person overrides) before generic non-cash surplus distribution.
- **Bundled 401(k) plans can model traditional/Roth splits directly.** Keep `annual_401k_contribution` as the total payroll contribution and use optional `annual_401k_contribution_split.{trad_ira,roth}` to route that total proportionally; older single-bucket override behavior remains the fallback.
- **Account-level retirement owners override household fallback shares.** `[accounts]` entries may be inline tables such as `{ category = "roth", owner = "person2" }`; live/offline raw-account reclassification uses that owner metadata to seed `trad_ira` / `roth` owner balances before any `roth_share` or RMD-share fallback logic applies.
- **Bundled retirement accounts can split opening balances across buckets.** `[accounts]` inline entries may also define `opening_balance_split = { trad_ira = ..., roth = ... }`; the live/cached account balance is then apportioned across those investable buckets before the first projection year, and owner attribution is applied to each split slice.
- **Gross-income wage migration is optional.** Unless NWN is explicitly re-scoped into a true household tax-return model, Monarch-style net-income wage inputs are acceptable and do not require forced gross-up migration.
- **Cash reserves are protected in two stages.** `cash_above_target` spends only dollars above the reserve; `cash_below_target` taps the reserve itself only as a last resort.
- **Specific emergency/sinking-fund expenses can override reserve protection.** `Expense` events may set `funding = "cash_reserve_first"` to let that event's deficit draw from cash below target before retirement buckets, while leaving the broader phase withdrawal order unchanged.
- **Surplus refills cash before investing.** Positive net flow first restores the active cash target, then allocates the remainder across positive non-cash investable buckets.
- **Output is always regenerated, never cached.** `python run.py` always produces a fresh chart.
- **Result consumers should prefer the normalized projection contract.** `ProjectionResult` is now the stable boundary between the simulation engine and downstream chart/sidecar layers; plain `DataFrame` callers remain supported as a compatibility wrapper.
- **Stochastic modes reuse the deterministic engine instead of forking semantics.** Monte Carlo and historical-sequence runs vary only the annual investable-return path; events, withdrawal policy, survivor behavior, taxes, and account routing stay on the same deterministic code path.
- **Stochastic display surfaces use a median path plus percentile bands.** Tables and most non-chart summaries read from the median yearly path, while charts and sidecars can also consume yearly percentile bands (`p10/p25/p50/p75/p90`) from the same run bundle.
- **Stochastic result bundles should carry yearly outcome semantics explicitly.** Beyond percentile bands, stochastic runs now expose a normalized yearly outcomes frame for success-through-year, cumulative failure, current-year trigger pressure, funded-ratio distribution, and yearly net-worth percentiles.
- **Stochastic success is scenario-configurable.** `[monte_carlo.success]` defines the failure test used by Monte Carlo and historical summaries; supported modes currently include `net_worth_below_zero`, `liquid_depletion`, `spending_shortfall`, `preserve_home_equity`, and a threshold-based `custom` comparator.
- **Yearly tax calculation should flow through typed contracts in a dedicated module.** Federal/state tax-system resolution and annual tax computation now live in `src/tax_model.py` with explicit dataclasses for inputs and outputs, which makes the modeled taxable-income path easier to audit and safer to extend.
- **Recurring chart annotations can be decoupled from model recurrence.** `chart_first_occurrence_only = true` keeps repeated events active in the model and tables while suppressing later main-chart annotations for readability.
- **Portfolio funding is now explicit in the data model.** Deficit coverage records bucket-level withdrawals (`cash`, `taxable`, `trad_ira`, `roth`) so the Cash Flow tab can show how retirement spending is funded.
- **Main-chart age labels are responsive UI, not model truth.** The parenthetical ages below year ticks are shown on larger screens but suppressed on narrow viewports so the x-axis remains legible.
- **Scenario comparison is baseline-driven.** Scenario Parameters compares the active scenario against resolved default-scenario config and marks changed rows with `param-diff`; this is presentation-only and never changes model math.
- **Owner-split display labels come from config names, not internal keys.** UI labels/traces should render `person1.name`/`person2.name` in Accounts, Cash Flow, and Portfolio views while model/config internals continue to use stable keys (`person1`, `person2`).
- **Diff filtering is client-side only.** `Show only differences` toggles row/card visibility in the Scenario Parameters tab (`show-diffs-only`, `filtered-empty`) without recomputing data.
- **Assumptions and Scenario Parameters share the same diff UX contract.** Both tabs mark changed rows with `param-diff`, both can hide unchanged rows/cards client-side, and both default to diff-only mode on non-default scenarios.
- **Projection/editor scenario handoff is URL-driven.** Scenario context is preserved through explicit `?scenario=<slug>` query params for shell → editor and editor → projection links.
- **Shell embedded mode hides per-scenario floating toolbar controls.** UI controls needed inside the shell iframe must live in visible content regions (for example inside `.chart-wrap`), not `.page-toolbar`.
- **Main-chart event-label controls are annotation-filtering only.** Toggle logic targets vertical main-chart annotations (`textangle == -90`) and key-label detection is emoji-based (`🎉`, `🏛️`, `💀`), leaving non-event annotations (for example survivor-period note) untouched.
- **Shareable demo scenarios must use synthetic source mode.** `[data_source].mode = "synthetic"` + `[synthetic_start]` bypasses both live Monarch and cached raw accounts so sample runs do not leak personal data into sidecars.
- **Synthesized person-event labels should derive initials from display names.** Retirement/SS autogenerated labels use the configured person `name` initial, with person-key as fallback.
- **Retirement person settings are the source of truth.** Runtime config synthesizes `Retire` events from each person's `retirement_year`, while preserving any legacy event metadata overrides (label/enabled) for backward compatibility.
- **Social Security person settings are the source of truth.** Runtime config synthesizes `SocialSecurity` events from each person's `ss_start_age` and matching `social_security_benefits` bracket (with legacy `ss_monthly_benefit` fallback), while preserving any legacy event metadata overrides (label/enabled/taxability) for backward compatibility.
- **Death drives survivor mode immediately, not only after retirement.** Once one partner has passed their `EndOfPlan` year, survivor spending/policy/tax behavior starts in the next model year even if the survivor still has employment income.
- **Widow/er Social Security is simplified but now configurable.** The survivor can step up to the deceased partner's configured SS benefit once they reach `survivor_ss_start_age` (default 60), even before their own planned SS claim year.

## Event System

Events are declared in `config.toml` as `[[events]]` array entries. Each event has:

```toml
[[events]]
enabled = true
type = "Expense"           # determines property schema and model behavior
label = "Surgery drawdown"
year = 2026
amount = -6000             # negative = cash outflow
```

### Event Types and Properties

| Type | Duration | Key Properties |
|---|---|---|
| `Retire` | Permanent start | `person`, `year` — stops earned income for that person |
| `SocialSecurity` | Permanent start | `person`, `year`, `monthly_benefit` — adds SS income |
| `Expense` | Singular | `year`, `amount` — one-time cash outflow |
| `Income` | Singular or bounded | `year`, `amount`, `end_year` (optional) |
| `BuyHome` | Singular (down payment) + ongoing (mortgage) | `year`, `down_payment`, `price`, optional `property`, `mortgage_rate`, `term_years` |
| `SellHome` | Singular | `year`, `property`, optional `liability_names`, optional `sale_fee_rate`, optional `reinvest_to`, optional `reinvest_fraction` |
| `NewJob` | Permanent start | `person`, `year`, `annual_income` — replaces income |
| `CareerBreak` | Bounded | `person`, `start_year`, `end_year` — zeroes earned income |
| `Education` | Bounded | `person`, `start_year`, `end_year`, `annual_cost` |
| `Marriage` | Singular | `year` — currently informational; future: tax filing status change |
| `SpendingShift` | Singular or bounded | `year`, `mode="replace"`, optional `phase`, optional `end_year`, plus replacement spending fields |

### Model Impact Rules

- `Retire`: sets `person.income = 0` from `year` onward
- `SocialSecurity`: adds `monthly_benefit * 12` to income from `year` onward
- `Expense`: subtracts `amount` from liquid assets in `year`; optional `funding = "cash_reserve_first"` lets that expense break the cash target before Roth/traditional withdrawals if the year otherwise runs a deficit
- `Income`: adds `amount` per year within `[year, end_year]` (or just `year` if no `end_year`)
- `BuyHome`: subtracts `down_payment` in `year`; when `price` is provided it also creates/updates a tracked property (named by optional `property`, else the event label) so the purchase flows into `home_value` / `home_equity`; mortgage amortization from `BuyHome` fields is still future work
- `SellHome`: converts the named property value into cash proceeds net of sale fees and linked mortgage payoff, then removes that property from future home-value growth
- `NewJob`: replaces `person.income` from `year` onward
- `CareerBreak`: zeroes `person.income` for `[start_year, end_year]`
- `Education`: subtracts `annual_cost` per year for `[start_year, end_year]`
- `Marriage`: no model impact in V1 (placeholder for future tax filing status)
- `SpendingShift` (mode=`replace`): changes retirement/survivor baseline spending from `year` (optionally through `end_year`) without creating direct event cashflow lines

## Critical Paths

- `run.py` → `monarch_bridge.py` → `model.py` → `charts.py` → write output → set permissions
- If Monarch auth is stale: `uv run python login_setup.py` in `/opt/monarch-mcp-server`

## Key Technical Decisions

- **TOML over JSON:** Readable, commentable, stdlib. Adopted 2026-06-16.
- **Static HTML over Streamlit:** No server overhead; simpler architecture. Streamlit is V2 option if live-reload is needed. Adopted 2026-06-16.
- **Simplified tax in V1:** Flat effective-rate tax was the original approximation. As of 2026-06-17, the project has started the deeper-tax-realism path with configurable federal ordinary-income brackets and standard deductions; Social Security taxability and state tax still need more work. Adopted/updated 2026-06-17.
- **Phase-specific withdrawal policy in V1.5:** Reserve targets and withdrawal order live in `[withdrawal_policy]` instead of remaining hardcoded in `model.py`. Adopted 2026-06-17.
- **No OWL in V1:** OWL is a downstream decumulation tool. NWN must establish the strategic picture first. Adopted 2026-06-16.

## Promoted Learnings

- OWL is a decumulation optimizer (withdrawal phase only). NWN is the lifecycle trajectory model. They are complementary, not competing.
- Monarch does not provide growth rates, SS estimates, or planned events — those are always manual in config.
- **Phase-aware withdrawals need explicit config.** Once reserve targets mattered, hardcoded sequencing was too rigid; `[withdrawal_policy]` is now the durable control surface.
- **Cash target semantics are clearer than a generic reserve flag.** Distinguishing `cash_above_target` from `cash_below_target` lets the model preserve liquidity until it truly must break the reserve.
- **Emoji in Plotly annotations:** Unicode emoji render natively in annotation text in all modern browsers. No special config required. Put the emoji directly in the label string.
- **Survivor period vrect label:** do NOT use `annotation_text` on `add_vrect` — Plotly places it top-left in data space and it collides with vline annotations at the same x. Use a separate `add_annotation` with `yref="paper"` instead.
- **Main-chart event labels should stay to the right of the event line.** Vertical event annotations use a positive rightward x-shift with left anchoring so the text block sits visually to the right of the vline instead of straddling it.
- **Gantt density tuning must move bar width and chart height deliberately.** Slimmer bars alone leave airy rows; reduce the height formula to compress row pitch, then re-check the served page with a real offline render.
- **Historical mode reads annual-return windows from CSV, not bespoke code tables.** The contract expects `simulation.historical_returns_path` to point at a `year,return` CSV; rolling windows across that dataset define the historical run set, and the bundled `config/return_sequences/us_balanced_returns.csv` is intentionally an illustrative starter rather than an audited reference series.
- **Stochastic sidecars should preserve one normalized bundle shape.** `projection_yearly.csv` remains the primary display-path export, `simulation_summary.json` carries result-mode metrics, and stochastic runs add `projection_bands_yearly.csv` instead of replacing the deterministic files.
- **Stochastic UI should mirror the normalized bundle, not recompute semantics client-side.** The `Simulation` tab now reads from the same yearly outcomes frame that sidecars persist as `simulation_outcomes_yearly.csv`, so failure timing and success-rule interpretation stay aligned across page, tests, and exports.
- **Tax audit output belongs in sidecars, not only in the HTML page.** `tax_breakdown_yearly.csv` is now the normalized per-year tax audit surface for modeled filing phase, taxable-income components, and federal/state splits.
- **Tax audit output should include explanatory subcomponents, not just totals.** The yearly tax sidecar and rendered summaries now carry deduction-adjusted federal taxable income, Social Security taxable fraction/provisional income, and state taxable income before/after deduction so audits can explain why a year taxed the way it did.
- **Detailed yearly audit surfaces should mirror sidecar structure.** When a modeled output already has a normalized yearly sidecar (like taxes), the projection page can expose the same shape as a dedicated yearly tab instead of overloading summary cards or cash-flow rows.
