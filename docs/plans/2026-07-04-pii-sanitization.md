# PII Sanitization Plan — Net Worth Navigator

> **Goal:** Remove personal identifying information (names, birth dates) from the current codebase and full Git history so the repository can be shared with friends and open-sourced.

**Approach:** Two-stage process.

1. **Stage 1** — Fix PII in current code at HEAD (source files, templates, tests, docs). Commit clean state.
2. **Stage 2** — Run `git filter-repo` to rewrite full commit history with text and author metadata replacements.

**Why staged:** Stage 1 lets us verify the code still works (tests pass, UI renders) before committing to a history rewrite. Stage 2 propagates replacements into every past commit atomically.

**Current PII inventory** (confirmed 2026-07-04):

| Category | Current location | History |
|---|---|---|
| Author name: `Matt` | Committer metadata (55 commits) | All 191 commits via `Matt <LemurTech@xentana.com>` |
| Email: `LemurTech@xentana.com` | Committer metadata | Same |
| First names in source/tests/docs | `tests/*.py`, `README.md`, `docs/projectbrief.md`, `src/references/*.md` | All commits touching those files |
| Surnames: `Household`, `Household` | `README.md`, `docs/projectbrief.md` | All commits |
| Birth dates: `1967-04-23`, `1976-10-02` | `tests/*.py` | All commits touching test files |
| Field IDs: `person1_retirement_year`, `person2_retirement_year` | `admin_app.py`, `templates/setup_panel.html` | All commits since Setup Panel creation |
| Scenario slugs: `early-death-person1`, `early-death-person2` | `docs/activeContext.md` | All docs commits |
| Test account name: `401k Person 1 (6-01)` | `tests/test_recurring_events.py` | Old config.toml + all test commits |
| Test labels: `Retire (Person 1 legacy)`, `SS (Person 1 legacy)` | `tests/test_recurring_events.py` | Test commits |

---

## Stage 1 — Current Code Cleanup

This stage fixes PII in every tracked source file at HEAD. Test assertions are updated in lockstep with test fixture data so tests remain passing.

### Task 1.1 — Rename field IDs in `admin_app.py`

**Objective:** Replace personal-name field ID mappings with generic `person1`/`person2` equivalents.

**File:** `admin_app.py:1490-1491`

**Change:** In `_QUICK_CONTROL_MAP`:
- `"person1_retirement_year"` → `"person1_retirement_year"` (maps to same TOML path `"person1.retirement_year"`)
- `"person2_retirement_year"` → `"person2_retirement_year"` (maps to same TOML path `"person2.retirement_year"`)

**Verification:** The TOML path value stays `("person1.retirement_year", int)` — only the frontend-facing key changes. No logic change, just a rename.

### Task 1.2 — Rename field IDs in `templates/setup_panel.html`

**Objective:** Replace all 10 occurrences of `matthew_*`/`weny_*` HTML IDs, JS variables, and payload keys with `person1_*`/`person2_*`.

**File:** `templates/setup_panel.html`

**Replacements:**
| Old | New | Occurrences |
|---|---|---|
| `id="person1_retirement_year"` | `id="person1_retirement_year"` | Line 456 (HTML) |
| `id="person2_retirement_year"` | `id="person2_retirement_year"` | Line 469 (HTML) |
| `c.person1_retirement` | `c.person1_retirement` | Lines 862, 963, 1014 |
| `c.person2_retirement` | `c.person2_retirement` | Lines 864, 964, 1015 |
| `getField('person1_retirement_year')` | `getField('person1_retirement_year')` | Line 1096 |
| `getField('person2_retirement_year')` | `getField('person2_retirement_year')` | Line 1097 |
| `body.person1_retirement_year` | `body.person1_retirement_year` | Line 1098 |
| `body.person2_retirement_year` | `body.person2_retirement_year` | Line 1099 |
| `wireSlider(..., 'person1_retirement_year', ...)` | `wireSlider(..., 'person1_retirement_year', ...)` | Line 963 |
| `wireSlider(..., 'person2_retirement_year', ...)` | `wireSlider(..., 'person2_retirement_year', ...)` | Line 964 |

**Verification:** After all replacements, no occurrences of `matthew_retirement` or `weny_retirement` remain in the file:
```
grep -c 'matthew_retirement\|weny_retirement' templates/setup_panel.html
# Expected: 0
```

### Task 1.3 — Sanitize test files

**Objective:** Replace all `name: "Person 1"` / `name: "Person 2"` test data and assertions with generic names `"Person 1"` / `"Person 2"`.

**Files affected:**
- `tests/test_assumptions_summary.py`
- `tests/test_recurring_events.py`
- `tests/test_sidecars.py`
- `tests/test_simulation_modes.py`
- `tests/test_tax_model.py`
- `tests/test_withdrawal_policy.py`

**Step 1 — Rename test data person names:**

In each test file, replace:
- `"name": "Person 1"` → `"name": "Person 1"` (fixture data)
- `"name": "Person 2"` → `"name": "Person 2"` (fixture data)
- `"name": "Person 1",` → `"name": "Person 1",`
- `"name": "Person 2",` → `"name": "Person 2",`

**Step 2 — Rename test assertions in lockstep:**

Replace all assertion strings that reference Person 1/Person 2:
- `self.assertIn("Person 1", html)` → `self.assertIn("Person 1", html)` (test_assumptions_summary.py:47)
- `self.assertIn("Person 2", html)` → `self.assertIn("Person 2", html)` (test_assumptions_summary.py:48)
- `self.assertIn("<th>Person 1</th>", html)` → `self.assertIn("<th>Person 1</th>", html)` (test_assumptions_summary.py:118)
- `self.assertIn("<th>Person 2</th>", html)` → `self.assertIn("<th>Person 2</th>", html)` (test_assumptions_summary.py:119)
- `"Person 1 earned income"` → `"Person 1 earned income"`
- `"Person 2 earned income"` → `"Person 2 earned income"`
- `"Traditional IRA / 401k contributions — Person 1"` → `"Traditional IRA / 401k contributions — Person 1"`
- `"Traditional IRA / 401k contributions — Person 2"` → `"Traditional IRA / 401k contributions — Person 2"`
- `"Roth contributions — Person 1"` → `"Roth contributions — Person 1"`
- `"Roth contributions — Person 2"` → `"Roth contributions — Person 2"`
- `"Traditional IRA / 401k — Person 1"` → `"Traditional IRA / 401k — Person 1"`
- `"Traditional IRA / 401k — Person 2"` → `"Traditional IRA / 401k — Person 2"`
- `"Roth — Person 1"` → `"Roth — Person 1"`
- `"Roth — Person 2"` → `"Roth — Person 2"`
- `"Trad IRA \u002f 401k \u2014 Person 1"` → `"Trad IRA \u002f 401k \u2014 Person 1"`
- `"Trad IRA \u002f 401k \u2014 Person 2"` → `"Trad IRA \u002f 401k \u2014 Person 2"`
- `"Roth \u2014 Person 1"` → `"Roth \u2014 Person 1"`
- `"Roth \u2014 Person 2"` → `"Roth \u2014 Person 2"`
- `"Retire (Person 1 legacy)"` → `"Retire (Person 1 legacy)"` (test_recurring_events.py:571, 582)
- `"SS (Person 1 legacy)"` → `"SS (Person 1 legacy)"` (test_recurring_events.py:721, 735)
- `"401k Person 1 (6-01)"` → `"401k Person 1 (6-01)"` (test_recurring_events.py:1078, 1083, 1098, 1107, 1121, 1130, 1145, 1160)

**Step 3 — Verify no Person 1/Person 2 remain in test files:**
```
grep -rn "Person 1\|Person 2" tests/ --include="*.py" | grep -v __pycache__
# Expected: 0 matches
```

### Task 1.4 — Sanitize README.md

**File:** `README.md`

| Old | New | Location |
|---|---|---|
| `Household household` | `Household` | Line 3 |
| `matthew`/`weny` compatibility paths | `person1`/`person2` compatibility paths | Line 243 |

### Task 1.5 — Sanitize `docs/projectbrief.md`

**File:** `docs/projectbrief.md`

| Old | New | Location |
|---|---|---|
| `Owner: Matt` | `Maintainer:` (remove name) | Line 3 |
| `Household household` | `Household` | Line 8 |
| `for both Person 1 and Person 2` | `for both persons` | Line 14 |
| `Person 1 and Person 2 with independent retirement dates` | `both persons with independent retirement dates` | Line 24 |
| `Matt — owner, primary user` | `Person 1 — primary user` | Line 61 |
| `Person 2  — modeled household member` | `Person 2 — modeled household member` | Line 62 |

### Task 1.6 — Sanitize `docs/activeContext.md`

**File:** `docs/activeContext.md`

| Old | New | Line |
|---|---|---|
| `early-death-person1` | `early-death-person1` | 42 |
| `Person 1 passes in his 60s` | `Person 1 passes in their 60s` | 42 |
| `early-death-person2` | `early-death-person2` | 43 |
| `Person 2 passes in her 60s` | `Person 2 passes in their 60s` | 43 |
| `Confirm Person 2 SS estimate` | `Confirm Person 2 SS estimate` | 84 |

### Task 1.7 — Sanitize `src/references/survivor-phase-modeling.md`

**File:** `src/references/survivor-phase-modeling.md`

| Old | New | Line |
|---|---|---|
| `to terminate at Person 1's death.` | `to terminate at Person 1's death.` | 110 |

### Task 1.8 — Run tests

```
cd /home/lemurtech/Net-Worth-Navigator
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests pass (no regressions from name changes).

### Task 1.9 — Commit

```
git add -A
git commit -m "refactor: sanitize personal information from codebase

Replace Person 1/Person 2 names with Person 1/Person 2, rename field IDs 
(person1_retirement_year→person1_retirement_year), replace surnames 
with generic references. Test data and assertions updated in lockstep."
```

---

## Stage 2 — Git History Rewrite (git filter-repo)

Runs after Stage 1 is committed. Rewrites every commit in history with the full set of replacements.

### Prerequisites

```bash
# Install git-filter-repo
pip install git-filter-repo

# Make a bare backup clone
cd /home/lemurtech
git clone --mirror /home/lemurtech/Net-Worth-Navigator Net-Worth-Navigator-backup.git
```

### Patterns file

Create `sanitize-patterns.txt`:

```
LemurTech@xentana.com==>LemurTech@xentana.com
1967-04-23==>1967-04-23
1976-10-02==>1976-10-02
Household==>Household
Household==>Household
person1_retirement_year==>person1_retirement_year
person2_retirement_year==>person2_retirement_year
401k Person 1 (6-01)==>401k Person 1 (6-01)
Retire (Person 1 legacy)==>Retire (Person 1 legacy)
SS (Person 1 legacy)==>SS (Person 1 legacy)
Person 2 earned income==>Person 2 earned income
Person 1 earned income==>Person 1 earned income
Traditional IRA / 401k contributions — Person 1==>Traditional IRA / 401k contributions — Person 1
Traditional IRA / 401k contributions — Person 2==>Traditional IRA / 401k contributions — Person 2
Roth contributions — Person 1==>Roth contributions — Person 1
Roth contributions — Person 2==>Roth contributions — Person 2
Traditional IRA / 401k — Person 1==>Traditional IRA / 401k — Person 1
Traditional IRA / 401k — Person 2==>Traditional IRA / 401k — Person 2
Roth — Person 1==>Roth — Person 1
Roth — Person 2==>Roth — Person 2
Trad IRA \u002f 401k \u2014 Person 1==>Trad IRA \u002f 401k \u2014 Person 1
Trad IRA \u002f 401k \u2014 Person 2==>Trad IRA \u002f 401k \u2014 Person 2
Roth \u2014 Person 1==>Roth \u2014 Person 1
Roth \u2014 Person 2==>Roth \u2014 Person 2
early-death-person1==>early-death-person1
early-death-person2==>early-death-person2
Matt ==>Matt  (trailing space intentional — matches "Matt " as author name)
```

> **Order matters:** Put more specific/longer patterns first so they match before shorter substrings.

### Run filter-repo

```bash
cd /home/lemurtech/Net-Worth-Navigator

# Rewrite author name + email
git filter-repo --force \
  --name-callback 'name.replace(b"Matt", b"Matt")' \
  --email-callback 'email.replace(b"LemurTech@xentana.com", b"LemurTech@xentana.com")' \
  --replace-text sanitize-patterns.txt
```

### Verify

```bash
# No author with old name/email should remain
git log --all --format='%an <%ae>' | sort -u | grep -i "matthew"
# Expected: no output

# No occurrences of old patterns in any commit
git grep -i "Matt\|Person 2 \|Household\|1967-04-23\|1976-10-02" $(git rev-list --all) | head -5
# Expected: no output or only benign false positives

# Verify the latest commit (Stage 1's commit) is consistent
git log --oneline -1
```

### Push

```bash
# Force push to remote (requires force push allowed on default branch)
git remote -v
git push --force --all origin
git push --force --tags origin
```

### Cleanup

```bash
# Remove patterns file (it lives in the repo tree and was rewritten too)
rm sanitize-patterns.txt

# Local clones will need fresh fetch
# Tell anyone with a clone to:
#   git fetch --all
#   git reset --hard origin/main
```

---

## Acceptance Criteria

1. No `Matt`, `Person 2 `, `Household`, `Household` in any commit's content or metadata.
2. No `1967-04-23` or `1976-10-02` birth dates in any commit.
3. No `person1_retirement_year`, `person2_retirement_year` in any commit.
4. No `LemurTech@xentana.com` author email in any commit.
5. All tests pass on the Stage 1 commit (`pytest tests/ -v`).
6. The current sample/starter scenarios (`sample.toml`, `starter.toml`) remain unchanged (they were already generic).
