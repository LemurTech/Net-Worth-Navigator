# System Patterns — Net Worth Navigator

**Last Review:** 2026-06-24

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
- **Taxable brokerage withdrawals should use tracked basis before fallback fractions.** The model now carries a yearly `taxable_cost_basis` ledger; realized-gain taxable income comes from the withdrawal's gain portion, while `taxable_withdrawal_taxable_fraction` remains only a backward-compatible way to infer the opening basis state when no explicit seed is supplied.
- **Roth balances track contribution basis separately from earnings.** Yearly outputs now distinguish `roth_contribution_basis` from `roth_earnings`, and Roth withdrawals surface basis-vs-earnings portions for auditability even though current NWN tax treatment still keeps Roth withdrawals non-taxable.
- **Gross-income wage migration is optional.** Unless NWN is explicitly re-scoped into a true household tax-return model, Monarch-style net-income wage inputs are acceptable and do not require forced gross-up migration.
- **Cash reserves are protected in two stages.** `cash_above_target` spends only dollars above the reserve; `cash_below_target` taps the reserve itself only as a last resort.
- **Specific emergency/sinking-fund expenses can override reserve protection.** `Expense` events may set `funding = "cash_reserve_first"` to let that event's deficit draw from cash below target before retirement buckets, while leaving the broader phase withdrawal order unchanged.
- **Surplus refills cash before investing.** Positive net flow first restores the active cash target, then allocates the remainder across positive non-cash investable buckets.
- **Output is always regenerated, never cached.** `python run.py` always produces a fresh chart.
- **Result consumers should prefer the normalized projection contract.** `ProjectionResult` is now the stable boundary between the simulation engine and downstream chart/sidecar layers; plain `DataFrame` callers remain supported as a compatibility wrapper.
- **Stochastic modes reuse the deterministic engine instead of forking semantics.** Monte Carlo and historical-sequence runs vary only the annual investable-return path; events, withdrawal policy, survivor behavior, taxes, and account routing stay on the same deterministic code path.
- **Stochastic display surfaces use a median path plus percentile bands.** Tables and most non-chart summaries read from the median yearly path, while charts and sidecars can also consume yearly percentile bands (`p10/p25/p50/p75/p90`) from the same run bundle.
- **Stochastic result bundles should carry yearly outcome semantics explicitly.** Beyond percentile bands, stochastic runs now expose a normalized yearly outcomes frame for success-through-year, cumulative failure, current-year trigger pressure, funded-ratio distribution, and yearly net-worth percentiles.
- **Grace-based stochastic failure modes need two layers of state.** For modes such as `spending_shortfall` and `preserve_home_equity`, yearly outputs should distinguish raw trigger pressure from actual failure after grace exhaustion; otherwise the UI overstates failure in years that are only temporarily stressed.
- **Stochastic success is scenario-configurable.** `[monte_carlo.success]` defines the failure test used by Monte Carlo and historical summaries; supported modes currently include `net_worth_below_zero`, `liquid_depletion`, `spending_shortfall`, `preserve_home_equity`, and a threshold-based `custom` comparator.
- **Secondary stochastic risk metrics should be derived from the same run bundle, not separate model paths.** Alternative probabilities such as spending shortfall, liquid depletion, net-worth-below-zero, and home-equity-required rescue are best computed by replaying the same yearly run frames through variant success settings so the UI stays semantically aligned with the configured failure rules.
- **Yearly tax calculation should flow through typed contracts in a dedicated module.** Federal/state tax-system resolution and annual tax computation now live in `src/tax_model.py` with explicit dataclasses for inputs and outputs, which makes the modeled taxable-income path easier to audit and safer to extend.
- **Recurring chart annotations can be decoupled from model recurrence.** `chart_first_occurrence_only = true` keeps repeated events active in the model and tables while suppressing later main-chart annotations for readability.
- **Portfolio funding is now explicit in the data model.** Deficit coverage records bucket-level withdrawals (`cash`, `taxable`, `trad_ira`, `roth`) so the Cash Flow tab can show how retirement spending is funded.
- **Main-chart age labels are responsive UI, not model truth.** The parenthetical ages below year ticks are shown on larger screens but suppressed on narrow viewports so the x-axis remains legible.
- **Scenario comparison is baseline-driven.** Scenario Parameters compares the active scenario against resolved default-scenario config and marks changed rows with `param-diff`; this is presentation-only and never changes model math.
- **Owner-split display labels come from config names, not internal keys.** UI labels/traces should render `person1.name`/`person2.name` in Accounts, Cash Flow, and Portfolio views while model/config internals continue to use stable keys (`person1`, `person2`).
- **Diff filtering is client-side only.** `Show only differences` toggles row/card visibility in the Scenario Parameters tab (`show-diffs-only`, `filtered-empty`) without recomputing data.
- **Assumptions and Scenario Parameters share the same diff UX contract.** Both tabs mark changed rows with `param-diff`, both can hide unchanged rows/cards client-side, and both default to diff-only mode on non-default scenarios.
- **Projection/editor scenario handoff is URL-driven.** Scenario context is preserved through explicit `?scenario=<slug>` query params for shell → editor and editor → projection links.
- **Rendered projections are now scenario-plus-mode artifacts.** One TOML scenario can emit multiple pre-rendered mode variants (`deterministic`, `historical`, `monte_carlo`) under separate output folders, and the shell manifest is responsible for routing between them.
- **Long editor renders should expose planned work before the server responds.** Since the config editor posts to a blocking backend render, the client overlay now uses a precomputed render-plan snapshot (scenario count, mode count, scenario names) to show informative staged progress copy while waiting.
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
- **Natural-language stochastic metrics belong in shared summaries.** UI labels like `Probability of Success` and `Worst-Decile Terminal Net Worth` should map directly to normalized summary keys instead of hardcoded Monte Carlo-only copy, which keeps historical and Monte Carlo modes parallel.
- **Tax audit output belongs in sidecars, not only in the HTML page.** `tax_breakdown_yearly.csv` is now the normalized per-year tax audit surface for modeled filing phase, taxable-income components, and federal/state splits.
- **Tax audit output should include explanatory subcomponents, not just totals.** The yearly tax sidecar and rendered summaries now carry deduction-adjusted federal taxable income, Social Security taxable fraction/provisional income, and state taxable income before/after deduction so audits can explain why a year taxed the way it did.
- **Optional account metadata is the preferred path for better opening basis approximations.** When a scenario needs more accurate starting basis than the household-wide fallback, `[accounts]` inline entries may supply `basis_fraction` for taxable accounts and `roth_contribution_basis_fraction` for Roth accounts; synthetic scenarios can seed direct amounts instead.
- **Keep TOML comments brief and move the handbook into the shared definitions page.** The repo now ships a static `definitions.html` reference page for grouped, simplified explanations of config parameters; scenario files should keep enough inline guidance to stay usable, but longer explanations belong in the shared page.
- **Detailed yearly audit surfaces should mirror sidecar structure.** When a modeled output already has a normalized yearly sidecar (like taxes), the projection page can expose the same shape as a dedicated yearly tab instead of overloading summary cards or cash-flow rows.
- **Static-page CSV parsing must handle quoted fields.** Pandas `to_csv()` correctly quotes fields containing commas, but a naive JS `split(',')` will split inside those quotes — corrupting column alignment for rows where quoted fields contain the delimiter character. The `events_active` column is the canonical trigger because it carries comma-separated event labels. The fix is a state-machine line parser (`parseCSVLine`) that tracks an `inQuotes` flag, strips wrapping double-quotes, and only treats commas as delimiters when outside quotes. This applies to any static HTML page that parses sidecar CSVs client-side.

---

## UI Engineering Lessons (hard-won) — 2026-06-30

### Sticky table headers & overflow containers
**`position: sticky` on `<thead>` or `<th>` fails inside any ancestor with `overflow-x: auto|scroll|hidden`.** The overflow container becomes the sticky scrollport, and since these containers only scroll horizontally, sticky never engages vertically. **Solution**: split each `<table>` into a header table (placed in a wrapper with no overflow ancestor → sticky works against the page viewport) and a body table (placed in a `.table-scroll` wrapper with `overflow-x: auto` for horizontal scroll). Both tables use `table-layout: fixed` with explicit `<colgroup>` pixel widths so column alignment is guaranteed identical — no runtime measurement or width-matching needed.

### Header rowlabel pinning
**`position: sticky; left: 0` on `<th>` is unreliably supported across browsers** when the `<th>` is inside a horizontally-scrolled container with `table-layout: fixed`. **Solution**: use JS transform in the scroll sync handler. Apply `transform: translateX(scrollX)` to the `th.rowlabel` to counter the horizontal scroll, keeping it visually pinned. Fill the gap where the cell was before translation with `boxShadow: scrollX + 'px 0 0 0 #182233'` (leftward box-shadow in the header background color) to prevent adjacent year headers from peeking through.

### Overscroll dead space
**Dead horizontal scroll space past the last column** is caused by cell content overflowing past the table boundary. Even with `table-layout: fixed` and `box-sizing: border-box`, inline elements (like `<span>` with `min-width`) can overflow cells and inflate `scrollWidth`. **Solution**: add `overflow: hidden` to `.datatable` to clip content at the table edge. Pair with wider year columns (130px, giving 110px content area after padding) to prevent number clipping.

### Dual-scroll sync for header/body
The header and body each have their own `.table-scroll` containers (`.header-scroll` and `.body-scroll`). The header scrollbar is hidden (`scrollbar-width: none`). On body scroll, sync `headerScroll.scrollLeft = bodyScroll.scrollLeft`. This avoids transform-based approaches that caused peeking/gap issues.

### Plotly layout: matching chart configurations
When two Plotly charts share identical responsive legend/margin logic, they must also share **height** and **margin**. A shorter chart (340px) with the same mobile legend position as a taller chart (420px) will have less room for the below-chart legend, causing overlap with x-axis titles. **Match height, margins, and legend config exactly** between charts that share layout behavior.

### `overflow: clip` vs `overflow: hidden`
**`overflow: hidden` creates a CSS scroll container** that traps `position: sticky` descendants — they stick to the hidden container (which can't scroll) instead of the page. **Use `overflow: clip`** to constrain width without creating a scroll container, allowing sticky to pass through to the page body.

### Event delegation for dynamic content
**Per-element event listeners can fail silently** when elements aren't in the DOM yet (e.g., `DOMContentLoaded` fires before all elements are parsed) or when elements are inside scrolled containers that interfere with events on mobile. **Use event delegation on `document`**: `document.addEventListener('click', e => { var th = e.target.closest('th[data-year]'); ... })`. This works on both desktop and mobile regardless of DOM timing.

### `data-col` attributes must be on both header and body cells
**The year-highlight feature requires `data-col` attributes on BOTH `<th>` (header) and `<td>` (body) cells.** The click handler queries `[data-col="N"]` globally to toggle the `year-highlight` class across all tables. If `git checkout` restores a pre-highlight version of `src/tables.py`, these attributes are lost. Verify with `search_files('data-col')` in the output.

### Tabulator.js — when NOT to use it
**Tabulator's `frozenColumns` and `headerVisible` features require Tabulator's own internal scroll container.** For full-height tables (all rows visible, page-level vertical scroll), Tabulator never creates its internal vertical scroll, so these features never engage. **Tabulator is a poor fit for full-height tables with page-level scrolling** — use native CSS/JS approaches instead. Tabulator is excellent for fixed-height viewport tables with internal scroll.

### Hover tooltips for `x unified` charts
**Individual trace hovertemplates in `hovermode="x unified"` should NOT include `<b>%{x}</b>`.** The shared x unified header already shows the x-axis value (the year), and repeating it on every trace entry creates visual clutter on busy charts. **Rule**: each trace's `hovertemplate` should contain only `{label}: %{y...` and nothing about the x value. This applies to all charts on the projection and shell pages that use unified hover.

### Age labels as annotations, not ticktext
**Embedding age labels in x-axis `ticktext` (`"<year><br>(age1/age2)"`) causes two problems:** (1) the hover tooltip header inherits the multi-line tick text, showing ages where they shouldn't be; (2) intermediary unlabeled ticks lack ages entirely, creating inconsistency. **Solution**: keep ticktext as just the year, and render age labels as separate Plotly `add_annotation()` calls positioned at `y=-0.085` (paper coords below the x-axis) for each labeled tick. The hover header stays clean, and the axis still shows ages.

### Axis title standoff
**`margin.b` alone does not move the x-axis title away from tick labels.** Plotly positions the axis title relative to the tick labels, not the plot edge. **Solution**: use `xaxis=dict(title=dict(text="...", standoff=N))` where `standoff` controls the gap in pixels between the lowest tick/annotation and the title text.

### Responsive annotation visibility
**When rendering decorative annotations (age labels, helper text) that should disappear on small screens, don't rely on the compact-mode breakpoint alone.** Annotations have a `visible` property that can be toggled via `Plotly.relayout(chart, updates)` using the `annotations[N].visible` key pattern. **Solution**: in the responsive JS, iterate `chart.layout.annotations`, identify target annotations by text pattern (e.g., text starts with `(` for age labels), and set `'annotations[N].visible' = !compact` using a separate wider breakpoint if needed.

### Config backup retention

**Backup deduplication and time-based retention prevent dense edit sessions from wiping out historical backups.** `_prune_backups()` uses time-based pruning (14-day cutoff) with a minimum-count floor (5 most recent always kept). Both `_backup_and_write()` and `_backup_and_write_toml()` check whether the last backup matches the current config content before creating a new file — redundant backups from no-op saves are skipped.

- Context: The old `keep=10` count-based policy meant 10 saves in a single session would overwrite all older backups. Now a burst of saves preserves history going back 14 days.
- Callers: Both the raw TOML editor endpoints and the new API endpoints (save-quick-controls, save-classification, save-synthetic-start, save-render) go through these functions.
- Retention parameters: `keep_days=14, keep_min=5` — tunable via the function signature, not a constant.
- Rollback instructions: Backups live in `output/config-backups/<slug>/config-YYYYMMDD-HHMMSS.toml`. Restore by copying the desired backup over `scenarios/<slug>.toml` (or using the raw TOML editor).
