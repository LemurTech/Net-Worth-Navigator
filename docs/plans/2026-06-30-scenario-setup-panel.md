# Scenario Setup Panel — Implementation Plan

> **Status:** Design approved. Ready for implementation.
> **See also:** `docs/ui-ideas.md` (ideas #1-4), `src/admin_app.py`, `templates/config_editor.html`

**Goal:** Replace the standalone raw TOML config editor with a unified Scenario Setup page that combines a quick-edit strip, a structured Data Sources & Accounts sub-tab, a Synthetic Setup sub-tab, and the existing raw TOML editor — all on one page, deploying alongside the old page until ready to swap.

**Non-goal:** This phase does not add CSV import, manual account creation from scratch, or full account lifecycle management. The architecture is designed to support those later, but they are out of scope.

**Architecture:** A new route `/finances/config/setup` on the existing FastAPI app (`admin_app.py`) serving a new Jinja2 template (`templates/setup_panel.html`). The old route `/finances/config/` stays untouched. Both routes share the same backend (config load/save/validate, backup, re-render). The new page calls new API endpoints on the same app. `tomlkit` is the only new Python dependency — it enables surgical section writes without destroying TOML comments or formatting.

**Deployment Strategy:** Develop and test locally by running `admin_app.py` on a separate port while the production container serves the old page. When ready, swap nginx to point `/finances/config/` to the new route (or redirect to `/finances/config/setup`). No branch needed, no dev environment.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, `tomlkit`, existing config-loading and re-render machinery in `admin_app.py`. No changes to `run.py`, `model.py`, `charts.py`, `tables.py`, `scenario_shell.py`, or any projection code.

---

## Task 1: Add `tomlkit` dependency and rebuild container

**Objective:** Install `tomlkit` in the project venv and the Docker container so the new API endpoints can use it.

**Files:**
- Modify: `pyproject.toml` (if it exists) or create/adjust requirements list
- Modify: `Dockerfile.config-editor`

**Steps:**
1. Install `tomlkit` in the project venv: `.venv/bin/pip install tomlkit`
2. Add `tomlkit` to any pinned requirements file or `pyproject.toml`
3. Add `tomlkit` to `Dockerfile.config-editor`'s pip install step
4. Rebuild the Docker image: `docker compose build nwn-config-editor`
5. Verify the old page still works at `/finances/config/`

**Dependencies:** None.

**Verification:** Import `tomlkit` from within the container shell; confirm round-trip TOML edit preserves comments.

---

## Task 2: Add API endpoints to `admin_app.py`

**Objective:** Add the backend endpoints that the new Setup page will call — account listing, section-specific TOML writes, synthetic-start read/write, data-source diagnostics.

**Files:**
- Modify: `src/admin_app.py`

**Endpoints to add:**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/accounts` | Return classified Monarch/cached accounts list + categories + cache timestamp |
| POST | `/api/save-classification` | Save `[accounts]` and `disabled = [...]` via `tomlkit` |
| GET | `/api/synthetic-start` | Return current `[synthetic_start]` values |
| POST | `/api/save-synthetic-start` | Save `[synthetic_start]` and toggle `data_source.mode` |
| POST | `/api/save-quick-controls` | Save individual quick-edit fields (cash targets, returns, years, etc.) |
| POST | `/api/refresh-monarch` | Trigger explicit Monarch re-fetch, return updated account list |
| GET | `/api/data-source-status` | Return data source diagnostics per account (source, cache age, warnings) |

**Design notes for each:**

- **GET `/api/accounts`**: Returns accounts from cache (or empty if none). Includes `source: "cached"`, `cache_timestamp`, and `account_classification` from the TOML. Never triggers Monarch fetch.
- **POST `/api/save-classification`**: Accepts `{accounts: [{name, category, disabled}]}`. Uses `tomlkit` to open the scenario TOML, replace the `[accounts]` section entries and `disabled = [...]` list, write back. Preserves all other sections and comments.
- **GET `/api/synthetic-start`**: Returns the current `config.get("synthetic_start", {})` merged with empty defaults for missing buckets.
- **POST `/api/save-synthetic-start`**: Accepts `{data_source: "monarch"|"synthetic", balances: {...}}`. Uses `tomlkit` to set `data_source.mode` and `[synthetic_start]`. If data_source is "synthetic" and starting balances are empty, return a validation error.
- **POST `/api/save-quick-controls`**: Accepts individual field updates like `{cash_target_accumulation: 40000, stock_return: 0.07, ...}`. Each field maps to a known TOML key path. Uses `tomlkit` for targeted key writes.
- **POST `/api/refresh-monarch`**: Calls `fetch_raw_accounts()` from `monarch_bridge.py`, reclassifies, saves to cache, returns the updated account list + timestamp. Show a progress indicator.
- **GET `/api/data-source-status`**: Returns per-account source info: `{account_name: {source: "cache"|"synthetic", cache_age_days: N, warning: null}}`. If Monarch auth has failed, that's noted here.

**Dependencies:** Task 1 (tomlkit installed).

**Verification:** Call each endpoint with curl or in-browser fetch. Confirm TOML is modified correctly and comments are preserved. Confirm backup file is created on writes.

---

## Task 3: Build the quick-edit panel

**Objective:** Create the always-visible strip at the top of the new Setup page with structured controls for the 5 most-frequent levers.

**Files:**
- New: `templates/setup_panel.html` (start building it section by section)

**Sections:**

### Data source selector
```
Data source: ○ Monarch (live/cached)    ● Manual entry (synthetic)
```
Radio buttons. Switching to Manual entry auto-selects the Synthetic Setup tab below. Uses existing `data_source.mode` TOML key.

### Cash targets
```
Accumulation: [ $40,000 ]   Retirement: [ $50,000 ]   Survivor: [ $30,000 ]
```
Three inline number inputs with reset-to-defaults link.

### Returns
```
Stock return: [  7.0% ]   Bond return: [  4.0% ]
```
Two percent inputs.

### Retirement year (per person)
```
Person 1 retires: [ 2033 ]   Person 2 retires: [ 2038 ]
```
Year inputs, auto-populated from person config.

### Withdrawal order (expander for accumulation + survivor)
```
Withdrawal priority (retirement):
  [taxable]  [trad_ira]  [roth]  [cash_below_target]  ← drag to reorder
▼ Accumulation & Survivor phases
  Accumulation: [cash_above_target] [taxable] [roth] [trad_ira] [cash_below_target]
  Survivor:     [cash_above_target] [trad_ira] [taxable] [roth] [cash_below_target]
```
Retirement phase shown by default. Accumulation and survivor hidden under an expander. Drag-reorder chips. Same for surplus order below.

### Save button
```
[ Save Quick Controls ]
```
Inline save button — does NOT trigger a re-render. Shows success/error toast. Uses `POST /api/save-quick-controls`.

### Re-render
The existing "Save + Re-render" and "Render All" buttons remain in the page chrome (from the current editor template).

**Dependencies:** Task 2 (API endpoints).

**Verification:** Change a value, click Save, re-open the raw TOML editor (old page), confirm the correct TOML key changed. Change nothing else — confirm comments and other sections are untouched.

---

## Task 4: Build the Data Sources & Accounts sub-tab

**Objective:** Add a sub-tab to the Setup page that shows all known accounts with their source, category, and a "Refresh from Monarch" button.

**Files:**
- Modify: `templates/setup_panel.html` (add sub-tab content)

**Layout:**
```
┌─ [Raw TOML] [Data Sources & Accounts] [Synthetic Setup] ──┐
│                                                             │
│  Accounts loaded from cache as of Jun 21, 2026              │
│  [ Refresh from Monarch ] (spinner while loading)           │
│                                                             │
│  ┌─ Account ───────────┬─ Balance ───┬─ Source ───┬─ Age ─┬─ Category ──────┬─ Disabled ─┐
│  │ Vanguard 401k       │ $371,172    │ 🟢 Cache   │  9d   │ [trad_ira ▼]    │ ☐          │
│  │ WF Mortgage (5156)  │ $109,382    │ 🟢 Cache   │  9d   │ [liability ▼]   │ ☐          │
│  │ 2020 Honda CR-V     │ $  4,895    │ 🟢 Cache   │  9d   │ [auto ▼]        │ ☐          │
│  │ ...                 │             │            │       │                  │            │
│  └─────────────────────┴─────────────┴────────────┴───────┴──────────────────┴────────────┘
│                                                             │
│  Unmatched Monarch accounts (not in [accounts]):            │
│  ┌─ Account ───────────────┬─ Balance ─┬────────────────────┐
│  │ Some New Account        │ $12,000   │ [ignore ▼]        │
│  └─────────────────────────┴───────────┴────────────────────┘
│                                                             │
│  [ Save Classification ]
└─────────────────────────────────────────────────────────────┘
```

**Key behaviors:**
- Table loads from cache by default. Never auto-fetches Monarch.
- **"Refresh from Monarch"** button is explicit — triggers `POST /api/refresh-monarch`, shows a spinner, updates the table and cache timestamp when complete.
- **Category dropdown** includes: `taxable`, `trad_ira`, `roth`, `cash`, `real_estate`, `vehicle`, `liability`, `disabled`, `ignore`.
- **Disabled checkbox** moves accounts to `disabled = [...]` list.
- **Source column** shows a colored dot matching the freshness indicator convention (green = ≤30d, yellow = >30d, gray = synthetic/manual).
- **Unmatched accounts section** shows Monarch accounts that aren't in the TOML's `[accounts]` map yet — allows the user to classify them on first sight.
- **"Save Classification"** button posts to `POST /api/save-classification`.

**Dependencies:** Task 1 (tomlkit), Task 2 (API endpoints).

**Verification:** Load the page, confirm cached accounts appear. Change a category, save, then check the raw TOML editor — the `[accounts]` section should have the new mapping, rest of file untouched. Click "Refresh from Monarch" and confirm the balance updates.

---

## Task 5: Build the Synthetic Setup sub-tab

**Objective:** Add a sub-tab with a structured form for entering starting balances when using manual/synthetic mode.

**Files:**
- Modify: `templates/setup_panel.html`

**Layout:**
```
┌─ [Raw TOML] [Data Sources & Accounts] [Synthetic Setup] ──┐
│                                                             │
│  Data Source: ○ Monarch (live/cached)  ● Manual entry       │
│                                                             │
│  Investable Balances:                                      │
│    Taxable:      [ $     120,000 ]                         │
│    Traditional:  [ $     380,000 ]                         │
│    Roth:         [ $      95,000 ]                         │
│    Cash:         [ $      45,000 ]                         │
│    Taxable cost basis: [ $ 60,000 ] (optional)             │
│    Roth contribution basis: [ $ 95,000 ] (optional)        │
│                                                             │
│  Non-Investable:                                            │
│    Home Value:   [ $     520,000 ]                         │
│                                                             │
│  Property Values (for SellHome events):                    │
│    Primary Residence:  [ $     520,000 ]                   │
│    [+ Add another property]                                │
│                                                             │
│  Liability Balances (auto-detected from [[liabilities]]):  │
│    Home Mortgage (5156):  [ $     265,000 ]                │
│    2020 Honda CR-V (9628): [ $     4,895 ]                │
│                                                             │
│  [ Save Synthetic Settings ]                                │
└─────────────────────────────────────────────────────────────┘
```

**Key behaviors:**
- Form loads empty by default (no auto-population from Monarch cache). If the scenario already has `[synthetic_start]` values, they pre-fill.
- The **Data source radio** at the top controls whether Monarch or Synthetic mode is active — switching to Manual auto-fills from... well, by design, it stays empty. A future "Copy from Monarch cache" button could bridge the gap.
- **Liability fields** are auto-generated from `[[liabilities]]` entries in the TOML — no hardcoding needed.
- **Property values** section allows adding/resolving property names. Initially populated from `[synthetic_start.property_values]`.
- **[+ Add another property]** button appends a new name/balance row with JavaScript.
- **"Save Synthetic Settings"** posts to `POST /api/save-synthetic-start` and toggles `data_source.mode` accordingly.
- Inputs use dollar formatting (comma-separated, no cents) with on-blur formatting.

**Dependencies:** Task 1 (tomlkit), Task 2 (API endpoints), Task 4 (shared table/panel chrome).

**Verification:** Enter balances, save, open the raw TOML editor and confirm `[synthetic_start]` is populated and `data_source.mode = "synthetic"`. Re-open the Setup page and confirm values persist. Switch back to Monarch mode, save, confirm `data_source.mode = "monarch"` in the TOML.

---

## Task 6: Wire up the sub-tab chrome and navigation

**Objective:** Complete `templates/setup_panel.html` with the three sub-tabs, their toggle behavior, and the quick-edit panel above them.

**Files:**
- Create: `templates/setup_panel.html` (full page template)
- Modify: `admin_app.py` (add the `/config/setup` route)

**Page structure (top to bottom):**
1. Scenario selector + action buttons (reuse from `config_editor.html`)
2. Quick-edit panel (Task 3)
3. Sub-tab bar: `[Raw TOML] [Data Sources & Accounts] [Synthetic Setup]`
4. Active sub-tab content area (swap in-place with JS on tab click)
5. Status/notification area (reuse existing pattern)

**Sub-tab navigation:**
- Pure CSS/JS tab system (like the projection page's tab system in `charts.py`)
- No page load on tab switch
- Raw TOML tab uses the existing textarea + validation/save flow

**The route:**
```python
@app.get("/config/setup", response_class=HTMLResponse)
async def setup_panel(request: Request, scenario: str = None, job: str = None):
    # Similar to / route but renders setup_panel.html instead
    ...
```

**Asset requirements:**
- The new template needs drag-reorder JS (for withdrawal/surplus order chips). A lightweight sortable library or vanilla HTML5 drag-and-drop API (no external dependency).
- No additional CSS frameworks — all styling inline in the template `<style>` block (consistent with existing NWN pages).

**Dependencies:** Tasks 3, 4, 5.

**Verification:**
1. Navigate to `/finances/config/setup`
2. Confirm scenario selection works
3. Switch between all three sub-tabs — content swaps without page reload
4. Make a change in each sub-tab, save, confirm the raw TOML tab shows the updated values
5. Confirm the old page at `/finances/config/` still works and is unaffected

---

## Task 7: Swap deployment

**Objective:** Once the new page is tested and validated, swap nginx to serve it as the primary config editor.

**Files:**
- Modify: nginx config (`/opt/hal-pages/default.conf` or equivalent)

**Options:**
| Approach | Change needed | Risk |
|---|---|---|
| Redirect `/finances/config/` → `/finances/config/setup` | nginx 301 rule + update FastAPI route | Low — old page still exists at direct URL |
| Replace the `/` route in `admin_app.py` to serve `setup_panel.html` instead of `config_editor.html` | One line in `admin_app.py` | Medium — old page goes away |
| Add a sub-tab to the old template that loads the new page | Not recommended — mixes the two designs |

**Recommended:** Add a nginx redirect. The old page stays accessible at `/finances/config/raw` or `/finances/config?raw=1` for fallback. Keeps both pages available during transition.

**Dependencies:** Tasks 1-6 completed and validated.

**Verification:** Hit `/finances/config/` — confirm it serves the new Setup page. Hit `/finances/config?raw=1` — confirm the old raw editor loads.

---

## Reference: Key TOML sections and their `tomlkit` write targets

| TOML Path | Quick-edit field | `tomlkit` write strategy |
|---|---|---|
| `data_source.mode` | Data source radio value | Replace value in place |
| `assumptions.stock_return` | Stock return input | Replace value |
| `assumptions.bond_return` | Bond return input | Replace value |
| `withdrawal_policy.*_cash_target` | Cash target inputs | Replace each key |
| `withdrawal_policy.*_withdrawal_order` | Withdrawal order chip arrays | Replace array in place |
| `withdrawal_policy.*_surplus_order` | Surplus order chip arrays | Replace array |
| `person*.retirement_year` | Retirement year inputs | Replace value |
| `accounts` | Account classification map | Replace entire table section (but not the whole file) |
| `disabled` | Disabled accounts list | Replace list |
| `synthetic_start` | All synthetic start fields | Replace entire section |
| `synthetic_start.liability_balances` | Auto-detected liability fields | Replace nested map |
| `synthetic_start.property_values` | Property name/balance pairs | Replace nested map |

The `tomlkit` strategy for each: open the file, parse into a `tomlkit` document, navigate to the container (section or table), replace or set the specific key, write the document back. The document object preserves comments and ordering automatically.

---

## Future scope (not in this plan)

These are documented as design constraints but explicitly out of scope for this implementation:

- **CSV import** of account balances
- **Adding/removing accounts** from scratch (only Monarch-discovered accounts are editable)
- **Full account lifecycle management** (name, type, balance history)
- **Multi-user or auth** for the config editor
- **Balance history charts** (store timestamped snapshots over time)
