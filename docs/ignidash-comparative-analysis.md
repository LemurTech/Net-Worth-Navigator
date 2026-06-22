# Comparative Analysis — Net Worth Navigator vs. ignidash

**Date:** 2026-06-22
**Scope:** Compare `D:\Dev\Net-Worth-Navigator` (NWN) with `D:\Dev\ignidash`, assess where each product shines, and evaluate feasibility of Monarch-style balance sync, scenario migration, and cross-pollination.

## Executive Summary

Net Worth Navigator is stronger today for your actual household planning problem.
It is simpler, more direct, more local-first, and already models several things that matter specifically to your use case:

- two-person household planning
- independent retirement timing
- survivor-mode behavior
- scenario-per-file workflow
- custom event semantics
- direct Monarch anchoring

ignidash is stronger as a generalized financial-planning product and simulation engine.
It has meaningfully deeper productization and a richer retirement-account/tax engine than NWN in several areas:

- Monte Carlo simulation
- historical backtesting
- richer account typing
- contribution-rule and IRS-limit modeling
- more advanced federal tax mechanics
- polished UI flows
- built-in AI/chat/insights surfaces

My overall recommendation is:

- keep NWN as the primary planning tool for your real household scenarios
- treat ignidash as a source of ideas and possibly a secondary analysis surface
- only pursue a Monarch-to-ignidash bridge if the goal is exploratory comparison, not replacement
- do not attempt a full NWN-to-ignidash migration unless ignidash first gains true couple/household support

## Where Net Worth Navigator Shines

### 1. Better fit for your planning shape

NWN is built around a two-person household with explicit person-level settings and shared household outcomes.
That matters because your planning is not just "retire at age X with one portfolio." It includes:

- `person1` / `person2` modeling
- independent retirement years
- survivor spending rules
- survivor Social Security behavior
- death-triggered phase changes
- household cash-reserve policy

ignidash's core timeline is currently single-person. Its `timeline` schema has one birth month, one birth year, one life expectancy, and one retirement strategy. That is a major structural mismatch for your real scenarios.

### 2. Better scenario expressiveness for your use case

NWN's scenario surface is unusually expressive for household planning because it combines:

- typed events
- recurring events
- reserve-first expense funding
- home buy/sell events
- spending-shift regimes
- person-specific retirement and SS synthesis
- local scenario cloning and rerender flow

That gives you a very practical planning language for things like:

- surgery funding
- vacations and sinking funds
- move-to-Indonesia regime shifts
- survivor transitions
- house sale timing

ignidash has strong building blocks, but they are more form-centric and less tailored to your household semantics.

### 3. Lower operational complexity

NWN is still "a Python app plus static output."
ignidash is a full Next.js + Convex product with:

- auth
- database
- server functions
- Docker/self-hosting flow
- WebSocket-backed Convex runtime
- optional Stripe / AI / analytics integrations

That extra machinery is not free. If your goal is "edit assumptions, rerender, inspect plan," NWN is much closer to the minimum viable system.

### 4. Better local-control story

NWN keeps the planning surface in TOML files under your control.
That is especially valuable for:

- local-only scenarios
- bulk editing
- diffability
- reproducibility
- easy scripted transformations

ignidash stores plans in Convex documents and is much more app-database oriented. It has JSON import, but its natural operating mode is not file-native planning.

## Where ignidash Shines

### 1. Stronger simulation engine

ignidash has a materially more developed calculation engine than NWN in several areas:

- month-by-month simulation instead of NWN's annual cadence
- fixed-return, Monte Carlo, and historical-backtest modes
- iterative annual tax settlement
- RMD handling
- richer account classes
- realized-gains and Roth contribution-basis tracking
- debt and physical-asset modeling integrated into the engine

If the question is "which engine looks more like a general-purpose retirement-planning product," ignidash wins.

### 2. Stronger retirement-account mechanics

ignidash has explicit support for:

- `401k`, `403b`, `ira`, `roth401k`, `roth403b`, `rothIra`, `hsa`, `taxableBrokerage`, `savings`
- shared contribution limits
- employer match
- contribution ordering
- mega-backdoor Roth flags
- Roth contribution-basis tracking
- RMD eligibility distinctions by account type

NWN is improving quickly here, but it still uses a more household-approximation-oriented model.

### 3. Stronger tax depth

ignidash's tax engine is notably ahead of NWN in federal modeling detail. It already includes:

- ordinary income brackets
- LTCG bracket stacking
- NIIT
- Social Security taxation
- early-withdrawal penalties
- capital-loss carryover
- Section 121 treatment for primary residence sales

NWN currently has a pragmatic tax model tuned to your planning workflow. ignidash is closer to a reusable tax-simulation framework.

### 4. Stronger product/UI polish

ignidash is much more mature as an end-user product:

- dashboard
- plan list
- compare page
- finances tracker
- simulator sections
- chart suites
- tables
- AI chat
- AI insights
- onboarding flows

NWN is very effective, but it is still purpose-built and operator-oriented.

## Is ignidash robust enough for your needs?

### Short answer

Partly, but not as a replacement yet.

### Robust enough in these areas

ignidash looks robust enough for:

- single-person retirement planning
- account-level retirement modeling
- contribution and withdrawal analysis
- tax-aware retirement projections
- Monte Carlo and historical stress testing
- polished exploratory analysis

### Not robust enough for your actual household model

For your specific needs, the largest gaps are structural rather than cosmetic:

- no true couple/dual-person core timeline
- no household survivor model comparable to NWN
- no NWN-style event language for your custom life-planning cases
- no obvious equivalent to your phase-specific reserve semantics
- no direct Monarch bridge
- no native TOML scenario workflow

The README itself still lists "Support for planning as a couple" as planned rather than complete. That is the key blocker.

## Is ignidash overly complex?

For your use case, yes, probably.

That does not mean ignidash is badly designed. It means its complexity is aimed at a broader product problem:

- multi-user app architecture
- persistence and auth
- general-purpose UI workflows
- AI feature integration
- self-hosting and deployment
- database-backed syncing

If your main job is "model my household with custom scenarios and local assumptions," much of that complexity is overhead rather than leverage.

The biggest complexity tradeoff is this:

- NWN complexity mostly lives in your modeling semantics
- ignidash complexity lives in both modeling semantics and product infrastructure

For a solo local planner, NWN's tradeoff is usually better.

## Could we apply the Monarch bridge methodology to ignidash?

### Short answer

Yes, probably, but the bridge target would be different.

### Why it is feasible

ignidash already has an internal "NW Tracker -> simulator plan" sync concept:

- finances are stored separately from plans
- plan accounts can carry `syncedFinanceId`
- plan debts can carry `syncedFinanceId`
- physical assets can carry `syncedAssetId` / `syncedLiabilityId`
- there is utility code that propagates finance updates across linked plans

That is a promising insertion point.

### What a Monarch bridge would need to do

Instead of NWN's current "Monarch -> classified balances -> model start state" flow, an ignidash bridge would likely be:

1. Pull Monarch accounts
2. Map them into ignidash finance assets/liabilities
3. Upsert those into the `finances` document
4. Let ignidash's existing sync utilities push updated balances into linked plans

### Main implementation challenges

- account-type mapping from Monarch into ignidash's asset/liability taxonomy
- ownership semantics, since your household is joint and ignidash is still primarily single-person
- deciding whether a Monarch account should become:
  - an NW Tracker asset
  - a simulator account
  - a physical asset
  - a debt
- handling the mismatch between NWN categories and ignidash plan schemas

### Practical recommendation

If you want to try this, start with a narrow bridge:

- cash accounts
- taxable brokerage
- retirement accounts
- mortgage / vehicle liabilities

Avoid trying to solve scenario migration and household semantics in the same first pass.

## Could we port NWN scenario configs into ignidash?

### Short answer

Partially, but not cleanly and not losslessly.

### What could port relatively well

These NWN concepts map reasonably well:

- current balances -> ignidash accounts / finances
- annual wage income -> incomes
- Social Security income -> incomes
- recurring expenses -> expenses
- debts -> debts
- real estate -> physical assets
- broad market assumptions -> market assumptions

### What maps poorly

These are the problematic areas:

- two-person structure
- survivor phase semantics
- death-triggered transitions
- survivor Social Security step-up
- phase-specific withdrawal policy
- reserve-first event funding
- NWN `SpendingShift`
- synthesized retirement/SS events from person settings
- event-level semantics tied to household phases

ignidash's plan model is not event-centric in the same way. It is closer to:

- timeline
- incomes
- expenses
- accounts
- debts
- physical assets
- contribution rules
- tax settings

That means a converter could translate the overlapping subset, but many of your most valuable NWN behaviors would be flattened into approximations or dropped.

### Realistic migration posture

A one-way export tool from NWN to ignidash JSON is feasible for a reduced subset.
It would be useful for:

- approximate what-if comparisons
- Monte Carlo overlays on a simplified version of the plan
- exploratory side analysis

It would not be a faithful replacement for the NWN scenario set.

## What should stay in NWN, and what is worth porting from ignidash?

### Keep in NWN

These are NWN differentiators worth preserving:

- scenario TOML workflow
- household-first modeling
- explicit survivor semantics
- custom event language
- direct Monarch anchoring
- local-only scenario iteration

### Good candidates to port from ignidash into NWN

#### 1. Monte Carlo / historical stress-testing mode

This is the clearest strategic win.
NWN is deterministic today. Adding optional stochastic and historical modes would meaningfully expand its decision value without forcing a product rewrite.

#### 2. Richer account mechanics

ignidash has cleaner account taxonomy and stronger per-account behavior.
Useful NWN upgrades inspired by that model:

- more explicit account classes
- tighter Roth basis handling
- improved taxable basis / gains tracking
- clearer RMD behavior per account type

#### 3. Contribution-rule framework

ignidash's contribution ordering and limit handling is more mature.
A lighter-weight NWN version could add:

- explicit contribution-order rules
- optional employer-match modeling
- contribution-limit awareness
- better routing semantics for mixed employer plans

#### 4. Better tax modularity

ignidash's tax engine suggests a more modular design direction for NWN:

- tax processor separation
- clearer taxable-income source breakdown
- richer outputs for auditability

NWN should likely keep its pragmatic assumptions, but its internals could still benefit from this structure.

#### 5. Better chart decomposition and result views

ignidash has a broader and more composable output layer:

- multi-view charts
- drill-downs
- multi-simulation result modes
- richer table views

NWN could borrow some of that presentation architecture without adopting the whole product stack.

#### 6. JSON import/export boundary

ignidash's import path is a good reminder that NWN could benefit from a formal machine-readable interchange format alongside TOML, especially if you ever want:

- external tools
- batch transforms
- comparison exports
- simulation adapters

## What should probably not be ported into NWN

- Convex-backed persistence
- auth / subscription plumbing
- AI features as a first priority
- full SaaS-style product architecture
- heavy UI formification of the planning surface unless TOML becomes a real bottleneck

Those would add a lot of complexity before they add proportionate value.

## Recommended Strategy

### Best near-term path

1. Keep NWN as the source-of-truth planner
2. Borrow selected engine/product ideas from ignidash
3. If desired, build a narrow NWN -> ignidash export for simplified comparison runs
4. Only build a Monarch -> ignidash bridge if you want ignidash as a secondary dashboard/simulator

### Best medium-term path for NWN

If we want to invest based on what ignidash proves valuable, the highest-payoff NWN roadmap items look like:

1. Monte Carlo and/or historical backtesting
2. richer taxable-basis and account mechanics
3. more modular tax internals
4. optional import/export schema
5. improved multi-view results and drill-downs

### Best medium-term path for ignidash, if replacement is still desired

Before ignidash could reasonably replace NWN for you, it would need:

1. true couple support
2. survivor-phase semantics
3. better household event modeling
4. a way to preserve custom scenario logic
5. a stable local/self-hosted workflow you actually enjoy operating

## Bottom Line

ignidash is not too weak. It is actually stronger than NWN in several general retirement-planning dimensions.

But it is probably too misaligned, today, to replace NWN for your real household planning.

The strongest posture is a hybrid one:

- NWN remains the bespoke planner because it matches your semantics
- ignidash serves as inspiration and possibly a secondary analysis engine
- any bridge work should be incremental and scoped to balance sync or simplified export first, not full migration
