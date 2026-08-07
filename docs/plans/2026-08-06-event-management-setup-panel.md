# Event Management in the Setup Panel

**Status:** Proposed
**Date:** 2026-08-06
**Source:** [NWN Improvement Proposal — FIREMaster Lessons](../../../../obsidian/Main/12%20Projects/2026/2026%20Net%20Worth%20Navigator/NWN%20Improvement%20Proposal%20-%20FIREMaster%20Lessons.md), Item #3
**Assessment performed:** 2026-08-06 — full codebase inspection of Setup Panel, admin_app.py, model.py event processing, TOML schema, and definitions page.

---

## Motivation

Typing `[[events]]` blocks by hand in the Raw TOML editor is the worst part of NWN's UX. The Setup Panel already handles structured quick-controls via tomlkit-backed API endpoints — extending that same pattern to cover events would directly address the single biggest source of friction in scenario editing. This is the proposal's Tier 1, Item #3 recommendation: guided forms per event type, validation on save, clean TOML output preserving git-diffable, revert-friendly state.

**What users currently face:**

- 13 event types, each with 2–15 fields, documented only inline in sample scenario files
- No type validation — a typo like `"Expence"` silently produces a non-functional event
- Recurring controls (`repeat_every_years`, `repeat_until_year`, `repeat_count`) can conflict and only fail at runtime
- SellHome cross-references (`property`, `liability_names`, `property_values` keys) tracked entirely by hand
- Enable/disable requires opening Raw TOML, finding the right block, changing a boolean
- Reordering events (which are processed sequentially) requires cut-and-paste of whole TOML blocks

---

## Assessment Summary

A full codebase inspection (2026-08-06) confirmed the proposal is architecturally sound:

- **tomlkit** can read, modify, and write `[[events]]` array-of-tables while preserving comments and ordering
- The `api_save_quick_controls` pattern — read TOML via tomlkit, apply structured form changes, write back, create timestamped backups, trigger async re-render — is proven and directly reusable
- The Setup Panel's tab system (`Metadata | Accounts | Raw TOML`) is easily extensible with a 4th tab
- The dark-themed CSS design system is consistent and reusable across tabs

**What's new vs. quick controls:** Quick controls modify known scalar paths (`assumptions.stock_return`). Events require insert/update/delete/reorder on an array of tomlkit tables — a new API shape, but one that tomlkit supports natively via `doc.append("events", table)`.

---

## Event Type Catalog

All 13 event types recognized by the model engine (`src/model.py`, `EVENT_ICONS` dict):

| # | Type | Complexity | Required Fields | Key Optional Fields |
|---|------|-----------|-----------------|---------------------|
| 1 | `EndOfPlan` | Simple | `person`, `year` | `label`, `enabled` |
| 2 | `Retire` | Simple | `person`, `year` | `label`, `enabled` |
| 3 | `Marriage` | Simple | `year` | `label`, `enabled` |
| 4 | `Income` | Medium | `year`, `amount` | `end_year`, `taxable`, `taxable_fraction`, recurrent controls |
| 5 | `Expense` | Medium | `year`, `amount` | `expense_kind`, `funding`, recurrent controls |
| 6 | `Education` | Medium | `person`, `start_year`, `end_year`, `annual_cost` | `label`, `enabled` |
| 7 | `SocialSecurity` | Medium | `person`, `year`, `monthly_benefit` | `taxable`, `taxable_fraction` |
| 8 | `NewJob` | Medium | `person`, `year`, `annual_income` | `label`, `enabled` |
| 9 | `CareerBreak` | Medium | `person`, `start_year`, `end_year` | `label`, `enabled` |
| 10 | `BuyHome` | Complex | `year`, `down_payment` | `price`, `property`, `mortgage_rate`, `term_years` |
| 11 | `SellHome` | Complex | `year`, `property` | `liability_names`, `sale_fee_rate`, `reinvest_to`, `reinvest_fraction` |
| 12 | `SpendingShift` | Complex | `start_year`, `mode` | `end_year`, `phase`, `retirement_annual`, `survivor_annual`, `survivor_percent_of_retirement` |
| 13 | `ContributionChange` | Complex | `year`, `person` | 13 contribution/employer override fields (absolute, delta, percent-mode, employer-match) |

**Recurring controls** (applicable to Expense, Income, and others): `repeat_every_years`, `repeat_until_year`, `repeat_count`, `chart_first_occurrence_only`.

**Common fields on every event:** `enabled` (bool), `label` (string), `type` (string — determined by form, not user-entry).

**Synthesized events:** `Retire`, `SocialSecurity`, and `EndOfPlan` events are auto-generated at runtime from `person.dob` + `life_expectancy` + `ss_start_age`. The Events tab should display these as read-only cards since the user controls their parameters via the People section on the Metadata tab.

---

## Phase Plan

### Phase 3a — Events Tab with Summary Cards + Toggle

**Goal:** Add an Events tab that reads existing `[[events]]` blocks and renders them as summary cards with enable/disable toggles. No editing yet — just visibility and control.

**Files touched:**

| File | Change |
|------|--------|
| `templates/setup_panel.html` | New `tab-btn[data-tab="events"]` in tab bar. New `tab-content` div with event list container. JS to parse events from Raw TOML textarea content, render summary cards (type icon, label, years, amount preview), wire toggle buttons. Toggle calls API then updates Raw TOML textarea. |
| `admin_app.py` | New `POST /api/toggle-event` endpoint — accepts `scenario` slug + event index, reads TOML via tomlkit, flips `enabled` on the target `[[events]]` entry, writes back with backup. Returns `{ok, enabled_state}`. |

**API endpoint:**

```
POST /api/toggle-event?scenario=<slug>
Body: { "index": 2, "enabled": false }
Response: { "ok": true, "enabled": false }
```

**Summary card template (conceptual):**

```
┌──────────────────────────────────────────────────────┐
│ 💸  Travel                                            │
│     Expense  |  2027 (repeats every 2 yrs → 2055)    │
│     -$8,000  |  Kind: discretionary                  │
│                                        [✔ Enabled]   │
└──────────────────────────────────────────────────────┘
```

**Cost estimate:** ~150 lines HTML/JS, ~60 lines Python.

---

### Phase 3b — Add Event Form

**Goal:** An "Add Event" button opens a type-selector dropdown, then a type-specific form with correct fields, defaults, placeholder values, and help text. On save, appends a new `[[events]]` block to the TOML document.

**Files touched:**

| File | Change |
|------|--------|
| `templates/setup_panel.html` | "Add Event" button + type-selector modal. Per-type form templates (generated JS-side from a field catalog). Form submission via `apiPost()`. |
| `admin_app.py` | New `POST /api/add-event` endpoint — validates fields per type, creates a tomlkit table, appends to `[[events]]`, writes TOML via `_backup_and_write_toml()`. Returns `{ok, index}`. |
| `src/definitions_page.py` | (Optional) Update event definitions if any fields change. |

**API endpoint:**

```
POST /api/add-event?scenario=<slug>
Body: {
  "type": "Expense",
  "label": "Travel",
  "year": 2027,
  "amount": -8000,
  "expense_kind": "discretionary",
  "funding": "cash_reserve_first",
  "repeat_every_years": 2,
  "repeat_until_year": 2055,
  "chart_first_occurrence_only": true
}
Response: { "ok": true, "index": 3 }
```

**Field catalog design:** A JS-side object keyed by event type, each entry listing fields with type, label, placeholder, help text, and default value. Example:

```javascript
const EVENT_FIELDS = {
  Expense: [
    { name: 'label', type: 'text', label: 'Label', placeholder: 'e.g. Travel', help: 'Human-readable name for charts and tables' },
    { name: 'year', type: 'number', label: 'Year', required: true },
    { name: 'amount', type: 'number', label: 'Amount', placeholder: '-8000', help: 'Negative for outflows, positive for inflows' },
    { name: 'expense_kind', type: 'select', label: 'Kind', options: ['mandatory', 'discretionary'], default: 'discretionary' },
    { name: 'funding', type: 'select', label: 'Funding', options: ['', 'cash_reserve_first'], default: '', help: '"cash_reserve_first" lets this event break reserve protection first' },
    // ... recurring controls
  ],
  // ... 12 more types
};
```

**Validation per type (server-side):**

- Required fields present and non-empty
- `year` / `start_year` / `end_year` are integers within simulation range
- `amount` is numeric
- `person` is `"person1"` or `"person2"` (person2 only valid for couple households)
- `expense_kind` is `"mandatory"` or `"discretionary"` if provided
- `funding` is `"cash_reserve_first"` or omitted if provided
- For SellHome: `property` references a known key from `[synthetic_start.property_values]`
- For recurring events: at least one of `repeat_count`, `repeat_until_year`, or simulation `end_year` exists
- `repeat_every_years > 0` if present

**Cost estimate:** ~300 lines HTML/JS, ~150 lines Python (field catalog + validation).

---

### Phase 3c — Edit, Delete, Reorder

**Goal:** Full CRUD on event list. Click a card to open its edit form (pre-populated). Delete with confirmation dialog. Reorder with up/down arrow buttons.

**Files touched:**

| File | Change |
|------|--------|
| `templates/setup_panel.html` | Edit modal (reuses form templates from 3b). Delete confirmation. Up/down arrow buttons on each card. DOM re-render on reorder. |
| `admin_app.py` | `POST /api/update-event` — replace event at index. `POST /api/delete-event` — remove event at index. `POST /api/reorder-events` — accept new index array. |

**API endpoints:**

```
POST /api/update-event?scenario=<slug>
Body: { "index": 2, "type": "Expense", "label": "Travel", ... }
Response: { "ok": true }

POST /api/delete-event?scenario=<slug>
Body: { "index": 2 }
Response: { "ok": true }

POST /api/reorder-events?scenario=<slug>
Body: { "order": [0, 2, 1, 3] }
Response: { "ok": true }
```

**Delete confirmation:** A simple modal: "Delete 'Travel' event? This cannot be undone." with Cancel / Delete buttons.

**Reorder UI:** Up (↑) and down (↓) arrow buttons at the top-right of each card. First card has no up arrow; last card has no down arrow. On click, swap indices and re-render.

**Cost estimate:** ~200 lines HTML/JS, ~100 lines Python.

---

### Phase 3d — Validation Endpoint

**Goal:** A dedicated `POST /api/validate-events` that checks all events for field presence, type correctness, cross-references, and recurring control consistency — returns structured errors without running a full projection.

**API endpoint:**

```
POST /api/validate-events?scenario=<slug>
Response: {
  "ok": false,
  "errors": [
    { "index": 2, "field": "repeat_until_year", "message": "Recurring event needs repeat_count, repeat_until_year, or simulation.end_year" },
    { "index": 5, "field": "property", "message": "SellHome references unknown property 'Beach House'. Known properties: Single Residence" }
  ]
}
```

**Validation rules:**

| Rule | Applies to |
|------|-----------|
| Required fields present | All types |
| `year` / `start_year` / `end_year` are integers in range | All types |
| `amount` is numeric | Expense, Income |
| `person` is valid and appropriate for household type | Person-aware types |
| `expense_kind` is `mandatory` or `discretionary` | Expense |
| `funding` is `cash_reserve_first` or omitted | Expense |
| `property` references known value | SellHome |
| `liability_names` reference known liabilities | SellHome |
| Recurring controls are consistent (not conflicting) | Expense, Income, others with repeat fields |
| `repeat_every_years > 0` | Recurring events |
| `mode` is `replace` | SpendingShift |
| Typo detection on `type` field | All (should never happen with form-driven creation, but validate anyway) |

**Cost estimate:** ~150 lines Python.

---

## Implementation Order

```
Phase 3a (list + toggle)  →  Phase 3b (add form)  →  Phase 3c (edit/delete/reorder)  →  Phase 3d (validation)
```

Phase 3a is the highest-value, lowest-risk starting point. It gives users immediate visibility into their events and the ability to toggle them without touching Raw TOML — while building the foundational tomlkit event manipulation code that all subsequent phases depend on.

Phase 3d (validation) should run before any save operation from Phase 3b onward — it's listed last because it can be built incrementally as each event type's form is added in 3b/3c.

---

## Risks and Pitfalls

### 1. tomlkit array-of-tables index tracking

tomlkit's AoT API (`doc["events"]`) returns a list-like object. Insert, update, and delete operations must preserve the index mapping between the UI's card order and the TOML array order. If tomlkit re-indexes internally, the client's stored indices become stale. **Mitigation:** always re-read TOML on every save operation; send the full event data (not just index) in update requests to allow server-side identity matching by label or content hash.

### 2. TOML-as-SSOT round-tripping

Every form save must round-trip through tomlkit without losing comments, whitespace, or field ordering within a table block. **Mitigation:** write a dedicated test that creates an event with all optional fields, reads it back, and asserts the resulting TOML is functionally identical and non-corrupted. Run this before any Phase 3 work touches user scenario files.

### 3. Synthesized events confusion

`Retire`, `SocialSecurity`, and `EndOfPlan` are auto-generated at runtime from Metadata tab fields. The Events tab should display them as read-only "System Events" with a note: "Controlled via People settings on the Metadata tab." **Do not allow editing or deleting these in the Events tab.** They only appear in the list when the TOML file explicitly contains `[[events]]` entries of those types (which the user may have added manually before synthesized events were introduced).

### 4. Single-person vs. couple field visibility

Events with a `person` field (`Retire`, `EndOfPlan`, `SocialSecurity`, `CareerBreak`, `NewJob`, `ContributionChange`, `Education`) should only show `person2` as an option when `household_type` is `"couple"`. The form generator must check this dynamically. In single-person mode, `person` can be hidden entirely and default to `"person1"`.

### 5. ContributionChange complexity

With 13 optional fields split across absolute, delta, percent-mode, and employer-match categories, ContributionChange is the most complex event type. Its form should be organized into collapsible sections:

- **Contribution Amounts** — `annual_401k_contribution`, `annual_ira_contribution`, `annual_401k_employer_match`
- **Contribution Deltas** — `annual_401k_contribution_delta`, `annual_ira_contribution_delta`, `annual_401k_employer_match_delta`
- **Percent-Mode Overrides** — `gross_income`, `gross_income_annual_increase_percent`, `retirement_contribution_percent`, `retirement_contribution_annual_increase_percent`, `retirement_contribution_max_percent`
- **Employer Match Settings** — `annual_401k_employer_match_mode`, `annual_401k_employer_match_rate`, `annual_401k_employer_match_max_percent`

This event should ship last in the Phase 3 sequence, after the simpler types prove the pattern works.

### 6. Container restart requirement

After any change to `admin_app.py`, the nwn-config-editor container must be restarted: `cd /opt/hal-pages && docker compose restart nwn-config-editor`. Browser cache requires `Ctrl+Shift+R` after restart.

---

## Testing Approach

### Unit tests (pytest)

- `test_tomlkit_event_roundtrip.py` — Create events of each type via tomlkit, write to temp TOML, read back, assert field equality and comment preservation
- `test_event_validation.py` — Feed valid and invalid event dicts to the validation function, assert error presence/absence per rule
- `test_event_crud.py` — Add, update, toggle, delete, reorder events via API endpoints against a temp TOML file

### Manual verification (per phase)

- After Phase 3a: open Setup Panel, verify Events tab shows all existing events with correct types/amounts/years, toggle enable/disable, verify Raw TOML updates, verify projection reflects toggled state
- After Phase 3b: add each event type, verify form validation catches errors, save, verify Raw TOML shows correct block, run projection
- After Phase 3c: edit an existing event, verify TOML updates correctly, delete an event, verify removal, reorder events, verify projection changes
- After Phase 3d: submit invalid events, verify structured error messages, fix errors, verify validation passes

---

## Files Summary

| File | Phase 3a | Phase 3b | Phase 3c | Phase 3d |
|------|----------|----------|----------|----------|
| `templates/setup_panel.html` | ✓ tab + cards + toggle JS | ✓ add-form modal + field catalog JS | ✓ edit/delete modals + reorder JS | — |
| `admin_app.py` | ✓ `POST /api/toggle-event` | ✓ `POST /api/add-event` + field catalog + validation | ✓ update/delete/reorder endpoints | ✓ `POST /api/validate-events` |
| `src/event_validation.py` | — | — | — | ✓ validation module |
| `tests/test_event_*.py` | ✓ roundtrip test | ✓ add + validation tests | ✓ CRUD tests | ✓ validation tests |

---

## Decision Log

- **2026-08-06:** Assessment complete. Architecture confirmed sound. Phased approach adopted (3a → 3b → 3c → 3d). Plan written to `dev` branch.
