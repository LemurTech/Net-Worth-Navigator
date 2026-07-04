# Scenario Transition Plan — Net Worth Navigator

**Last Updated:** 2026-06-19
**Status:** Proposed

## Summary

Net Worth Navigator will move from a single-root `config.toml` model to a
scenario-based configuration model with:

- one scenario per config file
- shared tax-table reference files split out from scenario configs
- per-scenario backups
- per-scenario sidecars
- a shell-style projections page that loads pre-rendered scenario outputs
- editor-controlled rendering (`render current` and `render all`)

This plan preserves NWN's current strengths:

- raw TOML remains the authoring format
- projection rendering stays fast because scenario selection does not re-fetch
  Monarch data
- the public projections page remains mostly static
- the config editor remains the control plane for editing and rendering

## Goals

- Reduce clutter in scenario configs by moving bulky tax tables into shared
  reference files.
- Support multiple named scenarios without mixing them into one giant TOML.
- Keep scenario switching fast on the projections page by using pre-rendered
  outputs.
- Preserve exact-text raw TOML editing for each scenario file.
- Keep backups and generated analysis files isolated per scenario.

## Non-Goals For V1

- No live Monarch fetch on scenario selection.
- No browser-side filesystem discovery or directory listing dependency.
- No server-side render triggered directly from the projection-page dropdown.
- No structured form editor replacing raw TOML editing.
- No multi-scenario-in-one-file format.

## Proposed File Layout

```text
Net-Worth-Navigator/
├── config/
│   └── tax_tables/
│       ├── 2025_us_federal_oregon.toml
│       └── ...
├── scenarios/
│   ├── default.toml
│   ├── optimistic.toml
│   └── ...
├── output/
│   ├── scenarios/
│   │   ├── index.json
│   │   ├── default/
│   │   │   ├── projection.html
│   │   │   ├── projection_yearly.csv
│   │   │   ├── event_flows.csv
│   │   │   ├── scenario_manifest.json
│   │   │   └── accounts_snapshot.json
│   │   └── optimistic/
│   │       └── ...
│   └── config-backups/
│       ├── default/
│       └── optimistic/
└── ...
```

## Scenario Config Shape

Each scenario should remain a full scenario document, but with tax reference
data split out.

Suggested top-level metadata:

```toml
[scenario]
name = "Default Plan"
slug = "default"
description = "Baseline household plan using current assumptions."
tax_table_set = "2025_us_federal_oregon"
```

The rest of the file continues to hold scenario-specific assumptions:

- simulation
- display
- people
- spending
- withdrawal policy
- assumptions
- accounts
- liabilities
- events

The `tax_table_set` value points to `config/tax_tables/<name>.toml`.

## Shared Tax Table Shape

The shared tax-table file should contain reference data only:

- federal bracket schedules
- federal standard deductions
- Social Security provisional-income thresholds
- state tax reference data
- tax-year metadata and source notes

The scenario file should retain only scenario-specific tax behavior:

- `enabled`
- lifecycle filing statuses
- any future scenario-specific tax toggles that are not table data

## Manifest Shape

The public shell page and editor should rely on a generated manifest rather
than scanning directories directly.

Suggested path:

- `output/scenarios/index.json`

Suggested content per scenario:

```json
{
  "default_slug": "default",
  "generated_at": "2026-06-19T12:00:00",
  "scenarios": [
    {
      "slug": "default",
      "name": "Default Plan",
      "description": "Baseline household plan using current assumptions.",
      "config_path": "scenarios/default.toml",
      "projection_path": "scenarios/default/projection.html",
      "rendered_at": "2026-06-19T12:00:00"
    }
  ]
}
```

## UX Model

### Config Editor

The editor becomes the scenario control plane.

Required additions:

- scenario dropdown
- create/clone scenario action
- scenario name and description visibility
- save current scenario
- save + render current scenario
- render all scenarios
- scenario-specific backup location display

Editor behavior:

- loading a scenario reads exactly one scenario TOML file
- saving preserves exact text for that scenario file
- validation resolves shared tax-table references before reporting success
- clone copies the source scenario file into a new slugged file and updates the
  manifest source of truth if needed

### Projection Shell Page

The public page becomes a shell with:

- a scenario dropdown
- the current scenario description
- an embedded projection view, likely via `iframe`

Behavior:

- initial page load uses the manifest default scenario
- changing the dropdown swaps the embedded rendered projection path
- no re-render is triggered from this page in V1

## Transition Phases

### Phase 1 — Shared Config Loader

Create a shared config-loading module used by:

- `src/model.py`
- `src/monarch_bridge.py`
- `run.py`
- `admin_app.py`

Responsibilities:

- load one scenario file
- load referenced shared tax-table file
- merge them into one runtime config object
- expose scenario metadata cleanly
- validate duplicate/missing keys where needed

This is the core enabling step. It should land before editor or projection-page
scenario UI.

### Phase 2 — Tax Table Extraction

Move the current large `[taxes]` reference tables out of `config.toml` into a
shared tax-table file under `config/tax_tables/`.

Tasks:

- define the split between scenario tax settings and shared tax data
- migrate the current 2025 federal/Oregon table content
- update runtime loader merge behavior
- update tests to load through the new merged-config path

### Phase 3 — Scenario Directory Model

Introduce `scenarios/` and migrate the current root `config.toml` into the
first scenario file, likely `scenarios/default.toml`.

Tasks:

- define slug rules
- add scenario discovery
- define default-scenario selection
- add scenario metadata parsing
- make the current root config path either:
  - a compatibility shim for one release window, or
  - a removed legacy path if migration is handled in one cut

Recommended approach:

- keep a brief compatibility window if it reduces churn in `run.py`,
  `admin_app.py`, and documentation

### Phase 4 — Per-Scenario Output Layout

Change rendering outputs to be scenario-specific.

Tasks:

- render HTML into `output/scenarios/<slug>/projection.html`
- write sidecars into the same per-scenario directory
- move backups to `output/config-backups/<slug>/`
- ensure deploy logic can publish:
  - the shell page
  - the scenario manifest
  - each scenario's rendered artifacts

### Phase 5 — Editor Scenario Management

Extend the FastAPI editor to support:

- scenario dropdown
- load selected scenario
- clone current scenario
- save current scenario
- save + render current scenario
- render all scenarios

Notes:

- exact-text save behavior should remain intact
- clone flow should require a validated new slug
- backup behavior should remain automatic per save

### Phase 6 — Projection Shell Page

Add a public shell page that reads `output/scenarios/index.json` and populates
the scenario dropdown.

Recommended V1 implementation:

- static shell HTML + small JS
- `iframe` for scenario projection pages
- fallback state when a scenario is missing or has not been rendered

### Phase 7 — Cleanup And Documentation

Tasks:

- update README for new scenario workflow
- update deployment/admin docs
- update Memory Bank docs after the transition lands
- remove single-config assumptions from comments and UI copy

## Key Design Decisions To Preserve

- one scenario per file
- no scenario render on dropdown selection in V1
- no live Monarch fetch on scenario selection
- manifest-driven scenario discovery
- shell-page model for projections
- editor-driven render actions

## Migration Risks

### 1. Loader Duplication

Config loading is currently duplicated in `src/model.py` and
`src/monarch_bridge.py`. If scenario logic is added in two places, drift is
likely. Shared loader first is the safest path.

### 2. Backward Compatibility

Several code paths and docs currently assume root `config.toml` is the single
source file. Transition work needs a deliberate compatibility plan or a clean
flag day migration.

### 3. Raw Editor Assumptions

`admin_app.py` currently assumes one editable file and one backup namespace.
Scenario support changes both assumptions and needs careful path validation.

### 4. Deployment Shape

The current deploy step publishes one `projection.html`. Scenario support needs
clear rules for where the shell page, scenario projections, and manifest are
published.

### 5. Test Coverage Gaps

Existing tests mostly patch `load_config()` directly. They should be migrated
to test the shared merged-config loader plus scenario discovery/render behavior.

## Recommended Implementation Order

1. Add shared config loader and merged-config tests.
2. Extract tax tables into `config/tax_tables/`.
3. Introduce `scenarios/default.toml` and scenario metadata.
4. Update render pipeline for per-scenario output and sidecars.
5. Extend editor with scenario dropdown, clone, and render actions.
6. Add shell projections page backed by the generated scenario manifest.
7. Remove or retire obsolete single-config assumptions.

## Open Questions

- Should default-scenario selection live inside one scenario file or in a small
  project-level manifest/source file?
- Should `config.toml` remain as a temporary compatibility shim during
  migration, and if so for how long?
- Should the shell page live at `/finances/` while scenario pages live under
  `/finances/scenarios/<slug>/projection.html`?
- Should scenario descriptions be editable only inside TOML metadata, or also
  exposed as first-class editor form fields?

## Suggested First Implementation Slice

The lowest-risk first slice is:

1. create the shared config loader
2. move current tax tables into `config/tax_tables/2025_us_federal_oregon.toml`
3. keep using the current single scenario during this step
4. add tests proving runtime config merge behavior

That delivers immediate config cleanup and lays the foundation for
multi-scenario work without forcing the full scenario migration at once.
