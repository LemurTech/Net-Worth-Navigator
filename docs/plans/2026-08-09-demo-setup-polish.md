# Read-Only Demo Setup Visual Polish

**Status:** Complete (2026-08-09)

## Goal

Make the static Scenario Setup page feel recognizably like the live product
while keeping its strict read-only, offline-safe contract.

## Scope

1. Expand the demo notice into a concise orientation panel that explains the
   static snapshot, interactive local-only affordances, and how to edit a plan.
2. Carry across high-value field help from the live Setup Panel, prioritizing
   cash targets, market assumptions, claiming benefits, contribution routing,
   tax/RMD settings, simulation rules, accounts, and events.
3. Use the live event type icon vocabulary in read-only event cards and add
   visual status/type treatment.
4. Recreate appropriate non-mutating UI affordances: advanced disclosure
   panels, selected source/household cards, and richer state badges.
5. Extend generator tests, rebuild the preview, and run the full suite.

## Guardrails

- No network requests, API URLs, form submissions, or mutation controls.
- All visual controls must be static display or local browser-only disclosure/
  tab interaction.

## Result

- Added a richer static-snapshot orientation panel, local-only interaction
  cues, and collapsed advanced disclosures that mirror the live panel's
  advanced-control treatment.
- Added targeted live-help explanations throughout the Setup surface and the
  live event-type icon vocabulary to every event card.
- Rebuilt all four samples successfully; focused checks and the full 224-test
  suite passed.
