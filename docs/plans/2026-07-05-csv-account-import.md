# CSV Account Balance Import

**Date:** 2026-07-05
**Status:** Proposed
**Feature branch:** `feature/csv-import`

## Overview

Add a new `csv_import` data source mode that lets users upload a CSV of account balances
exported from Monarch Money (or any app producing the same column layout), assign account
types via the existing classification UI, and re-import (update) CSV files later while
preserving previously assigned types.

This fills the final gap in the Monarch-optional roadmap (Phase 5 — Structural / CSV),
making the application fully usable without any Monarch subscription.

## Motivation

- Monarch Money users who want a local tool without a live Monarch connection
- Users of other financial apps that can export `Date,Balance,Account` CSV
- Hosted-service users who need to bring their own data
- Self-hosted users who don't want to maintain the Monarch MCP dependency

## Design

### New data source mode: `csv_import`

A third value for `[data_source].mode` alongside `monarch` and `synthetic`.

### TOML storage

Two sections, cleanly separating balance data from classification metadata:

```toml
[data_source]
mode = "csv_import"

[csv_source]
last_import = "2026-07-05"

[csv_source.accounts]
"Checking - Joint" = 5432.10
"Savings - Joint" = 12345.67
"Capital One Venture" = 25000.00
"Vanguard Roth IRA" = 55000.00
"Vanguard Trad IRA" = 250000.00
"Home Mortgage" = 280000.00

[accounts]
"Checking - Joint" = "cash"
"Savings - Joint" = "cash"
"Capital One Venture" = {category = "cash", owner = "person1"}
"Vanguard Roth IRA" = {category = "roth", owner = "person1"}
"Vanguard Trad IRA" = {category = "trad_ira", owner = "person1"}
"Home Mortgage" = "liability"
```

**Why separate sections:**
- `[csv_source.accounts]` is balance data, overwritten on re-import
- `[accounts]` is classification data, preserved across imports
- New accounts on re-import appear in `[csv_source.accounts]` but have no entry
  in `[accounts]` → flagged as unclassified

**Why not extend `[synthetic_start]`:**
- `[synthetic_start]` uses aggregated bucket totals (e.g. `taxable = 80000`).
  Adding per-account data there would mix two different granularity models
  and make the TOML harder to reason about.
- `[synthetic_start]` remains useful for quick manual testing and blank-slate
  templates where per-account details don't matter.

## Data Flow

### First import

```
CSV Upload
    │
    ▼
csv_importer.py::parse_csv()
  • Parse rows: Date,Balance,Account
  • Group by Account name
  • Extract latest balance per account (max date wins)
  • Return list[{name, balance}]
    │
    ▼
POST /api/csv-upload
  • Parse, classify-check
  • Return: {accounts: [{name, balance, classified: bool}], source_type: "csv"}
    │
    ▼
Setup Panel UI
  • Show preview table with current classification status
  • New/unknown accounts show as "unclassified"
  • User assigns categories via dropdown (same pattern as Data Sources tab)
    │
    ▼
POST /api/save-csv-source
  • Write [csv_source] section (last_import + [csv_source.accounts])
  • Write [accounts] section with classifications
  • Switch data_source.mode to "csv_import"
```

### Re-import (Update)

```
CSV Upload (same endpoint)
    │
    ▼
csv_importer::merge_accounts(old_accounts, new_csv)
  • For each name in new CSV:
    - If name exists in old [csv_source.accounts]:
      → Update balance, keep classification from [accounts]
    - If name is new (not in old accounts):
      → Add to result, mark as unclassified
  • For each name in old accounts but NOT in new CSV:
    → Flag as potentially removed (warn user, do not auto-delete)
    │
    ▼
Return three lists to UI:
  1. Existing accounts (balance updated, classification preserved)
  2. New accounts (need classification)
  3. Possibly removed accounts (user can confirm deletion)
    │
    ▼
User reviews, assigns types to new accounts, confirms removals
    │
    ▼
POST /api/save-csv-source (writes updated state)
```

### Model execution

```python
# In run.py
def _csv_inputs_from_config(config: dict) -> tuple[dict, dict, dict, dict, dict, dict]:
    """
    Build portfolio/extras/liability/owner/basis dicts from [csv_source.accounts]
    + [accounts] classification. Mirrors the shape returned by monarch_bridge.py
    and _synthetic_inputs_from_config().
    """
    csv_accounts = config.get("csv_source", {}).get("accounts", {})
    accounts_section = config.get("accounts", {})

    portfolio = {"taxable": 0.0, "trad_ira": 0.0, "roth": 0.0, "cash": 0.0}
    extras = {"home_value": 0.0, "vehicles": 0.0, "other": 0.0}
    # ... classification + bucketing logic same shape as monarch_bridge::classify_accounts()
    return portfolio, extras, liability_balances, property_values, retirement_owner_balances, basis_seeds
```

The model engine (`model.py`) is **unchanged** — it already accepts the same
portfolio/extras dict shape regardless of source.

## CSV Format

**Supported column layout (initial, Monarch-optimized):**

```
Date,Balance,Account
2026-01-05,5432.10,Checking - Joint
```

- `Date`: YYYY-MM-DD or any common date format parseable by `dateutil.parser`
- `Balance`: numeric (positive for assets, negative for debts — we store absolute)
- `Account`: display name (string)

**Future generalization:** The column-mapping logic lives in one function so a
column-picker UI can be added later without changing the rest of the system.

## New API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/csv-upload` | Accept CSV file, parse, return accounts + classification status |
| `POST` | `/api/save-csv-source` | Save `[csv_source]` section + `[accounts]` classification to TOML |
| `GET` | `/api/csv-source` | Return current `[csv_source]` data + per-account classification status |

### POST /api/csv-upload

**Request:** `multipart/form-data` with `file` field containing the CSV,
plus optional `scenario` query param.

**Response:**
```json
{
  "ok": true,
  "accounts": [
    {"name": "Checking - Joint", "balance": 5432.10, "classified": true, "category": "cash"},
    {"name": "New Vanguard Account", "balance": 12000.00, "classified": false, "category": null}
  ],
  "new_accounts": ["New Vanguard Account"],
  "total_accounts": 12,
  "import_date": "2026-07-05",
  "warnings": ["Account 'Old Checking' present in config but not found in CSV"]
}
```

### POST /api/save-csv-source

**Request:**
```json
{
  "scenario": "default",
  "accounts": [
    {"name": "Checking - Joint", "balance": 5432.10, "category": "cash", "owner": "n/a"},
    {"name": "New Vanguard Account", "balance": 12000.00, "category": "roth", "owner": "person1"}
  ]
}
```

**Response:** `{"ok": true}` or error.

### GET /api/csv-source

**Response:**
```json
{
  "ok": true,
  "data_source_mode": "csv_import",
  "csv_source": {
    "last_import": "2026-07-05",
    "accounts": {"Checking - Joint": 5432.10, ...}
  },
  "accounts_status": [
    {"name": "Checking - Joint", "balance": 5432.10, "classified": true, "category": "cash"},
    {"name": "New Vanguard Account", "balance": 12000.00, "classified": false, "category": null}
  ]
}
```

## UI Changes

### Setup Panel — Data Sources & Accounts tab

The existing "Data Sources & Accounts" sub-tab already has:
- Account table with rows grouped by category (Cash, Taxable, Trad IRA, Roth, etc.)
- Category and Owner dropdowns per account
- Unmatched accounts section at bottom

**New behavior when `mode = "csv_import"`:**
- The CSV import section appears above the accounts table
- **File upload area** — drag-and-drop or click to select CSV
- **Preview table** — shows parsed accounts, their balances, and classification status
- **Classify new accounts** — inline dropdowns for unclassified names
- **Confirm import** button writes everything

**New accounts** appear in the unmatched section with "(new)" badge, awaiting
classification. **Existing accounts** show their current classification and
updated balance highlighted with a subtle indicator (e.g. "✓ balance updated").

### CSV Upload widget in the Data Sources tab

```
┌────────────────────────────────────────────────────────────────────┐
│  Data Source: ● Monarch  ○ Manual Entry  ○ CSV Import            │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ 📁 Import from CSV                                         │   │
│  │ Drag & drop your Monarch export CSV here, or click to      │   │
│  │ select file. Expected format: Date,Balance,Account         │   │
│  │ [Choose File] ✓ last-import.csv                            │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Preview (12 accounts found) ───────────────────────────────┐ │
│  │ Account              │ Balance      │ Type        │ Owner  │ │
│  │────────────────────────────────────────────────────────────┤ │
│  │ Checking - Joint     │ $5,432.10   │ ✓ cash      │ n/a    │ │
│  │ Savings - Joint      │ $12,345.67  │ ✓ cash      │ n/a    │ │
│  │ Vanguard Roth IRA    │ $55,000.00  │ ✓ roth      │ p1     │ │
│  │ 🆕 New CapOne Card   │ $2,500.00   │ [ ▼ Select ]│ [ ▼ ]  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  [Cancel]  [Import & Save]                                        │
└────────────────────────────────────────────────────────────────────┘
```

### Re-import diff view

After a second CSV upload, show a "Changes since last import" summary:

```
┌─ Import Update ──────────────────────────────────────────────────┐
│  ✓ 8 existing accounts — balances updated, types preserved       │
│  🆕 2 new accounts — needs classification                       │
│  ⚠ 1 account removed from CSV — "Old Checking"                  │
│                                                                  │
│  [Classify New] [Confirm Import] [Cancel]                        │
└──────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1 — Core engine (no UI yet)

**Branch:** `feature/csv-import`

**File: `src/csv_importer.py`** (new module, ~200 lines)

1. `parse_csv(file_path: str) -> list[dict]`
   - Parse CSV rows into `[{name, balance, date}]`
   - Group by `name`, keep row with max date per group
   - `balance` always stored as positive (abs for negative values which
     Monarch uses for debts)
   - Return sorted list by name

2. `merge_accounts(old_accounts: dict, new_accounts: list, existing_classifications: dict) -> dict`
   - Returns `{"updated": [...], "new": [...], "maybe_removed": [...]}`
   - `updated`: in both old and new → new balance, preserved classification
   - `new`: in new only → no classification
   - `maybe_removed`: in old only → flagged for user review

3. `build_csv_starting_inputs(config: dict) -> tuple`
   - Mirrors `_synthetic_inputs_from_config()` return shape
   - Reads `[csv_source.accounts]` + `[accounts]`
   - Classify and aggregate into portfolio/extras/liability/property/owner/basis

**File: `run.py`** (~30 lines)

- Add `data_source.mode == "csv_import"` branch in `main()`:
  ```python
  elif data_source_mode == "csv_import":
      from src.csv_importer import build_csv_starting_inputs
      portfolio, extras, liability_balances, property_values, \
          retirement_owner_balances, basis_seeds = build_csv_starting_inputs(config)
  ```
- This branch sits alongside the existing `monarch` and `synthetic` branches

**Tests: `tests/test_csv_importer.py`**

- Parse a Monarch-style CSV string
- Parse with multiple rows per account (keep latest)
- Merge with existing classifications
- Handle empty CSV
- Handle negative balances (debt → abs)

### Phase 2 — API endpoints

**File: `admin_app.py`** (~150 lines)

- `GET /api/csv-source`
- `POST /api/csv-upload` — receives `multipart/form-data`, saves temp file,
  parses via `csv_importer.parse_csv()`, merges with existing
- `POST /api/save-csv-source` — writes `[csv_source]` + `[accounts]` to TOML,
  sets `data_source.mode = "csv_import"`

**Backup pattern:** Use the existing `_backup_and_write_toml()` for all TOML
writes.

### Phase 3 — UI (Setup Panel)

**File: `templates/setup_panel.html`** (~200 lines)

- Add "CSV Import" radio option to the Data Source selector
- When CSV Import is selected, show the upload + preview section
- Upload flow: file input → POST to `/api/csv-upload` → render preview table
- Preview table: account name, balance, category dropdown (pre-filled for
  existing, blank for new), owner dropdown
- "Import & Save" button → POST to `/api/save-csv-source`
- On re-import: show diff summary (see mockup above)

### Phase 4 — Edge cases & cleanup

- **Balance zero vs unset:** Accounts with $0 balance from CSV are treated as
  valid (user may have an empty account)
- **CSV with no rows:** Graceful error message
- **CSV with missing columns:** Parse error with diagnostic
- **Switching modes:** Changing from `csv_import` back to `monarch` or
  `synthetic` preserves the `[csv_source]` section but doesn't read it
- **Template scenarios:** `starter.toml` and `starter-couple.toml` keep
  `mode = "synthetic"`. Users choose `csv_import` after creation.
- **Large CSVs:** If the CSV has many thousands of rows (years of daily data),
  parsing and grouping handles it efficiently (O(n) pass, O(unique_accounts)
  memory)

## What Does NOT Change

| Component | Reason |
|-----------|--------|
| `model.py` | Already accepts portfolio/extras dicts from any source |
| `charts.py` | Renders model output, source-agnostic |
| `tables.py` | Same |
| `config_loader.py` | Already merges scenario sections |
| `scenarios.py` | Discovery/manifest unchanged |
| `monarch_bridge.py` | Unchanged — still handles `mode = "monarch"` |
| `[synthetic_start]` | Unchanged — still functional for manual-only users |
| `nginx config` | Already proxies all API paths |
| Existing API endpoints | No changes needed |
| Dockerfile | No new dependencies (csv is stdlib) |

## Versioning

- MINOR bump (v1.1.0 → v1.2.0) — new feature, backward-compatible
- `[csv_source]` is an optional section — old configs still parse

## Future Extensions (not in scope)

| Feature | When |
|---------|------|
| General CSV column mapping UI | V2 if other apps' CSV formats are requested |
| Multiple CSV import presets (Monarch, Mint, YNAB, etc.) | V2 |
| Full daily time series ingestion | V2 — could seed growth metrics |
| Auto-detect column layout from header row | V2 |
| Historical balance chart from CSV data | Separate feature |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large CSVs exceed request size limit | Increase nginx `client_max_body_size` or parse server-side in chunks |
| Account names change between exports (e.g. "Checking" → "Joint Checking") | User must manually re-classify; show name diff in re-import review |
| Negative balances in CSV (loans, credit cards) | `parse_csv()` takes `abs()`; liability accounts in `[accounts]` exclude them from investable |
| Monarch updates CSV column layout | The parser is strict about header row; wrong columns = clear error |
