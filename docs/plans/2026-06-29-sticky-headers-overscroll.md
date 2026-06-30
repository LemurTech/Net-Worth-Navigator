# Sticky Table Headers & Overscroll Fix — Implementation Plan

> **For Hermes:** Implement directly in this session.

**Goal:** Fix two table UX issues: (1) sticky headers that follow vertical page scroll, and (2) horizontal overscroll into dead space past the last column.

**Architecture:** Build-time table splitting. At page generation time, each `<table>` is split into a sticky header table (no overflow ancestor → `position: sticky` works) and a scrollable body table. Both use `table-layout: fixed` with explicit `<colgroup>` pixel widths so column alignment is guaranteed identical.

**Tech Stack:** Python 3.11+ (stdlib regex / html), inline CSS, vanilla JS.

---

## Background

### Why sticky headers are hard here
- `.table-panel` has `overflow-x: auto` — it's a CSS scroll container
- `position: sticky` inside a scroll container is relative to that container, not the viewport
- The overflow container only scrolls horizontally → sticky never engages

### Why overscroll happens
- Table has `width: 100%` with `table-layout: auto` → stretches to fill container + content pushes wider
- `scrollWidth` includes full rendered width, which may exceed the actual last-pixel boundary of the last column

### Solution: Build-time split + fixed layout
- Split each `<table>` into header table + body table
- Header sits in a `position: sticky` wrapper (no overflow ancestor = sticks to viewport)
- Body sits in `.table-scroll` (overflow-x: auto = horizontal scroll)
- Both use `table-layout: fixed` with explicit `<colgroup>` pixel widths
- Column widths guaranteed identical → no alignment drift

---

## Task 1: Add `_wrap_table_with_sticky_header()` helper to `src/charts.py`
- Extract `<thead>` and `<tbody>` from table HTML via regex
- Count year columns from thead
- Generate `<colgroup>` with label=210px, each year=110px
- Wrap in sticky header + scrollable body markup

## Task 2: Update `build_chart()` to apply the wrapper
- After each table function call, pass result through `_wrap_table_with_sticky_header()`
- Update the HTML template: `.table-panel` divs no longer need `table-panel` class (scroll is on inner `.table-scroll`)

## Task 3: CSS updates in `_TABS_CSS`
- Remove `overflow-x: auto; cursor: grab` from `.table-panel`
- Add `.sticky-header-wrap` styles (sticky, top:0, z-index, background)
- Add `.table-scroll` styles (overflow-x: auto, cursor: grab, drag styles)
- Adjust table border-radius to apply to header and scroll areas
- Ensure `.header-only` table has no bottom border/radius
- Ensure `.body-only` table has no top border/radius

## Task 4: JS updates in `_TABS_JS`
- Change scroll/wheel/drag handlers from `.table-panel` to `.table-scroll`
- Update `syncLabels()` to find `.body-only` table rowlabels (not header table)
- Keep year-highlight logic unchanged (works across both tables via `data-col`)

## Task 5: Overscroll fix
- Handled by `table-layout: fixed` + explicit total width → `scrollWidth` exactly matches content boundary
- No additional changes needed beyond the table-splitting

## Task 6: Test
- Run `.venv/bin/python run.py --offline --scenario default`
- Inspect `output/scenarios/default/deterministic/projection.html`
- Verify: sticky header behavior, column alignment, horizontal scroll stops at last column
- Deploy: `cp` to `/srv/web-projects/finances/scenarios/default/deterministic/`

## Task 7: Update Memory Bank
- Update `activeContext.md` with new task status
- Append to `progress.md`
