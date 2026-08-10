# "Migrate" Banner + User Guide Migration Steps — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Show a "Migrate to v2" banner in the Scenario Setup Panel when a scenario still uses the v1 person-timeline format, linking to new migration steps in the public User Guide.

**Architecture:** A new lightweight `GET /api/migration-status` endpoint reports whether the current scenario has v1 fields (`retirement_year` / `ss_start_age` / `life_expectancy`) without matching v2 events — reusing detection logic extracted from `GET /api/events` (which already computes this but nothing consumes it). The Setup Panel fetches it on page load and toggles a banner div (new `.migrate-banner` style modeled on the existing `.accounts-mode-banner`). The banner links to a new Starlight page `guides/migrating-to-v2` with backup-first, platform-tabbed migration steps.

**Tech Stack:** FastAPI (admin_app.py), vanilla JS + tomlkit-backed API (templates/setup_panel.html), Starlight/Astro guide, unittest tests.

---

## Current State (assessed 2026-08-10)

- **Migration steps in the User Guide: DO NOT exist.** No "migrat" match anywhere in `docs/guide/src/content/docs/`. The guide has a manual sidebar (`docs/guide/astro.config.mjs:18-58`) — a new page needs an entry there.
- **README line 21 already promises** "use the Setup Panel's migration guidance" — this feature makes that sentence true; no README edit required.
- **Detection already exists but is dead data:** `GET /api/events` (`admin_app.py:2231`) computes `migration_needed` + `migration_items` (lines 2300-2334) and the Setup Panel JS ignores both (verified: no `migration` reference in `templates/setup_panel.html`).
- **Scenario switching reloads the page** (header `<select onchange="this.form.submit()">`, `setup_panel.html:556`) → a page-load banner fetch is automatically re-run per scenario. No live-refresh logic needed.
- **`apiUrl()` appends `?scenario=` automatically** (`setup_panel.html:1345-1353`) — the new endpoint just reads `request.query_params.get("scenario")` like `/api/events` does.
- **Banner idiom exists:** `.accounts-mode-banner` CSS at `setup_panel.html:370-376`; `apiGet()` helper at `:1355`; `_toml_open()` used by event endpoints (`admin_app.py:2236`).
- **Scope decision:** banner + link only. An in-UI "Run migration" button is a bigger feature (server-side TOML rewrite path, backup semantics, sample read-only guard interaction) — follow-up candidate, out of scope here.
- **Public demo pages:** samples are all migrated → banner never triggers there; no `demo_setup_page.py` change.
- **Hermeticity:** the test suite must not read gitignored personal files or write into `scenarios/`. All server tests use pure-dict tests of the helper or monkeypatch `_toml_open`.

---

## Task 1: Extract migration detection into a shared helper

**Objective:** Move the inline detection block out of `api_list_events` into `_migration_status(doc)` so both endpoints share it, with human-facing item labels.

**Files:**
- Modify: `admin_app.py` (replace lines 2300-2334 block; add helper near `api_list_events`)
- Create: `tests/test_migration_banner.py`

**Step 1: Write failing tests** — `tests/test_migration_banner.py` (hermetic; pure-dict tests; `_FakeRequest` for endpoints with `admin_app._toml_open` patched):

```python
import unittest
from unittest.mock import patch

import admin_app


class _FakeRequest:
    def __init__(self, slug: str | None = None):
        self.query_params = {"scenario": slug} if slug else {}


class MigrationStatusTests(unittest.TestCase):
    def _v1_doc(self):
        return {
            "scenario": {"name": "V1 Scratch"},
            "person1": {"name": "Test", "dob": "1970-01-01",
                        "retirement_year": 2035, "ss_start_age": 67, "life_expectancy": 90},
        }

    def test_detects_v1_fields_without_events(self):
        needed, items = admin_app._migration_status(self._v1_doc())
        self.assertTrue(needed)
        self.assertEqual(len(items), 3)
        self.assertIn("Person 1 — Retirement", items)
        self.assertIn("Person 1 — Social Security", items)
        self.assertIn("Person 1 — End of Plan", items)

    def test_clean_when_events_exist(self):
        doc = self._v1_doc()
        doc["events"] = [
            {"type": "Retire", "person": "person1", "year": 2035},
            {"type": "SocialSecurity", "person": "person1", "year": 2037},
            {"type": "EndOfPlan", "person": "person1", "year": 2060},
        ]
        needed, items = admin_app._migration_status(doc)
        self.assertFalse(needed)
        self.assertEqual(items, [])

    def test_partial_migration_lists_only_missing(self):
        doc = self._v1_doc()
        doc["events"] = [{"type": "Retire", "person": "person1", "year": 2035}]
        needed, items = admin_app._migration_status(doc)
        self.assertTrue(needed)
        self.assertEqual(items, ["Person 1 — Social Security", "Person 1 — End of Plan"])

    def test_skips_absent_person2(self):
        needed, items = admin_app._migration_status(self._v1_doc())
        self.assertTrue(needed)
        self.assertFalse(any("Person 2" in i for i in items))

    def test_endpoint_returns_flags(self):
        with patch.object(admin_app, "_toml_open", return_value=(self._v1_doc(), None)):
            resp = admin_app.api_migration_status(_FakeRequest("v1scratch"))
        body = resp.body if hasattr(resp, "body") else resp
        import json
        data = json.loads(resp.body) if hasattr(resp, "body") else resp
        self.assertTrue(data["ok"])
        self.assertTrue(data["migration_needed"])
        self.assertEqual(len(data["items"]), 3)

    def test_events_endpoint_keeps_flags(self):
        with patch.object(admin_app, "_toml_open", return_value=(self._v1_doc(), None)):
            resp = admin_app.api_list_events(_FakeRequest("v1scratch"))
        data = json.loads(resp.body)
        self.assertTrue(data["ok"])
        self.assertTrue(data["migration_needed"])
        self.assertEqual(len(data["migration_items"]), 3)
```

**Step 2:** Run → `pytest tests/test_migration_banner.py -q` → expect FAIL (`AttributeError: module 'admin_app' has no attribute '_migration_status'`).

**Step 3: Implement** — in `admin_app.py`, add before `api_list_events`:

```python
def _migration_status(doc: dict) -> tuple[bool, list[str]]:
    """Return (needed, items) — whether the scenario still carries v1
    person-timeline fields that lack v2 events, with human-facing item labels."""
    raw_events = doc.get("events")
    events = raw_events if isinstance(raw_events, list) else []
    person_labels = {"person1": "Person 1", "person2": "Person 2"}
    labels = {"Retire": "Retirement", "SocialSecurity": "Social Security", "EndOfPlan": "End of Plan"}
    needed = []
    for person_key in ("person1", "person2"):
        person = doc.get(person_key)
        if not isinstance(person, dict):
            continue
        has = {t: any(e.get("type") == t and e.get("person") == person_key for e in events)
               for t in ("Retire", "SocialSecurity", "EndOfPlan")}
        p = person_labels[person_key]
        if not has["Retire"] and person.get("retirement_year") is not None:
            needed.append(f"{p} — {labels['Retire']}")
        if not has["SocialSecurity"] and (person.get("ss_start_age") is not None
                                          or person.get("ss_claim_age") is not None):
            needed.append(f"{p} — {labels['SocialSecurity']}")
        if not has["EndOfPlan"] and person.get("life_expectancy") is not None:
            needed.append(f"{p} — {labels['EndOfPlan']}")
    return (bool(needed), needed)
```

Then replace the inline block in `api_list_events` (currently `admin_app.py:2300-2334`, from `# ── Migration detection ──` through the `if migration_needed:` lines) with:

```python
        migration_needed, migration_items = _migration_status(doc)
        result = {"ok": True, "events": parsed, "count": len(parsed)}
        # (keep the birth_years block that follows, then:)
        if migration_needed:
            result["migration_needed"] = True
            result["migration_items"] = migration_items
```

Note: `migration_items` labels change from `"person1 Retire"` to `"Person 1 — Retirement"`. Nothing consumes them today (verified), so this is safe and the banner benefits.

**Step 4:** Run → `pytest tests/test_migration_banner.py -q` → PASS. Also `pytest tests/ -q` to catch /api/events regressions.

**Step 5: Commit** — `git add admin_app.py tests/test_migration_banner.py && git commit -m "refactor: extract shared migration-status detection in admin_app"`

---

## Task 2: Add `GET /api/migration-status` endpoint

**Objective:** Serve the migration flags standalone for the banner.

**Files:** Modify: `admin_app.py` (next to `api_list_events`, ~line 2231)

**Step 1:** Add to the failing test file:

```python
    def test_endpoint_clean_when_migrated(self):
        doc = {"scenario": {"name": "Migrated"},
               "person1": {"name": "Test", "dob": "1970-01-01"},
               "events": [{"type": "Retire", "person": "person1", "year": 2035}]}
        with patch.object(admin_app, "_toml_open", return_value=(doc, None)):
            resp = admin_app.api_migration_status(_FakeRequest("migrated"))
        data = json.loads(resp.body)
        self.assertTrue(data["ok"])
        self.assertFalse(data["migration_needed"])
        self.assertEqual(data["items"], [])
```

Run → FAIL (no `api_migration_status` yet).

**Step 2: Implement** — after `api_list_events`:

```python
@app.get("/api/migration-status")
async def api_migration_status(request: Request) -> JSONResponse:
    """Return whether the scenario still uses v1 person-timeline fields."""
    scenario_slug = request.query_params.get("scenario") or None
    try:
        doc, _ = _toml_open(scenario_slug)
        migration_needed, items = _migration_status(doc)
        return JSONResponse({"ok": True, "migration_needed": migration_needed, "items": items})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
```

**Step 3:** Run → `pytest tests/test_migration_banner.py -q` → PASS.

**Step 4: Commit** — `git commit -am "feat: add /api/migration-status endpoint"`

---

## Task 3: Banner markup, CSS, and JS in the Setup Panel

**Objective:** Render the banner on page load when the scenario needs migration.

**Files:** Modify: `templates/setup_panel.html`

**Step 1: Write template-assertion tests** (append to `tests/test_migration_banner.py`):

```python
class MigrateBannerTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = Path("templates/setup_panel.html").read_text(encoding="utf-8")

    def test_banner_markup_and_link_present(self):
        self.assertIn('class="migrate-banner" id="migrate-banner"', self.template)
        self.assertIn('id="migrate-banner-items"', self.template)
        self.assertIn("guides/migrating-to-v2", self.template)

    def test_banner_fetch_and_init_present(self):
        self.assertIn("api/migration-status", self.template)
        self.assertIn("function initMigrationBanner", self.template)
        self.assertIn("initMigrationBanner()", self.template)

    def test_banner_css_present(self):
        self.assertIn(".migrate-banner", self.template)
```

Run → FAIL.

**Step 2: Implement:**

a) **CSS** — after the `.accounts-mode-banner` block (`setup_panel.html:376`):

```css
    .migrate-banner {
      display: none; align-items: flex-start; gap: 10px;
      padding: 12px 16px; font-size: 13px; line-height: 1.5;
      color: #fcd34d; background: rgba(245,158,11,0.08);
      border-bottom: 1px solid rgba(245,158,11,0.25);
    }
    .migrate-banner.show { display: flex; }
    .migrate-banner a { color: #fbbf24; font-weight: 600; }
```

b) **Markup** — immediately after the header div closes (`setup_panel.html:573`), before the status area:

```html
    <div class="migrate-banner" id="migrate-banner">
      <span class="banner-icon">⚠️</span>
      <div>
        <strong>This scenario uses the older v1 format.</strong>
        <span id="migrate-banner-items"></span>
        <a href="https://lemurtech.github.io/Net-Worth-Navigator/guides/migrating-to-v2/" target="_blank" rel="noreferrer">Migration steps in the User Guide</a>
      </div>
    </div>
```

c) **JS** — add near the other init functions and invoke beside the existing init sequence (find where `initQuickEdit()` / tab inits run):

```javascript
      function initMigrationBanner() {
        apiGet('api/migration-status').then(function (data) {
          if (!data || !data.ok) return;
          var el = document.getElementById('migrate-banner');
          if (!data.migration_needed || !el) return;
          var itemsEl = document.getElementById('migrate-banner-items');
          if (itemsEl && data.items && data.items.length) {
            itemsEl.textContent = ' Missing: ' + data.items.join(', ') + '.';
          }
          el.classList.add('show');
        }).catch(function () {});
      }
      initMigrationBanner();
```

**Step 3:** Run → `pytest tests/test_migration_banner.py -q` → PASS; `pytest tests/ -q` → full suite green.

**Step 4: Commit** — `git commit -am "feat: add v2 migration banner to Setup Panel"`

---

## Task 4: User Guide migration-steps page + sidebar entry

**Objective:** Author the migration steps the banner links to, per the project's guide authoring patterns (platform tabs, hand-holding, numbered steps, Windows first for user-facing commands).

**Files:**
- Create: `docs/guide/src/content/docs/guides/migrating-to-v2.mdx`
- Modify: `docs/guide/astro.config.mjs` (sidebar; add after the Updating NWN entry at line 55)

**Step 1: Create the page.** Content outline (write in full, following the existing guide's tone and `<Tabs>/<TabItem>` pattern with imports from `@astrojs/starlight/components`):

1. **What changed in v2** — timeline decisions (retirement, Social Security claiming, end of plan) moved from per-person settings into the **Events** tab as `Retire`, `SocialSecurity`, and `EndOfPlan` events. Social Security benefit amounts are now looked up automatically from the person's benefit table — the stored amount on events is no longer used.
2. **Why migrate** — v1 files still render (legacy fallbacks keep retirement timing working), but Social Security income and the end-of-plan boundary only come from v2 events, so an un-migrated file would silently project no Social Security income. The banner in the Setup Panel appears until migration is done.
3. **Before you start: back up** — personal scenario files are not tracked by git; copy the whole `scenarios` folder to a safe location (numbered steps; both platforms).
4. **Run the migration** — numbered steps: open a terminal → `cd` into the project folder → dry run first → review output → run for real. Platform tabs: **Windows (PowerShell)** first, **Linux / macOS** second. Exact commands:
   - Dry run: `.venv\Scripts\python.exe scripts\migrate_v2.py --dry-run` / `.venv/bin/python scripts/migrate_v2.py --dry-run`
   - Apply: same without `--dry-run`
   - Optional comment cleanup for your own (non-sample) files: `--strip-comments`
5. **What the script does** — creates the three event types from the old fields (age → year from birth date), sorts events, normalizes spacing. It is safe to re-run (idempotent; a second run makes no changes).
6. **Verify** — open the Scenario Setup panel → Events tab shows the new cards; run **Save + Re-render**; the migration banner disappears.

**Step 2: Sidebar entry** in `docs/guide/astro.config.mjs` after line 55:

```js
{ label: 'Migrating to v2', slug: 'guides/migrating-to-v2' },
```

**Step 3: Validate the guide build** — `cd docs/guide && npm ci --ignore-scripts && npx astro build` → expect success (29 + 1 pages). (Follow AGENTS.md: dev server via `astro dev --background` if interactive checks are needed.)

**Step 4: Commit** — `git add docs/guide/ && git commit -m "docs(guide): add v1 to v2 migration steps page"`

---

## Task 5: End-to-end verification

**Objective:** Prove the banner works against the live app and nothing regressed.

**Steps:**
1. `pytest tests/ -q` → expect 224 + new tests, all passing.
2. Restart the config editor (admin_app.py changed): `cd /opt/hal-pages && docker compose restart nwn-config-editor`.
3. **Live banner check with a scratch v1 scenario** (gitignored, deleted afterwards):
   - Create `scenarios/v1scratch.toml`:
     ```toml
     [scenario]
     name = "V1 Scratch"
     household_type = "single"

     [person1]
     name = "Test"
     dob = "1970-01-01"
     retirement_year = 2035
     ss_start_age = 67
     life_expectancy = 90
     ```
   - `curl 'http://localhost/finances/config/api/migration-status?scenario=v1scratch'` → expect `{"ok": true, "migration_needed": true, "items": [...3 items...]}`.
   - Load `http://casalemuria.lan/finances/config/setup?scenario=v1scratch` (hard refresh) → banner visible with the three missing items and the guide link; check browser console for errors.
   - Switch to `sample` → banner absent.
   - Delete `scenarios/v1scratch.toml`.
4. Confirm `/api/events?scenario=sample` still returns `migration_needed` absent (migrated → clean).

**Commit** (if anything else changed) and present to the user for review before pushing.

---

## Task 6: Wrap-up — project docs + skill

**Objective:** Record the change where the project and the agent expect it.

- Add a `## 2026-08-10 (Migration banner + guide)` entry to `docs/progress.md` (Added: endpoint, banner, guide page; note that README's existing "Setup Panel's migration guidance" line now holds).
- Update the `net-worth-navigator` skill: V2 feature inventory gains the migration banner + `GET /api/migration-status` + `guides/migrating-to-v2` page; replace the pitfall note "the frontend doesn't currently display that flag" with the new behavior.
- Commit: `git commit -am "docs: progress + skill notes for migration banner"`

---

## Risks / Tradeoffs / Open Questions

- **Item label format change** in `/api/events` (`"person1 Retire"` → `"Person 1 — Retirement"`): nothing consumes it today; safe, but double-check no test asserts the old strings.
- **Banner is informational only** — users must run the CLI migration themselves. An in-UI migrate button is a deliberate follow-up (server-side rewrite + backup semantics + sample read-only interaction).
- **Emoji ⚠️ in banner**: the page is dark-themed and already uses emoji in events; fine on the homelab browsers. If rendering is inconsistent, swap for an SVG like the help icons.
- **Guide link is the public URL** (`lemurtech.github.io/...`) — correct per the public-demo preference; homelab users reach the public site.
- **Open question for the user:** should the banner also appear on the **projection/compare pages** (e.g., a topbar note when viewing an un-migrated scenario)? **Resolved 2026-08-10: Setup Panel only.**
