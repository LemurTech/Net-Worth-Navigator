# Setup Panel Single-Tab Refactor

**Date:** 2026-07-06
**Branch:** `feature/csv-import`

## Goal

Replace the current two-row layout (Quick Controls panel above + tabs below) with a single tabbed interface: **Metadata | Accounts | Raw TOML**. All action buttons live in a global bar below the tabs.

## Current Layout

```
QUICK PANEL (name, people, data source, cash targets, assumptions, priorities, SAVE/VALIDATE/RENDER buttons)
    |
TABS: Raw TOML | Data Sources & Accounts | Manual Setup
    |           |                          |
    textarea    accounts table + CSV       synth inputs
```

## New Layout

```
TABS: Metadata | Accounts | Raw TOML
    |           |              |
    name,      data source     textarea
    people,    selector +
    cash       contextual
    targets,   content
    assump-    (Monarch table /
    tions,     CSV import /
    priorities synthetic)
    |
GLOBAL ACTION BAR: [Save] [Validate] [Save+Render] [Render All] [New Template]
```

## Tasks

### Task 1: HTML — restructure into 3 tabs

1. Extract Quick Panel content → Metadata tab content (everything except Data Source radios)
2. Move Data Source radio selector → top of Accounts tab
3. Merge Manual Setup tab content → Accounts tab (shown when "Manual entry" selected)
4. Create global action bar div below tabs
5. Remove duplicate save buttons from old tab-actions

### Task 2: JS — update tab initialization

1. Add `initMetadataTab()` to populate metadata fields
2. Remove `initQuickEdit()` → replace with `initMetadataTab()` that reads same field IDs from new parent
3. Remove `syncDataSourceRadios()` → only one radio group now
4. Remove `setAccountsTabVisibility()` / `setManualSetupTabVisibility()` → Accounts tab always visible
5. Simplify `applyAccountsTabModeState()` → just adjusts Accounts tab content, no hiding tabs
6. Global Save button dispatches to correct save handler based on active tab

### Task 3: Wire everything and remove dead code

1. Remove old quick-panel container and its CSS
2. Remove Manual Setup tab button
3. Rename "Data Sources & Accounts" → "Accounts"
4. Test: all existing functionality still works after the moves
