# Read-Only Demo Scenario Setup Alignment

**Status:** Complete (2026-08-09)

## Goal

Make each generated demo Setup page accurately present the options and values
available in the live Scenario Setup Panel, without shipping any API calls,
save actions, or editable controls.

## Scope

1. Replace the legacy three-tab summary with the live panel's six-tab
   information architecture: Metadata, Social Security, Income &
   Contributions, Accounts, Events, and Raw TOML.
2. Render all currently surfaced configuration values as static display fields,
   including advanced metadata, simulation/Monte Carlo settings, contribution
   routing/ownership, synthetic balances, properties, liabilities, and typed
   event cards.
3. Derive retirement, Social Security claim, and end-of-plan information from
   v2 events instead of stale person-level v1 fields.
4. Preserve demo navigation and add a clear read-only notice. Static tabs may
   use local browser JavaScript only; the page must make no network requests
   and expose no mutation actions.
5. Add generator tests and rebuild the disposable local demo preview.

## Acceptance Criteria

- Generated pages expose all six live Setup tabs and no Save/Render/Add/Edit/
  Delete control.
- The sample pages show Social Security tables, person-specific income and
  contribution settings, liabilities, and event data.
- Timeline values originate from `Retire`, `SocialSecurity`, and `EndOfPlan`
  events.
- Generated HTML has no API URL or `fetch()` call.
- Focused and full tests pass; a real local preview build completes.

## Result

- Replaced the legacy three-tab summary with a six-tab static renderer matching
  the live Setup Panel's information architecture.
- The read-only renderer now displays v2 event-derived timeline values, Social
  Security benefit tables, detailed income/contribution settings, advanced
  household/simulation settings, manual balances/properties/liabilities, and
  every event's configured properties.
- It uses only local tab-switching JavaScript: no API URLs, fetches, or write
  controls are emitted. A real four-sample preview build and the 224-test suite
  completed successfully.
