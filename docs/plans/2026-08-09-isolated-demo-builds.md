# Isolated Demo Builds for Local Preview and GitHub Pages

**Status:** Complete (2026-08-09)

## Goal

Keep GitHub Pages deployment unchanged while making the demo builder safe to run
from any local branch. A local build must produce a self-contained static demo
without touching the user's normal `output/` projections, scenario manifest,
cache, sidecars, or deployment directory.

## Design

1. `run.py` accepts an output-root override and a no-deploy mode. Defaults keep
   the existing normal render/deploy behavior unchanged.
2. `build_demo.py` renders sample scenarios into an isolated work directory,
   then copies only sample artifacts into a separately selected demo output
   directory. It filters the copied manifest in memory; it never deletes from
   the normal scenario-output root.
3. `build_demo.py --output-dir <path>` supports branch-local preview builds.
   Its default remains `output/demo` for the GitHub Pages workflow.
4. The Pages workflow continues to run the builder and deploy the generated
   static artifact. Local users can serve the output with Python's built-in
   HTTP server for browser inspection.

## Acceptance Criteria

- A demo build passes `--output-root <work-dir> --no-deploy` to each sample
  render and does not mutate `output/scenarios`.
- The generated demo contains only sample scenario artifacts and its matching
  manifest.
- Existing `python run.py` behavior retains the default `output/` and deploy
  paths.
- The builder chooses the Windows virtual-environment Python when available.
- Tests cover output-root selection and demo-build subprocess isolation.
- README documents the local preview command.

## Verification

1. Run focused unit tests for scenario output roots and the demo builder.
2. Run the full test suite.
3. Build the demo into a disposable local preview directory and confirm the
   normal `output/scenarios` manifest is unchanged.

## Result

- Implemented `run.py --output-root <path> --no-deploy` and isolated
  `build_demo.py --output-dir <path> --work-dir <path>`.
- Verified a real Windows preview build of all four samples in 59 seconds.
  The SHA-256 digest of the normal `output/scenarios/index.json` was identical
  before and after the build.
- Focused tests plus the full test suite passed (223 tests total).
