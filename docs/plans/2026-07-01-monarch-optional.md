# Monarch-Optional Mode — Implementation Plan

> **Status:** Assessment complete. Ready for implementation.
> **See also:** `src/monarch_bridge.py`, `run.py`, `admin_app.py`, `templates/setup_panel.html`, `scenarios/sample.toml`

**Goal:** Make Net Worth Navigator fully usable by someone who does not have or want Monarch Money. A user who has never heard of Monarch should be able to clone the repository, configure their balances in a TOML file (or via the Setup Panel), and run the app without errors, confusing messages, or dead UI elements.

**Non-goal:** This plan does not add CSV import, bank API connectors, or any new balance-retrieval mechanism. The only non-Monarch input path is the existing `[synthetic_start]` system — this plan improves its usability, discoverability, and error handling, not its data model.

**What is already working:** The model engine (`model.py`) has zero Monarch dependency. When `[data_source].mode = "synthetic"`, `run.py` already fully bypasses all Monarch code and runs the projection from TOML-provided balances. The `sample.toml` scenario is a complete, runnable, Monarch-free scenario today. The Setup Panel has a data-source radio toggle and a Synthetic Setup sub-tab. **No architectural changes are required** — this plan is entirely about guard rails, error messaging, UI conditioning, and a better onboarding template.

**Architecture invariant:** All changes in this plan are strictly additive or conditional. No existing Monarch-using functionality is removed or broken. A user with Monarch configured will experience no change.

---

## Background: The Three Data-Source Modes

```
data_source.mode = "synthetic"   →  uses [synthetic_start] from TOML, Monarch never called
--offline (CLI flag)             →  uses output/balances_cache.json, Monarch never called
(default / "monarch")            →  live Monarch MCP subprocess
```

The model always receives a plain Python dict of starting balances from `run.py`. It does not know or care which path produced them. Everything in this plan happens at the `run.py` / `admin_app.py` / `monarch_bridge.py` / `setup_panel.html` layer — not in the projection or chart code.

---

## Phase 1: Clean Error Handling (monarch_bridge.py)

**Objective:** Replace opaque subprocess failures with actionable, user-facing error messages when Monarch is not installed or not configured.

**Problem today:** `monarch_bridge.py` hardcodes two absolute paths at module level:
```python
MCP_PYTHON = Path("/opt/monarch-mcp-server/.venv/bin/python3")
MCP_SRC    = Path("/opt/monarch-mcp-server/src")
```
When these paths don't exist (any machine other than Person 1's), `fetch_raw_accounts()` fails with a subprocess error whose `stderr` references Person 1-specific paths and tells the user to run `uv run python login_setup.py` at a directory that doesn't exist on their system.

**Files:** `src/monarch_bridge.py`

### Task 1.1 — Add a pre-flight check to `fetch_raw_accounts()`

Add an existence check before attempting the subprocess call. If the MCP python binary doesn't exist, raise a clean `RuntimeError` with a clear message that explains the situation and points to the fix.

```python
def fetch_raw_accounts() -> list[dict]:
    """
    Call the MCP server's Python to fetch accounts as JSON.
    Raises RuntimeError with a clear message if Monarch is not installed.
    """
    if not MCP_PYTHON.exists():
        raise RuntimeError(
            "Monarch MCP server not found at expected path.\n"
            "To run without Monarch, set [data_source].mode = \"synthetic\" in your scenario\n"
            "and provide starting balances in [synthetic_start].\n"
            f"(Expected binary: {MCP_PYTHON})"
        )
    result = subprocess.run(...)
    ...
```

**Dependencies:** None.

**Verification:** Delete or rename `/opt/monarch-mcp-server/.venv/bin/python3` temporarily (or run on a clean machine). Call `fetch_raw_accounts()`. Confirm the `RuntimeError` message is clean and does not contain Person 1-specific advice.

---

### Task 1.2 — Make MCP paths configurable

Currently the MCP server location is baked in. Allow a user to point to a different location by reading an optional environment variable or config value, falling back to the hardcoded defaults.

**Approach:** Read `MONARCH_MCP_PATH` from the environment, or optionally from a top-level `[monarch]` section in the scenario TOML. The fallback remains the existing hardcoded path so Person 1's setup is unchanged.

```python
import os

_DEFAULT_MCP_ROOT = Path("/opt/monarch-mcp-server")

def _mcp_root() -> Path:
    env = os.environ.get("MONARCH_MCP_PATH")
    return Path(env) if env else _DEFAULT_MCP_ROOT

# Then:
MCP_PYTHON = _mcp_root() / ".venv/bin/python3"
MCP_SRC    = _mcp_root() / "src"
```

This is a one-liner change for a Monarch user on a different machine — they set `MONARCH_MCP_PATH=/path/to/their/monarch-mcp-server` in their `.env` and it works.

**Files:** `src/monarch_bridge.py`

**Dependencies:** Task 1.1 (should be done together as one commit).

**Verification:** Set `MONARCH_MCP_PATH=/some/other/path` in the environment. Confirm `MCP_PYTHON` and `MCP_SRC` resolve to the new path. Confirm the pre-flight check uses the new path.

---

### Task 1.3 — Improve `run.py` error surfacing for Monarch failures

Currently if Monarch fetch fails during a full run, the exception propagates up and prints a Python traceback. Catch the `RuntimeError` from `fetch_raw_accounts()` in `run.py`'s `main()` and print a clear, actionable message before exiting.

```python
try:
    raw_accounts = fetch_raw_accounts()
except RuntimeError as exc:
    print(f"\nERROR: Could not fetch Monarch balances.\n{exc}\n")
    print("To run offline: python run.py --offline")
    print("To run without Monarch: set [data_source].mode = \"synthetic\" in your scenario.")
    sys.exit(1)
```

**Files:** `run.py`

**Dependencies:** Task 1.1.

**Verification:** On a machine without Monarch (or with Task 1.1 pre-flight check active), run `python run.py` on a scenario without `data_source.mode = "synthetic"`. Confirm clean error output, no traceback.

---

## Phase 2: Setup Panel UI Conditioning

**Objective:** Make the Setup Panel aware of the active data source mode and conditionally show or hide Monarch-specific UI elements.

**Problem today:** The Accounts tab always renders with "Accounts loaded from cache as of [date]" and a "Refresh from Monarch" button, even when the scenario is in synthetic mode and there is no cache. A non-Monarch user sees an empty table with no explanation, and clicking "Refresh from Monarch" returns an opaque 502 error.

**Files:** `templates/setup_panel.html`, `admin_app.py`

---

### Task 2.1 — `api/accounts` response: include `source_mode`

The endpoint already returns `source_mode`, so the template already has the data it needs. Confirm the `source_mode` field is available in the template's initial data payload (it's set by `api/data-source-status` too). No backend changes required — this is a note to confirm the data is there before doing template work.

**Verification:** Open browser dev tools. Hit `/api/accounts?scenario=sample`. Confirm `source_mode: "synthetic"` is in the response JSON.

---

### Task 2.2 — Accounts tab: add synthetic-mode banner and disable Refresh button

In `setup_panel.html`, the Accounts tab toolbar renders unconditionally. Add JavaScript logic that runs after the accounts response is loaded:

- If `source_mode === "synthetic"`: 
  - Inject an info banner: _"This scenario uses manual (synthetic) balances. The Accounts tab is for Monarch classification only and does not affect your projection. Switch to 'Monarch (live/cached)' mode in the Data Source control above to enable it."_
  - Disable the "Refresh from Monarch" button (`disabled` attribute + visual indicator).
  - Optionally dim the account table area.
- If `source_mode === "monarch"` and `account_count === 0`:
  - Show a different message: _"No cached accounts found. Click 'Refresh from Monarch' to pull live balances, or switch to Manual Entry mode in the Data Source control above."_

The existing JS that populates the accounts table runs on page load via `loadAccountsData()`. Add the mode-check logic at the end of that function.

**Files:** `templates/setup_panel.html`

**Dependencies:** Task 2.1 (confirms data is available).

**Verification:**
1. Open Setup Panel on `sample` scenario. Confirm banner appears and Refresh button is disabled.
2. Open Setup Panel on `default` scenario. Confirm normal Accounts behavior is unchanged.

---

### Task 2.3 — `api/refresh-monarch`: clean 409 response when Monarch not installed

Today, `api/refresh-monarch` catches all exceptions and returns `502` with a stack trace embedded in the error message. Add a specific check: if `MCP_PYTHON` does not exist, return a `409 Conflict` (or `503 Service Unavailable`) with a clean JSON payload explaining the situation, rather than a `502` with internal details.

```python
@app.post("/api/refresh-monarch")
async def api_refresh_monarch() -> JSONResponse:
    from src.monarch_bridge import MCP_PYTHON, fetch_raw_accounts, ...

    if not MCP_PYTHON.exists():
        return JSONResponse(
            {"ok": False, "error": "Monarch MCP server is not installed on this system. "
             "Use Manual Entry (synthetic) mode instead, or install and configure the Monarch MCP server."},
            status_code=503,
        )
    try:
        ...
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Monarch refresh failed: {exc}"}, status_code=502)
```

**Files:** `admin_app.py`

**Dependencies:** Task 1.1 (so that `MCP_PYTHON` reflects the configurable path).

**Verification:** Call `POST /api/refresh-monarch` on a machine without Monarch. Confirm `503` with clean error message in JSON (no stack traces, no Person 1-specific paths).

---

### Task 2.4 — Quick-edit Data Source radio: sync both radio groups

There are currently two data-source radio groups on the page — one in the quick-edit strip (`ds-radio-group`) and one inside the Synthetic Setup sub-tab (`synth-ds-radio-group`). They should always stay in sync. Add a JS event listener to each that updates the other when changed.

This is already a minor UX inconsistency that will become more noticeable as the page is used for Monarch-free scenarios.

**Files:** `templates/setup_panel.html`

**Dependencies:** None.

**Verification:** Switch mode in the quick-edit strip. Confirm the Synthetic Setup sub-tab radio reflects the change, and vice versa.

---

## Phase 3: Starter Template Scenario

**Objective:** Provide a clean, zero-filled, heavily-commented starting template that a new user (without Monarch) can clone as their first real scenario. `sample.toml` remains a reference/demo scenario with its fictional household and full inline documentation. `starter.toml` is a blank-slate template for a new user's actual household.

**Files:** `scenarios/starter.toml` (new file)

---

### Task 3.1 — Create `scenarios/starter.toml`

This file should:

- Set `[data_source].mode = "synthetic"` — no Monarch dependency.
- Set `is_default = false` (user will clone this and promote their copy to default).
- Use `# YOUR VALUE HERE` annotations on every required field.
- Have zero starting balances in `[synthetic_start]` with clear comments on what each bucket means.
- Include a single placeholder mortgage liability (`[[liabilities]]`) and a placeholder `SellHome` event, commented out, as the most common starting points.
- Include the same Social Security, Retire, and EndOfPlan event stubs as `sample.toml` but stripped of Alex/Sam-specific values.
- Include a `[display]` section with `projection_title = "My Household Plan"` as a prompt.
- Be ~100 lines total — short enough to read in one sitting, long enough to cover every required section.
- Include a header comment block explaining:
  - What each section is for.
  - What `synthetic_start` means (you enter your account balances manually).
  - That liabilities (mortgage, auto loans) need entries in both `[[liabilities]]` and `[synthetic_start.liability_balances]`.
  - How to clone this file to create a named scenario (`cp starter.toml scenarios/myhousehold.toml`, then edit `[scenario].slug` and `[scenario].name`).
  - How to run it: `python run.py --scenario myhousehold`.

**Structure of `starter.toml`:**

```
[scenario]
  name, slug, description, is_default = false

[data_source]
  mode = "synthetic"   # no Monarch required

[synthetic_start]
  taxable, trad_ira, roth, cash, home_value, vehicles
  [synthetic_start.property_values]   # one entry per property
  [synthetic_start.liability_balances]  # must match [[liabilities]] name entries

[simulation]
  start_year, end_year, render_modes

[display]
  projection_title

[person1]  # required fields: name, dob, life_expectancy, retirement_year, annual_take_home
           # contribution fields: contribution_method + gross_income + percent, OR annual_401k_contribution
           # social security: ss_start_age + social_security_benefits

[person2]  # same shape; omit if single-person household

[spending]
  retirement_annual, survivor_percent_of_retirement, debt_service_handling

[withdrawal_policy]
  cash targets + withdrawal orders (copy from sample.toml defaults)

[assumptions]
  stock_return, bond_return, inflation, equity_allocation

[[liabilities]]  # one entry per loan; commented-out example

[[events]]  # Retire (person1), Retire (person2), SocialSecurity (person1), SocialSecurity (person2)
            # EndOfPlan handled automatically from dob + life_expectancy
```

**Dependencies:** None.

**Verification:** Run `python run.py --scenario starter`. Confirm it runs without error and produces a deterministic projection with zero/placeholder values and no Monarch calls.

---

### Task 3.2 — Add `starter` to the Setup Panel scenario picker

The scenario picker in `setup_panel.html` is populated from the server by reading available `.toml` files in the `scenarios/` directory. Confirm `starter.toml` appears in the picker automatically (it should — `get_scenario()` already scans the directory). If not, investigate why and fix.

Add a visual indicator or tooltip to the starter scenario in the picker: _"Starting template — clone this to create your own scenario."_

**Files:** `templates/setup_panel.html`, `src/scenarios.py` (if needed)

**Dependencies:** Task 3.1.

**Verification:** Open the Setup Panel. Confirm "Starter Plan" (or whatever `[scenario].name` is set to) appears in the scenario picker dropdown.

---

### Task 3.3 — Update `README.md` with a "Getting Started Without Monarch" section

Add a top-level section to `README.md` titled **"Getting Started Without Monarch"** that explains:

1. Monarch Money is optional. The app works without it.
2. Clone `starter.toml` as your starting point.
3. Fill in your household details (names, ages, income, balances, retirement year).
4. Run `python run.py --scenario <yourslug>`.
5. Open the Setup Panel at `http://localhost:8010/setup` if running locally (or your configured URL) to edit via the web UI instead of editing TOML directly.
6. The "Synthetic Setup" tab in the Setup Panel is the GUI for entering your balances.
7. If you later want to connect Monarch, switch `[data_source].mode` to `"monarch"` in your scenario and configure the Monarch MCP server.

**Files:** `README.md`

**Dependencies:** Task 3.1.

**Verification:** Read through. Confirm every instruction is accurate and testable against the actual codebase at the time of writing.

---

## Phase 4: Setup Panel New-Scenario Workflow

**Objective:** Allow a user to create a new scenario from scratch within the Setup Panel without editing files manually. Today, cloning an existing scenario is the only non-file-system path.

**Problem today:** Clicking "Clone Scenario" copies the active scenario, which for a new user is likely `default.toml` — a Monarch-heavy scenario with 46 account classification entries, Person 1-specific values, and no synthetic balances. A non-Monarch user who clones `default.toml` gets a scenario that will fail to run without Monarch.

**Files:** `admin_app.py`, `templates/setup_panel.html`

---

### Task 4.1 — Add "New Scenario" button to Setup Panel action bar

Add a **"New from Template"** button (or rename "Clone Scenario" to offer two options: "Clone from Active" and "New from Template"). When "New from Template" is clicked:

1. Prompt for a scenario name and slug (same UX as Clone).
2. On the backend, copy `scenarios/starter.toml` (not the active scenario) to `scenarios/<new-slug>.toml`.
3. Write the new `[scenario].name` and `[scenario].slug` into the new file via `tomlkit`.
4. Redirect the panel to the new scenario.

**API change:** Add `POST /api/new-scenario` endpoint that accepts `{name, slug}`, copies `starter.toml`, and sets the scenario metadata. Return `{ok: true, slug: "..."}`.

If `starter.toml` doesn't exist at the time of the call, fall back to an inline minimal TOML string (the same content as Task 3.1) rather than failing.

**Files:** `admin_app.py`, `templates/setup_panel.html`

**Dependencies:** Task 3.1, existing Clone implementation (use as pattern).

**Verification:**
1. Click "New from Template". Enter name "Test Plan" / slug "test-plan".
2. Confirm `scenarios/test-plan.toml` is created with `[data_source].mode = "synthetic"`.
3. Confirm the panel switches to the new scenario.
4. Run `python run.py --scenario test-plan`. Confirm it runs without error.

---

### Task 4.2 — Clone source awareness: warn when cloning a Monarch scenario

When "Clone Scenario" is used and the source scenario has `data_source.mode = "monarch"` (or no `[data_source]` section at all), show a brief warning banner before completing the clone:

> _"The source scenario is configured for Monarch data. The cloned scenario will also require Monarch until you switch to Manual Entry mode in the Data Source control. If you don't use Monarch, consider using 'New from Template' instead."_

This is a soft warning — the clone proceeds as normal. It's just a disclosure so the user understands why their new scenario might fail to run immediately.

**Files:** `templates/setup_panel.html`

**Dependencies:** None — can be added independently of 4.1.

**Verification:** Clone a Monarch scenario. Confirm warning appears. Dismiss and verify clone completes normally.

---

## Phase 5: Long-term / Structural (Future Work)

These items are lower-priority and depend on decisions about the project's direction (open-source release, community users, etc.). They are documented here for completeness but are not scheduled.

### 5.1 — Suppress `[accounts]` section from synthetic scenarios

For a scenario in `mode = "synthetic"`, the `[accounts]` section is dead weight — it's a Monarch account classification map that does nothing when starting balances come from `[synthetic_start]`. A new user who reads their TOML will be confused by a large section of Monarch-named account strings.

**Option A:** When `starter.toml` is used as the template (Task 3.1), simply omit the `[accounts]` section. New scenarios created from the starter have no `[accounts]` section. The model handles a missing `[accounts]` section gracefully — it's already tested by `sample.toml`.

**Option B:** In the Setup Panel, when `source_mode === "synthetic"`, hide the "Data Sources & Accounts" sub-tab entirely and surface only the Synthetic Setup tab.

Option A is the right default for new users. Option B is a UI polish step.

**Risk:** Ensure `run.py` and `model.py` both gracefully accept a scenario with no `[accounts]` section. Verify with `sample.toml` (which already has no `[accounts]` section) — it already works.

### 5.2 — Abstract `DataSourceProvider` protocol

If a third balance-retrieval mechanism is ever added (CSV import, manual bank balance entry, another aggregator), it would be worth creating a `DataSourceProvider` ABC with two initial implementations: `MonarchProvider` and `SyntheticProvider`. Today, the three-branch `if/elif/else` in `run.py:main()` is easy to read and maintain. This abstraction is only warranted if a third provider is actually being added.

**Trigger:** PR or plan proposing a third data source (e.g. CSV import, OFX, Plaid).

### 5.3 — Local-only CSV balance import

A user who does not use any aggregator but wants real-balance anchors (rather than estimated synthetic balances) could supply a simple CSV with columns `name,category,balance`. `run.py` would read this as a third data source mode (`data_source.mode = "csv"`, `data_source.csv_path = "..."`).

This is a lightweight alternative to Monarch that requires no external service. Useful for open-source release.

**Scope:** `src/csv_bridge.py` (new, analogous to `monarch_bridge.py`), one new `data_source.mode` value, one new CLI option, one new Setup Panel radio. No model changes.

### 5.4 — Docker Compose for non-Person 1 deployments

The current `Dockerfile.config-editor` and nginx configuration bake in Person 1's deployment paths (`/srv/web-projects/finances`, `casalemuria.lan`). For open-source release, these should be configurable via environment variables or a `docker-compose.override.yml`.

This is blocked on a broader decision to release the project publicly.

---

## Dependency Map

```
Phase 1                Phase 2                Phase 3           Phase 4
──────────             ──────────             ──────────        ──────────
1.1 (pre-flight)  ──→  2.3 (clean 502)        3.1 (starter)  ──→  4.1 (new from template)
1.2 (config path) ─┐   2.2 (accounts banner)  3.2 (picker)       4.2 (clone warning)
1.3 (run.py msg)  ─┘   2.4 (radio sync)       3.3 (readme)

Phase 1 tasks have no cross-dependencies; all can be done in one commit.
Phase 2 depends on Phase 1 (specifically 2.3 depends on 1.1 for MCP_PYTHON check).
Phase 3 is independent of Phases 1–2.
Phase 4 depends on Phase 3.1 (needs starter.toml to exist).
```

---

## Acceptance Criteria (definition of done)

A new developer can verify the plan is fully complete when all of the following are true:

1. `python run.py --scenario starter` runs on a machine without Monarch and produces a projection HTML file.
2. `python run.py` on a machine without Monarch (with a `mode = "monarch"` scenario) exits cleanly with a readable error message — no Python traceback, no Person 1-specific paths.
3. `POST /api/refresh-monarch` on a machine without Monarch returns a JSON response with `ok: false` and a human-readable explanation — no 502, no stack trace.
4. The Setup Panel on `sample` (or any synthetic-mode scenario) shows the synthetic-mode banner in the Accounts tab, and the "Refresh from Monarch" button is disabled.
5. "New from Template" in the Setup Panel creates a scenario from `starter.toml` with `data_source.mode = "synthetic"`, and that scenario runs without error.
6. `README.md` has a "Getting Started Without Monarch" section that accurately describes the flow in items 1 and 5.
7. All existing scenarios (default, comfortable, optimistic, etc.) continue to run normally with `python run.py --offline` and `python run.py` (with Monarch configured).

---

## Pitfalls to Watch

- **`sample.toml` must not be modified.** It is the canonical reference scenario with inline documentation. Leave it exactly as-is. `starter.toml` is separate.
- **`[accounts]` section omission in synthetic scenarios.** Confirm `run.py` handles `config.get("accounts", {})` gracefully when the key is absent. It already does — but verify with a run on `starter.toml` before declaring Phase 3 complete.
- **`starter.toml` must have a unique `[scenario].slug`.** The scenario discovery system (`src/scenarios.py`) reads the `slug` from the TOML, not from the filename. Set `slug = "starter"` in the file and do not use this slug for a real household scenario.
- **Task 4.1 (new-scenario API) must write `[scenario].slug` into the new file.** The `_synthetic_inputs_from_config()` function and scenario manifest builder read the slug from the TOML, not from the filename. If the slug is left as `"starter"` in the cloned file, two scenarios will have the same slug and the manifest will be corrupted.
- **Docker container must be rebuilt after any `admin_app.py` change that adds new imports.** If Phase 4 adds an import that isn't already in the container's installed packages, you'll get `ModuleNotFoundError` at container startup. Rebuild with `docker compose build nwn-config-editor && docker compose up -d --force-recreate nwn-config-editor`.
- **The Synthetic Setup tab's inputs are disabled when `source_mode === "monarch"`.** When testing Phase 2 changes, verify that switching to synthetic mode in the radio also enables the Synthetic Setup inputs. The disable/enable logic is already in place but should be re-verified after the radio-sync work in Task 2.4.
- **`synthetic_start.liability_balances` keys must exactly match `[[liabilities]].name` entries.** In `starter.toml`, if a placeholder liability is included, the key in `[synthetic_start.liability_balances]` and the `name` field in `[[liabilities]]` must be identical strings. A mismatch silently produces a zero starting balance for the liability, making it appear paid off from year one.
