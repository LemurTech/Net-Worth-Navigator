# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.
Entries belong under a `## YYYY-MM-DD` date header. The `## [Unreleased]` pattern is retired.

## 2026-07-04 (Setup Panel — mobile responsive pass)

### Added

- **Default scenario checkbox**: Replaced the static DEFAULT badge next to the slug with a toggleable `[✔] Default` checkbox. Checking/unchecking calls `POST /api/set-default-scenario` which sets `is_default = true` in the target scenario's TOML and clears it from the previously-default scenario. New API endpoint in `admin_app.py`.
- **`POST /api/set-default-scenario` endpoint**: Reads the target scenario slug from the request body, sets `is_default` in the TOML, removes it from the current default, and writes backups for both.

### Changed

- **Header button layout**: Clone Scenario and Delete Scenario moved from the action bar to the top header `.links` bar, matching the visual style of Definitions and Open Projection. Added `.linkbtn-danger` CSS class. Top buttons use `flex: 1 1 45%` at ≤900px to break into two rows of two.
- **Top buttons font size**: `.linkbtn` set to `font-size: 13px` (was inheriting 16px on `<a>` tags and 14px on `<button>` tags). "Open projection" capitalized to "Open Projection".
- **Action bar equal widths**: At ≤600px, all action bar buttons (`Save Quick Controls`, `Validate`, `Save + Re-render`, `Save + Render All`, `New from Template`) share equal width via `flex: 1 1 0`. At ≤480px, they stack one per row via `flex: 1 1 100%`.
- **Raw TOML tab buttons equal width**: At ≤600px, all four buttons (`Validate`, `Save`, `Save + Re-render`, `Save + Render All`) share equal width.
- **Data source radio groups**: Both the quick-edit panel radios and the Synthetic Setup tab radios now use `flex: 1 1 0` on `.radio-group .radio-card` to stretch equally across the row. At ≤360px, they stack vertically via `flex-direction: column`.
- **Radio card text**: Added `white-space: nowrap` to `.radio-card` to prevent text wrapping inside cards at tight widths.
- **People section restructured**: Each person now uses two horizontal rows — Name + Birth Year on the first row, Retires (year) + Age slider on the second row. The name input and slider use `flex: 1; width: 100%` to fill available space; birth year and retires year use `width: 100px` for consistency. "or age" label moved inline with the slider in a single flex row.
- **Year field widths unified**: All six year inputs (person1/2 birth year, person1/2 retires year, simulation start year, simulation end year) use `width: 100px`. Stock Return, Bond Return, Inflation, and Equity Alloc inputs also set to `100px` for consistent sizing.
- **`@media (max-width: 600px)` breakpoint**: Removed `inline-row { flex-direction: column }` so People rows stay horizontal on mobile. Removed `radio-group { flex-direction: column }` (moved to 360px breakpoint).
- **`templates/setup_panel.html` and `admin_app.py`**: Multiple CSS rules, HTML structure changes, and JS handler for default checkbox. Container restarted after every change set.

### Fixed

- **Duplicate `@media (max-width: 900px)` block**: A prior patch created a duplicate block; merged correctly into one block.

### Verified

- All template changes confirmed via `curl` against the live `/finances/config/setup` endpoint: correct CSS rules, HTML elements, and JS function references present.
- API endpoint tested with `curl -X POST` — returns `{"ok": true}`.
- Config editor container restarted and serving 200 OK.

## 2026-07-04 (Plotly graph interaction controls)

### Added

- **Y-axis locked (`fixedrange=True`)** on all Plotly charts — main net worth, cash flow, portfolio (Monte Carlo + deterministic), liabilities, cash reserve, gantt, simulation outcomes, and compare page (net worth, portfolio, cash flow). Users can no longer drag the y-axis up/down into irrelevant ranges.
- **Scroll-wheel zoom enabled** (`config=dict(scrollZoom=True)`) on every Plotly chart. With y-axis locked, scroll-zoom operates only on the x-axis (years). Double-click resets to full range.
- **Preset zoom buttons** (Full / 10yr / 25yr / 50yr) on the main chart. Each button calls `Plotly.relayout()` to set specific x-axis ranges. Active button highlights in blue. Located below the event-label controls in the chart wrap.

### Changed

- **`src/charts.py`**: All 8 chart builder functions updated — every `yaxis` dict gained `fixedrange=True`; every `fig.to_html()` call gained `config=dict(scrollZoom=True)`. CSS, HTML template, and JS handler added for preset zoom buttons.
- **`src/scenario_shell.py`**: Compare page's three charts (net worth, portfolio, cash flow) gained `fixedrange: true` on y-axis and `scrollZoom: true` in their `Plotly.newPlot()` config.
- **`docs/activeContext.md`**: Updated status to reflect completed graph interaction work and next steps.

### Verified

- Syntax check: both `charts.py` and `scenario_shell.py` compile cleanly.
- Offline render (`run.py --offline` on default scenario) completes successfully across all three render modes (deterministic, historical, monte_carlo).
- Rendered HTML verified: 7 `fixedrange` occurrences in each projection page, `scrollZoom` in all chart configs, `zoom-preset-btn` and `zoomToYears()` function present in projection page output.
- Compare page rendered with 3 `fixedrange: true` occurrences and `scrollZoom` in each chart config.

## 2026-07-04 (tab tooltip polish — stuck-open + scroll-detach)

### Fixed

- **A tab tooltip would stay open while the next one opened, then close only once you moved past it.** Root cause: the fixed-position tooltip box (260px wide) can visually overlap the *next* tab's button, since tabs sit close together. Moving the mouse into that overlap still counted as hovering the *previous* tab's `.help-tooltip` wrapper (CSS `:hover` follows the DOM ancestor under the cursor, not what's visually on top), so its tooltip stayed lit even after the neighboring tab's own tooltip had already opened. Fixed with `pointer-events: none` on `.tab-btn .tooltip-content` — the tooltip box itself no longer participates in hover/hit-testing, so hovering the visual space it occupies always reaches the *actual* tab underneath.
- **Tab tooltips floated in place while the page scrolled underneath them.** `position: fixed` tooltips are pinned to viewport coordinates computed once when they open (see the 2026-07-04 tab-tooltip feature note above) — nothing recalculated that position as the page moved. Added scroll/resize listeners (capture phase, so scrollable ancestors are caught too) that reposition whichever fixed tab tooltip is currently visible (`:hover` on desktop, `.tooltip-open` tap-toggle on mobile) so it tracks its anchor tab during scroll instead of visually detaching.

### Verified

Confirmed via headless-Chromium Playwright: hovering tab A then tab B closes A's tooltip and opens B's cleanly (previously A stayed open); tab tooltips move in exact lockstep with their anchor tab during scroll (measured pixel-for-pixel, desktop hover and mobile tap-toggle both confirmed); reproduced identically in the shell/iframe embedded context. Full test suite: same 6 pre-existing unrelated failures, no new regressions.

## 2026-07-04 (tab-label help tooltips)

### Added

- **Help tooltips extended to every tab label** on the projection page (Accounts, Cash Flow, Tax, Simulation, Portfolio, Gantt, Liabilities, Cash Reserve, Assumptions, Scenario Parameters) — same info-icon + hover/tap pattern as the KPI strip, so enabling help mode now explains what each tab shows, not just the summary numbers. Shared the existing inline-SVG icon by promoting it from a `_build_kpi_summary()`-local variable to a module-level `_INFO_ICON_SVG` constant so both call sites use one definition.

### Fixed

- **Tab tooltips needed `position: fixed` instead of the KPI-strip's `position: absolute` pattern.** `.tabs` has `overflow-x: auto` (added earlier for mobile horizontal scrolling) — CSS forces `overflow-y` to also compute as `auto`/clipping on the same box once *any* overflow axis is non-`visible`, even if `overflow-y` is never explicitly set. A normal absolutely-positioned tooltip anchored inside `.tabs` would therefore always get clipped, the same class of bug the KPI-strip tooltip had before its `overflow: hidden` was removed — except `.tabs`' `overflow-x: auto` can't simply be removed (it's needed for mobile scroll). Fixed by giving `.tab-btn .tooltip-content` `position: fixed` and computing exact viewport pixel coordinates in JS (`positionTooltip()` branches on `getComputedStyle(content).position === 'fixed'`), escaping the container's clipping entirely.
- **Clicking the info icon on a tab would also switch tabs**, since the icon lives inside the same clickable `<button onclick="switchTab(...)">`. Fixed by passing the click `event` into `switchTab(id, evt)` and returning early when `evt.target.closest('.help-info-icon')` — the tap-to-toggle tooltip handler still fires normally, but the tab no longer switches underneath it.

### Verified

Confirmed via headless-Chromium Playwright: info icons render on all tab labels; hover (desktop) and tap-toggle (mobile, 390px) both show the tooltip fully visible with correct explanatory text; last-tab (Scenario Parameters) tooltip clamps within the right viewport edge; first-tab (Accounts) tooltip renders correctly when embedded in the shell's iframe — the exact scenario that broke KPI tooltips before this fix pattern existed; clicking the info icon does not trigger a tab switch. Full test suite re-run (one stale assertion in `test_tax_model.py` updated to match the new tab-button markup) — same 6 pre-existing unrelated failures, no new regressions.

## 2026-07-04 (compare page crash fix — pre-existing bug, not from responsive pass)

### Fixed

- **`compare.html` failed to load its scenario selector chips or any chart data**, silently (no visible error to the user, just an empty/loading page). Root cause: `build_compare_page()`'s `DOMContentLoaded` boot handler unconditionally called `document.getElementById('help-mode-toggle').classList.add(...)` and `.addEventListener(...)` — but the compare page has **no** `#help-mode-toggle` button and no help-mode/tooltip UI at all (it was copy-pasted wholesale from `build_scenario_shell()`'s boot script in commit `9232437`, 2026-07-02, and never actually used on this page). The `null.classList`/`null.addEventListener` TypeError aborted the rest of the `DOMContentLoaded` handler, so `resolveAvailableModes()`, `renderChips()`, and `refresh()` — all listed *after* the dead help-mode block in the same handler — never ran. This bug predates the 2026-07-03/07-04 shell header work; it was only discovered now because nothing had reloaded/tested the compare page directly since it was introduced. **Fix**: removed the entire dead help-mode block from `build_compare_page()`'s boot script (14 lines); the page has never had help-mode/tooltip functionality and doesn't need it.

### Verified

Confirmed via headless-Chromium Playwright with console/pageerror capture: zero JS errors on load, 11 scenario chips render (previously 0), chart populated (previously empty `#compare-chart`), KPI table has rows. Full test suite re-run — same 6 pre-existing unrelated failures, no new regressions.

## 2026-07-04 (iframe shell header — mobile/foldable responsive pass)

### Fixed

- **Plan Name / Plan Type selects wrapped onto separate lines far too early** — on tablets and foldable phones (e.g. Samsung Z-Fold 3 unfolded), not just true narrow phones. Root cause was a single coarse `@media (max-width: 980px)` breakpoint that forced the *entire* control row (selects + buttons) into one vertical stack, and a follow-up `600px` breakpoint attempt was still too conservative for the real device width. Final fix: gave the two `<select>`s `text-overflow: ellipsis` so they never need to wrap or grow — long scenario/plan names truncate with "…" instead. The vertical-stack fallback for the pair now only triggers below `359px` (narrower than any current production phone), so selects stay side-by-side at effectively all realistic screen widths, foldables included.
- **Mobile button row was disorganized (7 buttons crammed at various widths).** Removed "Definitions" (from both the shell header and the standalone projection page's own toolbar — link still lives on the Setup Panel where it's actually used) and "Refresh Frame" (redundant; other ways to refresh exist in both standalone and embedded contexts) entirely, along with their now-dead JS (`hardRefreshFrame`, `currentSelectedScenario`, `currentSelectedMode`, `refreshButton` — all only referenced by the removed button). Left 4 buttons: Open Scenario Page, Compare Scenarios, Help (?), Scenario Setup.
- **Help toggle button ("?") was a small fixed 42×42px square while its siblings were full-width buttons** — visually inconsistent and cramped on mobile. Switched all 4 buttons (including `#help-mode-toggle`) to `flex: 1 1 0` so they share the row equally at the mobile breakpoint; the button row fits on one line down to ~320px.
- **`.control-actions` had a stale fixed pixel width (`362px`) left over from an earlier layout** — this silently capped how much room the mobile button row had to shrink into, no matter how much padding/font-size tuning was applied. Fixed by giving it `width: 100%; flex-basis: 100%` at the mobile breakpoint so it uses the full available row width.
- **Button labels needed to shorten on mobile without losing the desktop wording.** Used a dual-span pattern (`<span class="linkbtn-full">`/`<span class="linkbtn-short">`) toggled via CSS visibility at the `720px` breakpoint — no JS or duplicated DOM elements needed. Desktop keeps "Open Scenario Page" / "Compare Scenarios" / "Scenario Setup"; mobile shows "Open" / "Compare" / "Setup".

### Verified

All changes confirmed via headless-Chromium Playwright sessions across a wide width sweep (320px through 1400px, with explicit checks at 360px, 390px, 500px, 600px, 673–717px for Z-Fold-unfolded range, and desktop) — selector one-line behavior, button one-line behavior with equal widths, label switching, and ellipsis truncation with a synthetic long scenario name all checked with no regressions to prior tooltip/modal fixes. Full test suite run after each change; the same 6 pre-existing unrelated failures persisted throughout (confirmed via `git stash` comparison against the base commit) with no new failures introduced. Two tests updated to match the new reality: `tests/test_scenario_shell.py` (removed stale `editor_url`/`definitions_url` kwargs and assertions for the deleted Definitions/Refresh Frame buttons) and `tests/test_tax_model.py` (updated Definitions-link assertion to `assertNotIn`).

## 2026-07-03 (iframe/help-mode bug fix pass)

### Fixed

- **Help-mode toggle was completely unwired in the deployed shell page.** `build_scenario_shell()` in `src/scenario_shell.py` rendered a `#help-mode-toggle` button with no click listener at all — the working implementation only existed in the separate `build_compare_page()` function. Ported the click handler + `localStorage` persistence + bidirectional `postMessage` sync (shell → iframe on click, shell → iframe on iframe `load`) into `build_scenario_shell()`.
- **Welcome modal rendered off-screen when embedded in the shell's iframe.** `position: fixed` inside the iframe centers against the iframe's own (`195vh`) box, not the visible browser viewport. The embedded page now detects iframe context and `postMessage`s the parent shell to render its own copy of the overlay (duplicated markup/CSS/JS in `scenario_shell.py`, since shell and iframe are separate documents).
- **Welcome modal too narrow when rendered in the shell.** The shell has a global `box-sizing: border-box` reset that the standalone page lacks; an identical `max-width: 620px` rule produced a visually narrower content area in the shell. Bumped the shell's copy to `max-width: 704px` to match rendered content width exactly (620 + padding/border accounted for).
- **Info icon (`ℹ️` emoji) rendered as a fallback glyph indistinguishable from "?"** on the user's Windows Brave/Edge setup (missing emoji font). Replaced with an inline SVG icon (stroke circle + dot + bar, `currentColor`) with no font dependency.
- **Tooltip `overflow: hidden` on `.kpi-strip` clipped the popup** since it renders above the icon (`bottom: 100%`) but outside the parent's own box. Removed the clip; moved corner-rounding to `:first-child`/`:last-child`.
- **Tooltips unreachable on touch devices** — CSS `:hover` never fires on touch. Added a tap-to-toggle `.tooltip-open` class via delegated click handler; tapping elsewhere closes it.
- **Tooltip text overflowed off-screen on mobile instead of wrapping.** A fixed `@media (max-width: 480px)` breakpoint failed at other real mobile viewport widths (confirmed failing at 600px in testing). Replaced with unconditional `white-space: normal`, `box-sizing: border-box`, and `max-width: min(260px, calc(100vw - 32px))` so wrapping is guaranteed regardless of viewport width.
- **A single unbounded `.tabs` flex row (9 buttons, `flex-wrap: nowrap`, no `overflow-x`) forced the whole page to overflow horizontally on mobile**, which in turn pushed the `position: fixed` help toggle off-screen relative to the visible viewport — the true root cause of "tooltip icons not clickable on mobile" (the button was unreachable, not un-clickable). Gave `.tabs` its own `overflow-x: auto` and added `max-width: 100vw; overflow-x: hidden` on `body` as a backstop.
- **Tooltip appeared "off-stage" above KPI boxes near the top of the viewport, and was occluded near the top of the shell's iframe.** Root cause was two-fold: (1) the tooltip was unconditionally positioned above its icon with no fallback; (2) an iframe clips its own painted content to its own local coordinate space regardless of how much room the *parent* page has — measuring "is there room above" against the parent viewport (frame-compensated) gave wrong answers. Added JS `positionTooltip()` that measures plain, uncompensated `getBoundingClientRect()` in whichever document is running (iframe-local when embedded) and toggles `.tooltip-below` / `.tooltip-clamp-left` / `.tooltip-clamp-right` classes to flip/clamp the popup so it always stays on-screen. A mid-implementation bug (measuring the icon's rect instead of the `.help-tooltip` wrapper's rect, which is the actual CSS positioning anchor) was caught and fixed before shipping.

### Verified

All fixes confirmed via headless-Chromium Playwright sessions (not just code review) across: standalone page, shell/iframe-embedded page, and mobile (iPhone 13 viewport, touch emulation) — hover, tap-toggle, vertical flip, and horizontal clamp all checked in each context with no regressions to existing tab-switching or data-table horizontal scroll behavior.

## 2026-07-02 (Phase 3 — COMPLETE: Validation, Help Mode, Sample Guidance)

### Added

#### **Task 1: Preflight Validation (Complete)**

- **Scenario validation function** (`src/model.py:validate_scenario`): Comprehensive pre-flight check for scenario configuration before projection runs. Validates required fields (scenario name/slug, simulation years, assumptions, spending, person data, income specs), data formats (DOB as YYYY-MM-DD, birth year 1900-2100), reasonable ranges (life expectancy <120, retirement age warnings), simulation logic (start <= end year, projection doesn't exceed life expectancy by >10 years), and synthetic-mode liability consistency (all liabilities must have matching balance entries).

- **CLI integration** (`run.py`): Validation runs automatically before every projection. On failure: clean numbered error list with actionable fixes, exits with code 1 (no Python traceback). On success: continues silently to projection.

- **API endpoint** (`admin_app.py:/api/validate-scenario`): POST endpoint for Setup Panel validation. Returns JSON with `is_valid` boolean, `errors` array, and `config_path`.

- **Setup Panel UI enhancement** (`templates/setup_panel.html`): Existing "Validate" button upgraded from TOML-syntax-only check to full semantic validation. Shows loading state during validation. On success: green toast. On failure: modal with numbered error list, config path, and "Edit Raw TOML" button.

#### **Task 2: Optional Help Mode (Complete)**

- **Help Mode toggle button** (`src/charts.py`): New `?` button in projection page toolbar (bottom-right, next to "Edit Config" and "Definitions"). Toggles help mode on/off. State persists in localStorage (`nwn-help-mode`). Button shows active state (blue background) when help mode is on.

- **Help Mode CSS** (`src/charts.py:_TABS_CSS`): Styling for help button, info icons, and tooltips. Info icons (ℹ️) are hidden by default, only visible when `body.help-mode-active` class is present. Tooltips appear on hover over info icons.

- **Help Mode JavaScript** (`src/charts.py:_TABS_JS`): Toggle logic restores state from localStorage on page load, adds/removes `help-mode-active` class on body element, persists preference across sessions.

- **KPI tooltips** (`src/charts.py:_build_kpi_summary`): Each KPI box now includes help icon + tooltip with explanation. Tooltips explain "Starting Net Worth", "Net Worth at Retirement", "Retirement Age", and "Net Worth at End" in plain language. Only visible when help mode is active.

- **First-time welcome overlay** (`src/charts.py:_TABS_JS`): One-time modal that appears when user first opens a projection. Highlights key features: chart hover, year-column highlighting, tab navigation, and help mode button. Two action buttons: "Remind me later" (dismisses without marking seen) and "Got it, don't show again" (sets localStorage flag `nwn-welcome-seen`). Styled with gradient background, border glow, and fade-in animation.

#### **Task 3: Guided Sample Exploration (Complete)** ✨

- **"About This Sample" information card** (`src/charts.py:build_chart`): Appears only when `scenario.slug == "sample"`. Displays above KPI boxes in projection output. Explains what the sample scenario demonstrates: dual-income household (Alex & Sam), retirement planning, mortgage/auto loan paydown, recurring events (travel, maintenance, vehicle replacements), and later-life planning. Includes tip about year-column highlighting and projection mode switching. Two action buttons: "View Sample Config" (opens editor) and "Create Your Own" (opens Setup Panel).

- **Sample guide CSS** (`src/charts.py:_TABS_CSS`): Teal gradient background, teal border accent, arrow bullets (▸), blue tip callout box with left border accent, two-button action bar with hover states.

### Design Decisions

- **Opt-in by default:** Help mode starts OFF (clean interface), user must click `?` to enable it.
- **Persistent preference:** LocalStorage remembers help mode state across page loads.
- **Visual feedback:** Active button gets blue background, info icons appear when active.
- **Contextual tooltips:** Tooltips are positioned above their target, with arrow pointer.
- **Non-intrusive welcome:** One-time orientation overlay, easily dismissed, never blocks workflow.
- **Remind-later option:** Users can defer the welcome without permanently dismissing it.
- **Sample-specific guidance:** "About This Sample" card only shows for the sample scenario, not for real user scenarios (preserves clean UX for production use).
- **Action-oriented CTA:** Sample guide includes direct links to view config or create new scenario, reducing friction for new users.

### Outcome

Phase 3 delivers a **complete onboarding and exploration experience** for new users:

1. **Preflight validation** catches configuration errors before they become confusing projection failures
2. **Optional help mode** provides contextual guidance without cluttering the default interface
3. **First-time welcome** orients new users to key interactions
4. **Sample guidance** explains the demo scenario and provides clear next steps

All three tasks integrated, tested, and working in production. New users can now:
- Load the sample scenario and understand what they're seeing
- Enable help mode to learn about KPI metrics
- Create their own scenario with validation feedback
- Understand configuration errors with actionable fixes

---

## 2026-07-02 (Phase 2 — Onboarding Improvements)
### Added

- **Installation verification script** (`scripts/verify_install.py`): Health check that verifies Python version (3.11+), dependencies, TOML parsing, model imports, and output directory. On success, shows clear next steps (try sample, create scenario, use web UI). Exit code 0 on pass, 1 on fail for CI/CD integration.

- **First-run welcome message** (`run.py`): Detects first run via `.initialized` marker in `output/` directory. Shows a welcome banner with numbered tips: try sample first, create your own scenario, use the web UI, run verify_install. Runs once per installation, not per scenario.

- **Setup status warning** (`src/charts.py`): Orange warning banner in projection HTML output when using placeholder/sample data. Detects: scenario slug is "starter" or "sample", person names are "Person 1"/"Person 2"/"Alex"/"Sam", scenario name is "Your Household Name", or description starts with "A household scenario". Links directly to the Edit Config page and Setup Panel. Warning disappears when user replaces placeholder values.

- **Quick Start section** (`README.md`): Moved to top of README (before "What It Does"). Three-step flow: 1) Install and Verify (with `verify_install.py`), 2) Try the Sample Scenario (recommended first step), 3) Create Your Own Scenario (copy starter or use web UI). Replaces separate "Getting Started Without Monarch" and "Quick Start (with Monarch)" sections.

### Changed

- **README structure**: "Getting Started" moved above feature descriptions for better onboarding flow. "Quick Start (with Monarch)" renamed to "Advanced: Using Monarch Money (Live Balance Sync)" and moved below the basic Quick Start. Reduced duplication between sections.

- **Project Structure listing** (`README.md`): Added `scripts/verify_install.py` to the file tree with description.

### Fixed

- **F-string syntax error** (`src/charts.py:1914`): Replaced inline conditional with escaped quotes (`switchTab(\\'simulation\\')`) with a pre-built `simulation_tab_html` variable to avoid backslash-in-f-string Python syntax error.

## 2026-07-02 (Windows Compatibility)

### Added

- **Cross-platform venv detection** (`src/monarch_bridge.py`): New `_mcp_python_binary()` function detects `sys.platform` and returns the correct Python binary path for Windows (`.venv\Scripts\python.exe`) vs Unix/macOS (`.venv/bin/python3`). Monarch users on Windows can now use the MCP integration by setting `MONARCH_MCP_PATH` to their Windows-style installation directory.

- **Windows compatibility guide** (`docs/windows-compatibility.md`): Comprehensive guide covering installation, synthetic mode setup, Monarch configuration on Windows, path handling, common issues, WSL2 option, and troubleshooting. Includes side-by-side command examples for PowerShell vs bash.

### Changed

- **README.md**: "Getting Started Without Monarch" and "Quick Start (with Monarch)" sections now split into Linux/macOS and Windows subsections with platform-specific commands (`cp` vs `copy`, `.venv/bin/python` vs `.venv\Scripts\python.exe`, etc.). Added explicit `MONARCH_MCP_PATH` setup instructions for Windows Monarch users.

- **`scenarios/starter.toml`**: Header comments updated to show both Linux/macOS and Windows commands for copying the template and running projections. Windows users now have clear guidance without needing to translate Unix commands.

- **`docs/ui-ideas.md`**: Windows Compatibility section marked as ✅ DONE with summary of what was fixed. Remaining work (optional enhancements like `--serve` flag) moved to "Summary of remaining work" subsection.

## 2026-07-01 (Phase 4 — New-scenario workflow)

### Added

- **`POST /api/new-scenario` endpoint** (`admin_app.py`): Creates a new scenario by reading `scenarios/starter.toml` as the source template and passing it through `create_scenario_from_content()` with the user-supplied name, slug, and description. Falls back to an inline minimal synthetic TOML if `starter.toml` is missing. Returns `{ok, slug, name}` on success; `409` on duplicate slug; `400` on missing fields.

- **"New from Template" button** (`templates/setup_panel.html`): Added to the action bar to the left of Clone Scenario. `initNewScenario()` prompts for name and slug, calls `api/new-scenario`, and redirects to the new scenario in the Setup Panel. Backend errors (duplicate slug, etc.) surface via `showError()`.

- **Clone-source warning** (`templates/setup_panel.html`): `initCloneScenario()` now checks `_accountsData.source_mode` before submitting the clone form. When the source scenario is Monarch-mode, a `confirm()` dialog warns the user that the clone will also require Monarch and suggests "New from Template" as the non-Monarch alternative. Clone proceeds or aborts based on the user's choice.

## 2026-07-01 (Phase 3 — Starter template and README)

### Added

- **`scenarios/starter.toml`**: Blank-slate household template for users without Monarch. `[data_source].mode = "synthetic"`, all balances at zero, every required field annotated with `← YOUR VALUE`. Correct TOML ordering (bare keys before sub-tables within each person block). Runs cleanly with zero balances out of the box. Versioned in git (excluded from the `scenarios/*.toml` gitignore via an explicit exception in `.gitignore`).

- **README "Getting Started Without Monarch" section**: Placed before the existing "Quick Start (with Monarch)" section. Covers: copy starter, fill in values, update slug, run projection, use the Synthetic Setup tab in the web UI, keep balances current manually, optionally connect Monarch later.

### Changed

- **`.gitignore`**: Added explicit `!scenarios/starter.toml`, `!scenarios/sample.toml`, `!scenarios/sample-a.toml`, `!scenarios/sample-b.toml` exceptions so shareable scenarios are tracked in git alongside personal scenarios that remain excluded.

- **`README.md`**: Opening description updated to note Monarch is optional. Project Structure section updated to list `starter.toml` and `sample.toml` with descriptions.

## 2026-07-01 (Phase 2 — Monarch-optional Setup Panel UI)

### Changed

- **`api/refresh-monarch` endpoint** (`admin_app.py`): Returns `503` with a clean JSON error message when the Monarch MCP binary is not present (uses the same `MCP_PYTHON.exists()` pre-flight check from Phase 1). No stack trace, no subprocess failure propagated to the browser.

- **Accounts tab mode-aware banner** (`templates/setup_panel.html`): After `initAccountsTab()` resolves, `applyAccountsTabModeState(source_mode)` is called. When `source_mode === "synthetic"`, a blue info banner is inserted above the account toolbar explaining the tab is inactive in synthetic mode. The "Refresh from Monarch" button is disabled (`opacity: 0.38`, `cursor: not-allowed`). When mode is `"monarch"`, the button stays enabled and no banner appears.

- **Two-way radio sync** (`templates/setup_panel.html`): `installSynthRadioHandlers()` now installs `change` listeners on both the quick-edit strip `ds_mode` radios and the Synthetic Setup tab `synth_ds_mode` radios. Any change to either group syncs the other, updates `toggleSynthInputs()`, and — if the Accounts tab is already loaded — calls `applyAccountsTabModeState()` to update the banner live without a page reload.

## 2026-07-01 (Phase 1 — Monarch-optional error handling)

### Added

- **Monarch-optional plan** (`docs/plans/2026-07-01-monarch-optional.md`): 5-phase implementation plan for making NWN fully usable without Monarch Money. Assessment of current gaps, phased task breakdown, dependency map, acceptance criteria, and pitfalls section. Phase 1 shipped in the same session; Phases 2–5 are documented and ready for handoff.

- **Pre-flight check in `fetch_raw_accounts()`** (`src/monarch_bridge.py`): If the MCP Python binary doesn't exist at its expected path, raises a clean `RuntimeError` with a plain-English explanation pointing to `data_source.mode = "synthetic"` as the fix, and the `MONARCH_MCP_PATH` env var as the path override. No subprocess is attempted. No Person 1-specific re-auth advice is shown.

- **`MONARCH_MCP_PATH` env var support** (`src/monarch_bridge.py`): `_mcp_root()` function reads `MONARCH_MCP_PATH` from the environment and uses it as the MCP server root, falling back to the hardcoded default `/opt/monarch-mcp-server`. `MCP_PYTHON` and `MCP_SRC` module-level constants are derived from this function so any user can point to their own install without modifying source code.

- **Clean error exit in `run.py`** (`run.py`): `fetch_raw_accounts()` call in `main()` is now wrapped in `try/except RuntimeError`. On failure: prints each line of the error message cleanly, lists the two alternatives (offline cache, synthetic mode), and calls `sys.exit(1)`. No Python traceback is shown to the user.

### Decisions

- **Monarch integration is now cleanly optional at the error-handling layer.** A user on a machine without Monarch, or with Monarch installed at a non-default path, receives an actionable message instead of a confusing subprocess failure. Status: Adopted.

## 2026-07-01

### Added

- **Config backup deduplication** (`admin_app.py`): Both `_backup_and_write()` and `_backup_and_write_toml()` now compare the current config content against the most recent backup before creating a new one. If unchanged, the backup write is skipped — preventing redundant backups from repeated no-op saves.

### Changed

- **Backup retention policy** (`admin_app.py`): `_prune_backups()` changed from count-based (`keep=10`) to time-based (`keep_days=14`, `keep_min=5`). Backups older than 14 days are pruned, but the 5 most recent are always protected regardless of age. Fixes issue where 10 saves in a single editing session would wipe out all historical backups for a scenario.

- **Scenario Setup Panel** (`templates/setup_panel.html`, `admin_app.py`): New structured config editor at `/finances/config/setup` with three sub-tabs:
  - **Quick-edit strip**: Data source radio, cash targets, returns, retirement years, drag-reorder withdrawal/surplus order chips, Save + Re-render.
  - **Data Sources & Accounts**: Account table from cache with category dropdowns, disabled checkbox, unmatched accounts section, explicit Refresh from Monarch button, Save Classification.
  - **Synthetic Setup**: Structured form for investable balances, non-investable assets, property values (add/remove), auto-detected liability balances from `[[liabilities]]`, Save Synthetic Settings.
- **7 new API endpoints** (`admin_app.py`): `GET /api/accounts`, `POST /api/save-classification`, `GET /api/synthetic-start`, `POST /api/save-synthetic-start`, `POST /api/save-quick-controls`, `POST /api/refresh-monarch`, `GET /api/data-source-status` — all backed by `tomlkit` for comment-preserving TOML writes.
- **`tomlkit` dependency** to `requirements.txt` and Docker image.

### Changed

- **Nginx config** (`/opt/hal-pages/default.conf`): `/finances/config` redirects to `/finances/config/setup`. Old raw editor stays at `/finances/config/` (trailing slash). Separate `/finances/config/api/` and `/finances/config/setup` location blocks for clean routing.
- **Docker image** rebuilt with tomlkit.
- **Setup panel fixes** (`templates/setup_panel.html`):
  - Status panel moved from bottom to top of page.
  - Source cell uses `display: inline-flex` on inner `<span>` (not `<td>`) for vertical alignment with other cells.
  - Unmatched rows produce 5 cells matching 5-column header (was 6 cells from duplicate source cell).
  - Added guidelines card explaining `ignore` vs `disabled` checkbox in the Data Sources tab.
  - Person retirement labels ("Person 1 Retires" / "Person 2 Retires") update dynamically from `person1.name`/`person2.name` in the TOML config.
- **Projection shell page** (`src/scenario_shell.py`): "Scenario Setup" primary button added to toolbar, linked to `/finances/config/setup?scenario=<slug>`. `run.py` passes `setup_url` parameter.
- **Quick-edit refinements** (`templates/setup_panel.html`, `admin_app.py`):
  - **Metadata section** at top with editable Plan Name, Description, read-only Slug + Rename Slug button, DEFAULT badge.
  - **People section** with name inputs, birth-year inputs, retires-year inputs, and age sliders (40-80) synced bidirectionally from birth year.
  - **Cash Target phase labels** changed to "Accumulation Phase", "Retirement Phase", "Survivor Phase" (25px wider inputs).
  - **Start/end year** inputs added to Assumptions & Years section.
  - Person names and retirement years moved to dedicated People section above Data Source.
- **Synthetic Setup tab UX** (`templates/setup_panel.html`): Balance inputs disabled (greyed) when data source is Monarch, enabled when Manual entry. Liability balances help text explains names are auto-detected from `[[liabilities]]` and match Monarch accounts by convention.
- **Grouped accounts display** (`templates/setup_panel.html`): Data Sources & Accounts tab groups matched accounts by category with section headers (── Cash (4) ──) in order: Cash → Taxable → Roth → Trad IRA → Real Estate → Vehicle → Liability → Ignore. Alphabetical sort within groups. Changing a category dropdown moves the row live to the correct group; empty groups collapse; group counts update automatically.
- **Owner column** (`templates/setup_panel.html`, `admin_app.py`): New Owner column between Category and Disabled with dropdown showing person names from Metadata + "n/a". Values stored as "person1"/"person2" matching TOML convention; API writes inline dicts when owner is set, plain strings otherwise. Dict-classified accounts (401k Person 1, OregonSaves) correctly show their owner pre-selected.
- **Selector brightness lowered** (`templates/setup_panel.html`): `.acct-category select` and `.acct-owner select` background changed to `#0d1524`.
- **All old-editor functions ported** (`templates/setup_panel.html`): Quick-panel action bar now has Validate, Save + Render All, Clone Scenario (prompt-based), and Delete Scenario (confirmation dialog with slug-typing). Delete disabled for default scenario.
- **Edit Scenarios button removed** (`src/scenario_shell.py`, `run.py`): Projection shell toolbar cleaned up — only "Scenario Setup" remains. `editor_url` parameter removed from `build_scenario_shell()`.
- **Definitions page link fixed** (`src/definitions_page.py`, `run.py`): "Open Config Editor" now points to `/finances/config/setup` instead of `/finances/config/`.
- **Cash Reserve tab** (`src/charts.py`): New projection tab between Liabilities and Assumptions. Plotly chart shows cash balance trace (blue), stepped phase-aware cash target (amber dashed), and below-target highlight (red, connectgaps=False) with phase-boundary vlines. Summary card below with per-phase target, minimum, years below, and status emoji.

## 2026-06-30

### Added

- **Deselect-all for column highlights** (`src/charts.py`): Double-click/double-tap any highlighted year header, click the "Account" rowlabel header, or press Escape to clear all column highlights.

- **`.data-col` attributes on all header and body cells** (`src/tables.py`): `_header_row()` emits `data-col='N'` and `data-year='Y'` on each `<th>`. `_data_row()` injects `data-col='N'` into each `<td>`. Required for cross-table column highlighting via `document.querySelectorAll('[data-col="N"]')`.

- **Mobile touch support for year highlighting** (`src/charts.py`): Event delegation on `document` with `e.target.closest('th[data-year]')` — works on both desktop and mobile regardless of DOM timing or scroll container nesting.

- **UI Engineering Lessons section in systemPatterns.md**: 8 hard-won lessons documented: sticky headers & overflow containers, header rowlabel pinning, overscroll dead space, dual-scroll sync, Plotly chart height matching, `overflow: clip` vs `hidden`, event delegation, `data-col` attribute requirements, and Tabulator.js evaluation.

### Changed

- **Surplus bar visualization removed** (`src/tables.py`): `_surplus_bar_cell()` function deleted. "Total Surplus Routed" row now uses standard `_data_row()` — simple bold numeric row like every other total row. The per-bucket breakdown is already visible in the individual Surplus Routing rows above it.

- **Cash Flow chart layout** (`src/charts.py`): Matched Portfolio chart exactly — height 420px (was 340px), margins `l=76,r=24,t=78,b=48` (was `l=80,r=24,t=72,b=48`), legend `bgcolor=rgba(0,0,0,0)` in Python layout, `Plotly.Plots.resize()` added after responsive relayout. Fixes legend-over-xaxis-title overlap and missing window-resize responsiveness on mobile.

- **Overscroll fix** (`src/charts.py`): `overflow: hidden` on `.datatable` clips cell content at the table boundary, preventing `scrollWidth` inflation from overflowing inline elements. Year column width increased 110→130px to prevent number clipping. JS scrollLeft clamping added as safety net.

- **Header rowlabel pinning** (`src/charts.py`): `syncHeaderScroll()` now applies `transform: translateX(scrollX)` to `th.rowlabel` and `boxShadow: scrollX + 'px 0 0 0 #182233'` to fill the translation gap.

- **Year-highlight handler** (`src/charts.py`): Switched from per-element listeners to event delegation on `document` — more reliable across DOM timing and scroll containers.

### Reverted

- **Tabulator.js migration** (commits `a035716` through `70d2119`): Evaluated Tabulator 6.3 for frozen columns and sticky headers. Rejected because Tabulator's `frozenColumns` and `headerVisible` require Tabulator's own internal scroll container, incompatible with full-height page-scrolled tables. Custom split-table approach restored from `a1e901c`.

### Decisions

- **Tabulator.js is a poor fit for full-height tables with page-level scrolling.** Context: Tabulator's sticky/frozen features need the table to be inside a Tabulator-managed viewport with internal scroll. NWN tables show all rows (no internal vertical scroll). Use native CSS/JS for page-scrolled tables; Tabulator is excellent for fixed-height viewport tables. Status: Adopted.

---

### Added

- **Liabilities Payoff Calendar** (`src/model.py`, `src/tables.py`, `src/charts.py`): New Liabilities tab between Gantt and Assumptions. Per-liability year-end balance columns (`liability_<slug>_balance`) stored in the DataFrame. Debt payoff Plotly trajectory chart (lines that stop at payoff via null insertion, payoff-year annotations, area fill). Amortization table with uniform column widths, payoff-year callout (✓), and type-colored row labels. Config-driven — works with any `[[liabilities]]` in the scenario TOML.

- **Hover tooltip cleanup** (`src/charts.py`): Removed redundant `<b>%{x}</b><br>` from every hovertemplate in all `hovermode="x unified"` charts (main net worth, cash flow, portfolio, liabilities, simulation). The shared x unified header already shows the year — repeating it per trace was clutter.

- **Main chart age-labels-as-annotations** (`src/charts.py`): Age labels separated from x-axis ticktext to fix hover tooltip inconsistency. Ages now rendered as independent Plotly annotations below the x-axis (y=-0.085 paper coords) at each 2-year tick. Ticktext shows just the year. Hover tooltip headers stay clean. Responsive JS hides age annotations below 1000px by toggling `annotations[N].visible`.

- **x-axis title standoff** (`src/charts.py`): Changed xaxis title from flat string to `dict(text="Year", standoff=28)` so the "Year" label can be independently positioned below tick labels and age annotations. Bottom margin bumped 88→100px (normal), 92→104px (compact).

### Changed

- **Debt payoff chart trace capping** (`src/charts.py`): After each liability's payoff year, subsequent balance values replaced with `None` so Plotly draws a gap instead of a flat zero line.

## 2026-06-29

### Added

- **Sticky table headers** (`src/charts.py`): Build-time table splitting via `_wrap_table_with_sticky_header()`. Each `<table class='datatable'>` is split into a `.sticky-header-wrap` (sticky header, no overflow ancestor → `position: sticky; top: 0` works) + `.table-scroll` (horizontal scroll container). Both tables use `table-layout: fixed` with explicit `<colgroup>` pixel widths (label=210px, each year=110px) so column alignment is guaranteed identical — no runtime measurement or clone-syncing needed.

- **Horizontal overscroll fix** (`src/charts.py`): Fixed by `table-layout: fixed` + explicit total width on both tables. `scrollWidth` now exactly matches sum of column widths — no overshoot past the last column. The `.table-scroll` wrapper handles all scroll/wheel/drag behavior.

### Changed

- **CSS** (`src/charts.py`): `.table-panel` loses `overflow-x: auto; cursor: grab` and gains `position: relative`. New `.sticky-header-wrap` (sticky, top:0, z-index:10, background/border-bottom) and `.table-scroll` (overflow-x:auto, cursor:grab, drag states). Split tables use `border-radius: 6px 6px 0 0` (header) and `border-radius: 0 0 6px 6px` (body) for continuous visual.

- **JS** (`src/charts.py`): Scroll/wheel/drag handlers now target `.table-scroll` instead of `.table-panel`. `syncLabels()` scoped to each `.table-scroll`'s child rowlabels. Year-highlight click handler unchanged — works across both tables via shared `data-col` attributes.

- **All datatable call sites** (`src/charts.py`): `accounts_html`, `cashflow_html`, `tax_html`, `portfolio_table_html` (×2), `table_html` (simulation) all pass through `_wrap_table_with_sticky_header()` in their respective build functions.

### Added

- **Favicon** (`src/charts.py`): Inline SVG favicon data URI in HTML `<head>` — dark rounded square with blue trend line over bar columns, matching the dark theme.

- **Mobile event-label defaults** (`src/charts.py`): On screens narrower than 768px, the chart now defaults to showing only key events (Show all unchecked, Keep key labels checked) on first load. User can toggle back manually.

- **Employee-only contribution columns** (`src/model.py`): New DataFrame columns `contribution_employee_trad_ira`, `contribution_employee_roth`, `contribution_employee_trad_ira_person1/2`, `contribution_employee_roth_person1/2` — employee-only retirement contributions excluding employer match.

### Changed

- **Cash Flow table** (`src/tables.py`): Per-person contribution rows now use employee-only columns and are labelled `Employee 401k/IRA — Person 1` / `Person 2`. Aggregate rows (`Traditional IRA / 401k contributions`, `Roth contributions`) also use employee-only totals so they match the sum of per-person rows. Employer match rows are shown separately. Per-person employer match rows now appear independently when non-zero (previously required both people to have non-zero match).

- **Household scenario TOMLs**: All 6 scenarios (default, comfortable, optimistic, restrictive, early-death-person1, early-death-person2) updated:
  - `retirement_contribution_percent` → 0.24 (hits $31K IRS cap from year 1)
  - `annual_401k_contribution_split` → 70/30 (trad/Roth)
  - Cash targets → $40K accumulation, $50K retirement, $30K survivor
  - Comments updated to match

- **Default scenario**: Stale comment on line 67 (`# 16%` → `# 24% of gross income ($31K IRS cap)`). Withdrawal policy comments updated.

### Fixed

- **Freed payment calculation** (`src/model.py`): All four sites where freed payments are computed (amortization payoff loop, SellHome liability payoff, auto_reduce active P&I) now use `monthly_base` (contractual P&I) instead of `monthly_total` (which included voluntary `monthly_extra`). Voluntary extra principal is no longer treated as permanently freed cash flow. Also added `monthly_base` to the liability state dict.

- **Event vlines hidden with annotations** (`src/charts.py`): `applyEventLabelVisibility()` JS now also toggles corresponding vline shapes when annotations are hidden. Previously only annotation text visibility was toggled, leaving vertical lines visible.

- **Cash Flow Roth contribution mismatch**: Total `Roth contributions` row was including employer-match Roth portions (5% of match via 95/5 split), creating a gap vs per-person rows. Fixed by making all aggregate contribution rows employee-only. The employer-match Roth portion ($391 in 2026) is now correctly contained within the `Employer match` row.

### Removed

- **Three early-mortgage scenario files**: `default-early-mortgage.toml`, `comfortable-early-mortgage.toml`, `optimistic-early-mortgage.toml` deleted. The early-mortgage scenario's `monthly_base` was also corrected to use `monthly_extra = 1000` before deletion.

### Added

- **Ordered-priority surplus routing** (`src/model.py`): `_apply_surplus_with_reserve_target` now distributes surplus as a strict priority chain via `*_surplus_order` instead of proportional-by-balance. Default order changed from `["taxable", "roth", "trad_ira"]` to `["roth", "taxable"]`. First non-excluded bucket receives ALL remaining surplus; if empty or excluded, falls through to the next. Cash remains the final backstop when no bucket in the order is available. Removed `_surplus_fallback_bucket` (no longer needed).

- **Roth IRA contribution caps on surplus routing** (`src/model.py`): New `_IRS_ROTH_IRA_LIMIT_*` constants, `_roth_ira_limit()` function (returns $7K under 50, $8K 50+ per person), and `_person_ira_contribution_to_roth()` helper. Household Roth surplus cap computed yearly: sum of per-person limits minus planned IRA contributions going to Roth. Applied via new `step_caps` parameter on `_apply_surplus_with_reserve_target`. Cap only active during accumulation (at least one person working); removed after both retire. Excess above cap spills to the next bucket in surplus_order.

- **SellHome reinvestment timing fix** (`src/model.py`): Pending reinvestments (e.g. `reinvest_to="taxable"`) are now processed inside the tax iteration loop, BEFORE the surplus sweep, so reinvestment proceeds reach their target bucket before the ordered priority applies. Previously ran after the loop, leaving no cash for reinvestment after the sweep.

- **Surplus Routing section in Cash Flow table** (`src/tables.py`): Dedicated rows for `Surplus to Roth`, `Surplus to taxable brokerage`, `Surplus to traditional IRA / 401k`. Data already tracked via `surplus_to_*` DataFrame columns.

### Changed

- **Scenario TOML surplus orders**: All 9 personal scenario files updated from `["taxable", "roth", "trad_ira"]` to `["roth", "taxable"]` for all three phases (accumulation, retirement, survivor). `restrictive.toml` kept its differentiated retirement/survivor `["taxable"]` orders unchanged. Sample scenarios left as-is.

### Fixed

- **Zero-surplus deficit branch owner-balance sync** (`src/model.py`): When a deficit is covered from cash and remaining excess cash is swept to a retirement bucket, `owner_balances` are now updated alongside the portfolio. Previously `_sync_retirement_bucket_totals` would overwrite the sweep with stale owner balances, causing Roth/trad_ira surplus additions to disappear during deficit years.

## 2026-06-24

### Fixed

- **Compare page — portfolio chart drop-to-zero bug.** Caused by JS `parseCSV()` using naive `line.split(',')` which split on commas inside quoted CSV fields. The `events_active` column contains comma-separated event labels (e.g. `🎉 Retirement (M), 🏛️ SS Begins (M)`), and 6 of 41 rows had those internal commas treated as field delimiters, shifting `taxable`/`trad_ira`/`roth` into wrong columns. Replaced with a state-machine `parseCSVLine()` parser in `src/scenario_shell.py` that tracks `inQuotes` and handles escaped quotes.
- **Compare page — delta chart bottom-left label overlap.** Y-axis `+$X.XXM` labels (wider due to `+` prefix) encroached on x-axis year labels in the corner. Increased `margin.l` (80→100), `margin.b` (56→72), `xaxis.ticklabelstandoff` (12→16), and `xaxis.title.standoff` (10→20) on the delta chart layout in `src/scenario_shell.py`.

## 2026-06-23

### Added

- **Phase 4 — Employer match and IRS 401(k) cap enforcement** (`src/model.py`, `src/tables.py`):
  - IRS employee elective deferral limits enforced at runtime: $23,500 base + $7,500 catch-up at age ≥ 50 (2025 values). Update `_IRS_401K_LIMIT_BASE` / `_IRS_401K_CATCHUP_EXTRA` in `src/model.py` annually.
  - New per-person config field `annual_401k_employer_match` (flat annual $). Always prefunded; routes through same `annual_401k_contribution_split` as employee. Person 1's household value: $5,688/yr, set in all 9 household scenario TOMLs.
  - New projection DataFrame / sidecar columns: `employer_match_total`, `employer_match_person1`, `employer_match_person2`, `person1_401k_over_irs_cap`, `person2_401k_over_irs_cap`.
  - Cash Flow tab: dedicated employer match row; amber ⚠ cap-exceeded warning banner.
  - Scenario Parameters: `401k employer match (annual)` diff row per person.
- **Scenario comparison page** (`src/scenario_shell.py`):
  - `compare.html` deployed at `/finances/compare.html` — reads sidecar CSVs and `simulation_summary.json` at runtime.
  - Scenario chip toggles (stable colour per slug, min 2 active), mode selector (deterministic / historical / monte_carlo).
  - Three Plotly charts: Total Net Worth trajectory, Investable Portfolio trajectory, Net Worth Delta (scenario − default).
  - KPI table with delta highlighting vs default; MC mode adds probability of success, worst-decile terminal NW, P10/P90, median first failure year, peak pressure rate.
  - Deep-linking via `?a=slug&b=slug` URL params; shell "Compare Scenarios" button pre-scopes to active vs default.
- **Scenario rename** (`admin_app.py`, `templates/config_editor.html`): `POST /rename-scenario` rewrites `[scenario]` block, moves TOML if slug changes, triggers offline render, redirects. Rename fields + button in config editor (disabled on default scenario).
- **Scenario deletion** (`admin_app.py`, `templates/config_editor.html`): `POST /delete-scenario` with slug-confirmation dialog; blocks deletion of default scenario; removes TOML + rendered output; triggers manifest refresh.
- **Two share-safe synthetic demo scenarios**: `sample-a.toml` (moderate: 7% equity, retirement 2038/2043, $82K/yr spending) and `sample-b.toml` (growth: 8.5% equity, retirement 2035/2037, $98K/yr, delayed SS to 70, $6K employer match). Both use Alex & Sam personas.

### Fixed

- Simulation tab legend responsive fix: `nwn-simulation` block added to `applyResponsiveChartLayout()` — legend moves below chart at ≤900px.
- Shell page: "Refresh Frame" button hidden on screens ≤980px; bracketed `[Mode]` suffix removed from scenario description text.
- Compare page: mode selector CSS background shorthand was malformed (missing comma between gradient layers), causing white fallback. Fixed to match shell page pattern.
- Compare page: y-axis title overlap fixed — `automargin: true` + `margin.l = 80` required alongside `standoff`; `standoff` alone is insufficient when left margin is too narrow.

---

## 2026-06-19 to 2026-06-22

### Added

- Monte Carlo simulation mode: seeded multi-run engine, `num_runs`, `seed`, `portfolio_return_volatility`; probability-band charts; stochastic KPI strip; Simulation tab with outcome-timing chart and yearly outcomes table.
- Historical-sequence simulation mode via `simulation.historical_returns_path` CSV; bundled starter dataset at `config/return_sequences/us_balanced_returns.csv`; turnkey without a user-supplied file.
- Configurable stochastic success/failure via `[monte_carlo.success]`: `failure_mode`, spending-funded threshold, home-equity/debt allowances, grace-period months.
- Normalized `ProjectionResult` contract in `src/model.py` shared by deterministic, Monte Carlo, and historical modes.
- Richer stochastic summary metrics: probability of success, spending shortfall, liquid depletion, net worth below zero, home-equity rescue; median/worst-decile terminal NW; first-failure distribution.
- Stochastic outcomes sidecar: `simulation_outcomes_yearly.csv` per run.
- Tax engine refactor: explicit yearly `YearlyTaxInputs` / `YearlyTaxOutputs` contracts in `src/tax_model.py`; `tax_breakdown_yearly.csv` sidecar; dedicated `Tax` tab in projection page.
- Federal bracket-based ordinary-income tax + Oregon state tax layer; SS provisional-income banding; configurable filing status per lifecycle phase; shared tax tables in `config/tax_tables/`.
- RMD modeling via `[taxes.rmd]`: forced traditional-account withdrawals from IRS life-expectancy factors.
- Richer account mechanics: taxable brokerage tracks cost basis vs. unrealized gains; Roth tracks contribution basis vs. earnings; optional basis seeding via `taxable_cost_basis`, `roth_contribution_basis`.
- Owner-level retirement bucket split: `trad_ira_person1/person2`, `roth_person1/person2` through projection pipeline; Accounts and Portfolio show per-person split; labels use configured person display names.
- Per-person `annual_401k_contribution_split` for routing employer-plan contributions proportionally between traditional and Roth.
- Account-level `owner` and `opening_balance_split` metadata in `[accounts]` inline tables for Monarch reclassification.
- `Expense` event `funding = "cash_reserve_first"` override; `expense_kind = "mandatory" | "discretionary"` categorisation.
- `SpendingShift` event type (`mode = "replace"`) for baseline spending regime changes.
- Survivor modeling improvements: survivor phase starts immediately after death; widow/er SS step-up via `survivor_ss_start_age`.
- Pre-retirement spending explicit precedence chain; `spending_basis = "real" | "nominal"` CPI indexing.
- `annual_take_home_is_net_of_retirement_contributions` payroll-prefunded flag.
- Phase-specific withdrawal policy (`[withdrawal_policy]`): per-phase cash targets, configurable withdrawal and surplus order.
- `SellHome` / `BuyHome` event improvements: proceeds preserved in cash; optional `reinvest_to`; real-estate property state tracking; `real_estate_appreciation` separate from CPI.
- Recurring events via `repeat_every_years` / `repeat_until_year` / `repeat_count`; `chart_first_occurrence_only` flag.
- Scenario comparison infrastructure: `compare.html`, deep-linking, delta chart (shipped 2026-06-23; listed here for completeness).
- Static definitions/reference page (`definitions.html`) linked from shell, projection pages, and config editor.
- Config editor: scenario clone, delete, rename; async render jobs with progress overlay; `Save + Render All`; timestamped backups; scenario-scoped projection/editor URL propagation.
- Public shell page: two-dimensional scenario + mode selector; iframe with version nonce; `Refresh Frame` control.
- Share-safe sample scenario (`scenarios/sample.toml`) with synthetic balances.
- `ignidash-comparative-analysis.md` and `ignidash-feature-port-plan.md` added to `docs/`.

### Fixed / Changed

- Main chart: 2-year x-axis ticks; age labels below year ticks; configurable chart title via `[display].projection_title`; event-label wrap and control strip.
- Gantt: denser row pitch, milestone vs span semantics, liability payoff milestones from projection output, survivor-period band, centered legend.
- Scenario Parameters: baseline-diff emphasis, `Show only differences` toggle, `Retirement ownership snapshots` card, `Tax output snapshot` card.
- Assumptions tab: baseline-diff support and `Show only differences` toggle.
- Horizontal table UX: JS `translateX(scrollLeft)` frozen first column + section bands, grab-to-pan, wheel-to-horizontal scroll.
- Portfolio tab: investable-only chart, projected-balances table, zero-taxable display cue, no cash bucket.
- KPI strip above main chart: Net Worth (EOY), Net Worth at Retirement, Retirement Age, Net Worth at End.
- `cash_return` separate from blended investable return; `wages.wage_tax_treatment` config.
- Cohesive dark theme across chrome, tables, and all Plotly charts.

