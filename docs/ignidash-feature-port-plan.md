# High-Level Plan — Porting Valuable ignidash Features into NWN

**Date:** 2026-06-22
**Purpose:** Define a practical, phased roadmap for bringing the highest-value ignidash ideas into Net Worth Navigator without importing ignidash's full product complexity.

## Executive Summary

The right goal is not "make NWN into ignidash."
The right goal is:

- keep NWN's core advantages
- selectively deepen the engine where ignidash is materially better
- preserve NWN's local-first TOML workflow
- avoid pulling in SaaS-style architecture that does not help household planning

The best candidates to port are:

1. Monte Carlo and historical stress-testing
2. richer account mechanics
3. contribution-rule and limit-aware modeling
4. more modular tax internals
5. better results decomposition and comparison surfaces
6. an optional machine-readable interchange layer

The wrong candidates to port are:

- auth
- Convex/database persistence
- AI chat as a first-class roadmap item
- full form-driven product UX replacing scenario TOML

## Guiding Principles

### Preserve NWN's identity

NWN should remain:

- household-first
- scenario-file-first
- Monarch-anchored
- event-rich
- static-output-friendly

### Prefer modular engine improvements

Port ideas as calculation and presentation modules, not as framework migrations.

### Keep the planning surface stable

New capabilities should extend:

- `scenarios/*.toml`
- sidecar outputs
- static projection pages

They should not require moving the repo into a database-backed app architecture.

### Separate engine depth from UX complexity

We can improve simulation fidelity and result analysis without turning NWN into a larger web application.

## Recommended Roadmap

## Phase 1 — Result Surfaces and Data Contracts

**Goal:** Prepare NWN to absorb richer simulation modes cleanly.

### Why first

Before adding Monte Carlo or deeper account mechanics, NWN needs cleaner output boundaries so new model modes do not become tangled in the current deterministic chart flow.

### Scope

- define a clearer internal simulation result contract in `src/model.py`
- standardize sidecar outputs so deterministic and future stochastic runs can share downstream tooling
- separate chart/table extractors from raw yearly model state more explicitly
- add an optional structured export format alongside TOML-driven scenarios

### Likely repo touch points

- [src/model.py](/D:/Dev/Net-Worth-Navigator/src/model.py)
- [src/charts.py](/D:/Dev/Net-Worth-Navigator/src/charts.py)
- [src/tables.py](/D:/Dev/Net-Worth-Navigator/src/tables.py)
- [src/sidecars.py](/D:/Dev/Net-Worth-Navigator/src/sidecars.py)

### Deliverables

- stable "projection result" structure documented in code and sidecars
- sidecar versioning or metadata for future multi-run outputs
- optional JSON export for one scenario run

### Success criteria

- deterministic runs still render exactly as expected
- sidecars become a reliable interface for future analysis layers
- future Monte Carlo work can plug in without rewriting chart logic from scratch

## Phase 2 — Monte Carlo and Historical Stress-Testing

**Goal:** Bring in ignidash's biggest strategic advantage without changing NWN's core scenario semantics.

### Why this is the highest-value port

This is the clearest feature gap today. NWN already answers "what happens under these assumptions?"
Monte Carlo and historical modes would add:

- "how fragile is this plan?"
- "how often does it fail under variable returns?"
- "how would this have behaved under bad historical sequences?"

### Scope

- add optional simulation modes:
  - deterministic
  - stochastic / Monte Carlo
  - historical-sequence backtest
- start with portfolio-return variation only
- keep existing event, spending, survivor, and withdrawal semantics unchanged
- generate summarized risk metrics rather than trying to render hundreds of full charts at first

### Suggested config surface

Add a scenario-level simulation block, for example:

```toml
[simulation_mode]
type = "deterministic"   # deterministic | monte_carlo | historical
num_runs = 250
seed = 12345
```

### Likely repo touch points

- [src/model.py](/D:/Dev/Net-Worth-Navigator/src/model.py)
- [src/charts.py](/D:/Dev/Net-Worth-Navigator/src/charts.py)
- [src/tables.py](/D:/Dev/Net-Worth-Navigator/src/tables.py)
- [run.py](/D:/Dev/Net-Worth-Navigator/run.py)

### Deliverables

- optional multi-run engine wrapper around the current model
- summary metrics such as:
  - success rate
  - worst percentile end net worth
  - first depletion year distribution
  - retirement-year net worth percentile bands
- a first-pass historical-sequence mode using curated return datasets

### Success criteria

- deterministic mode remains the default and unchanged
- Monte Carlo runs can be invoked per scenario without changing TOML ergonomics
- outputs stay understandable and household-focused, not abstract finance-lab output

## Phase 3 — Richer Account Mechanics

**Goal:** Port the most valuable parts of ignidash's account model while keeping NWN's household semantics intact.

### Why this matters

ignidash is ahead in:

- clearer account typing
- Roth basis handling
- RMD distinctions
- realized-gain awareness

NWN does not need full account-class architecture immediately, but it would benefit from a more explicit internal bucket model.

### Scope

- formalize account/bucket behavior more explicitly:
  - cash
  - taxable
  - traditional tax-deferred
  - Roth
  - physical assets
  - liabilities
- improve taxable withdrawal approximation surfaces
- add clearer Roth basis / contribution-basis support where feasible
- strengthen RMD and withdrawal-source accounting

### Likely repo touch points

- [src/model.py](/D:/Dev/Net-Worth-Navigator/src/model.py)
- [src/monarch_bridge.py](/D:/Dev/Net-Worth-Navigator/src/monarch_bridge.py)
- [scenarios/default.toml](/D:/Dev/Net-Worth-Navigator/scenarios/default.toml)

### Deliverables

- better bucket metadata and per-bucket rules
- clearer sidecar reporting for gains, withdrawals, and basis-sensitive behavior
- reduced ambiguity in taxable vs. Roth vs. traditional flows

### Success criteria

- funding traces become more auditable
- tax calculations have better upstream inputs
- the scenario surface stays understandable to a human editor

## Phase 4 — Contribution Rules and Limit-Aware Planning

**Goal:** Import the strongest parts of ignidash's contribution-rule thinking without overwhelming NWN's simpler planning model.

### Why this matters

NWN already supports explicit retirement contribution routing, but it still lacks richer contribution-planning semantics such as:

- ordered rule evaluation
- better employer-match behavior
- IRS-cap awareness
- more explicit overflow behavior

### Scope

- add optional contribution-rule blocks for advanced scenarios
- support ordered contribution destinations
- optionally model:
  - employer match
  - shared 401(k)/Roth 401(k) limits
  - IRA combined limits
  - HSA limits if added later
- preserve current simple per-person annual fields as the default path

### Suggested shape

Keep the current simple fields for most users, then allow advanced override blocks when needed.

### Likely repo touch points

- [src/model.py](/D:/Dev/Net-Worth-Navigator/src/model.py)
- [src/tables.py](/D:/Dev/Net-Worth-Navigator/src/tables.py)
- [scenarios/default.toml](/D:/Dev/Net-Worth-Navigator/scenarios/default.toml)

### Deliverables

- advanced contribution-order semantics
- optional employer-match modeling
- warnings or notes when configured contributions exceed modeled limits

### Success criteria

- current scenarios do not need to be rewritten
- advanced users can opt into richer rules
- contribution logic becomes less ad hoc and more auditable

## Phase 5 — Tax Engine Refactor Before Tax Expansion

**Goal:** Make NWN's tax system easier to extend before adding much more tax realism.

### Why this should precede deeper tax expansion

ignidash's main tax advantage is not just breadth. It also has better tax modularity.
NWN should improve structure before piling on more tax features.

### Scope

- separate tax-input gathering from tax calculation
- separate federal ordinary-income logic from state logic
- separate withdrawal tax sourcing from filing-status logic
- make tax outputs richer and easier to inspect in tables and sidecars

### Likely repo touch points

- [src/model.py](/D:/Dev/Net-Worth-Navigator/src/model.py)
- [src/config_loader.py](/D:/Dev/Net-Worth-Navigator/src/config_loader.py)
- [src/tables.py](/D:/Dev/Net-Worth-Navigator/src/tables.py)

### Deliverables

- clearer internal tax modules or helper layers
- richer sidecar tax breakdowns
- simpler insertion points for future features like:
  - NIIT
  - better dividend treatment
  - pension handling
  - IRMAA
  - property tax

### Success criteria

- no regression in current tax behavior
- future tax work becomes smaller and safer
- model audits become easier to explain from outputs

## Phase 6 — Comparison and Analysis UX

**Goal:** Port some of ignidash's best analysis affordances into NWN's static-output world.

### Why this matters

ignidash is stronger at helping a user inspect results from multiple angles.
NWN can borrow that strength without abandoning static HTML.

### Scope

- add scenario-to-scenario comparison views
- improve KPI and table drill-downs
- add percentile/range views for stochastic runs
- optionally add a compact "analysis mode" page separate from the main projection page

### Likely repo touch points

- [src/charts.py](/D:/Dev/Net-Worth-Navigator/src/charts.py)
- [src/tables.py](/D:/Dev/Net-Worth-Navigator/src/tables.py)
- [src/scenario_shell.py](/D:/Dev/Net-Worth-Navigator/src/scenario_shell.py)

### Deliverables

- better side-by-side scenario comparison
- richer chart modes derived from one render artifact set
- clearer navigation for deterministic vs. stochastic vs. historical outputs

### Success criteria

- analysis becomes deeper without requiring a new app backend
- the shell page remains fast and legible
- complex outputs stay understandable on the household planning page

## Optional Phase 7 — Interchange and External Adapter Layer

**Goal:** Make NWN more portable without compromising TOML-first operation.

### Why this is optional

This is useful if you want bridges, converters, or side-analysis tools later, but it is not the highest immediate value.

### Scope

- formal JSON export schema for scenarios and results
- optional import/export helpers
- reduced-subset export that could feed ignidash or other tools

### Deliverables

- documented NWN interchange format
- converter-friendly outputs
- lower-friction experimentation with external analysis tools

## Prioritization Recommendation

### Recommended order

1. Phase 1 — Result surfaces and data contracts
2. Phase 2 — Monte Carlo and historical stress-testing
3. Phase 5 — Tax refactor before deeper tax expansion
4. Phase 3 — Richer account mechanics
5. Phase 4 — Contribution rules and limit-aware planning
6. Phase 6 — Comparison and analysis UX
7. Phase 7 — Interchange layer

### Why this order

- Monte Carlo is the highest user-visible gain
- it depends on cleaner result plumbing
- deeper taxes and account mechanics benefit from structural cleanup first
- contribution rules are valuable, but less urgent than risk analysis

## What Not to Do

### Do not port the ignidash product stack

Avoid:

- database persistence as the main scenario store
- auth and user-account systems
- app-style form replacement of TOML by default
- AI chat before the engine/result layers mature

### Do not overfit NWN to single-person retirement-product assumptions

Any ported feature must respect:

- two-person household semantics
- survivor mode
- event-first planning
- reserve semantics

If a feature conflicts with those, NWN should adapt the idea rather than copying the implementation shape.

## First Concrete Slice

If we start now, the best first slice is:

### Slice A — Stochastic-readiness groundwork

- formalize result payload shape
- extend sidecars for future multi-run support
- identify where the current deterministic engine can be wrapped instead of rewritten
- design summary metrics for Monte Carlo success/failure outputs

### Slice B — First Monte Carlo MVP

- add seeded Monte Carlo portfolio-return variation
- run multiple deterministic-style yearly projections under varying return sequences
- emit percentile summary tables and one chart with probability bands

That would give NWN the strongest immediate lift from ignidash while preserving the current architecture and planning workflow.
