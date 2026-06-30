# Survivor Phase & Post-Death Modeling — Program Logic Reference

This document captures the internal mechanics of how NWN handles the
survivor period, death-year spending, and post-death expense termination.
Reading this before touching survivor-phase config or model code saves
tracing through 4–5 entry points in model.py.

---

## 1. SpendingShift Phase — The `retirement_annual` Dead-Code Trap

**File:** `model.py`, lines 1093–1100

```python
# Line 1093 — ONLY fires for "retirement" or "retirement_and_survivor"
if phase in {"retirement", "retirement_and_survivor"} and "retirement_annual" in event:
    retirement_spend = float(event["retirement_annual"])

# Line 1096 — fires for "survivor" or "retirement_and_survivor"
if phase in {"survivor", "retirement_and_survivor"}:
    if "survivor_annual" in event:
        survivor_spend = float(event["survivor_annual"])
    elif "survivor_percent_of_retirement" in event:
        survivor_spend = retirement_spend * float(event["survivor_percent_of_retirement"])
```

**Critical rule:** When `phase = "survivor"`, line 1093 is **skipped**.
The `retirement_annual` field in the event is dead code. The
`survivor_percent_of_retirement` on line 1100 multiplies against the
*original* base `retirement_spend` from config, not the event value.

**Config symptom:** A SpendingShift like this silently produces $75K × 0.5
= $37.5K real instead of the intended $25K real:
```toml
phase = "survivor"             # ← dead code for retirement_annual
retirement_annual = 50000      # ← never consumed
survivor_percent_of_retirement = 0.5
```

**Fix:** Use `phase = "retirement_and_survivor"` so both lines fire, OR
set `survivor_annual` directly.

**When `retirement_and_survivor` fires (correct behavior):**
1. Line 1093: `retirement_spend = 50000` (event value replaces base)
2. Line 1100: `survivor_spend = 50000 × 0.5 = 25000`

---

## 2. Spending Computation Flow in the Yearly Loop

**File:** `model.py`, lines 3255–3286

```python
# Each year in the projection loop:
target_spend = float(spending["retirement_annual"])      # config value
survivor_spend = resolve_survivor_spending(spending)     # config value
both_retired = person1_retired and person2_retired
one_deceased = person1_deceased or person2_deceased

if one_deceased or both_retired:
    # Apply SpendingShift events:
    target_spend, survivor_spend = resolve_spending_shift_for_year(
        base_retirement_spend=target_spend,
        base_survivor_spend=survivor_spend,
        events=events,
        year=year,
        in_survivor_phase=one_deceased,
    )
    base_spend = survivor_spend if one_deceased else target_spend
    annual_spend = base_spend
    if spending_basis == "real":
        annual_spend = grow_annual_amount(base_spend, inflation, years_elapsed)
```

**Key observations:**
- `base_spend` is the value *before* CPI adjustment when `spending_basis = "real"`
- CPI growth uses `years_elapsed = year - simulation.start_year`
- In pre-retirement (both working): uses `resolve_pre_retirement_spending()` instead
- SpendingShift events only fire when at least one person is retired or deceased

**Example: 2058 survivor, Default scenario after fix:**
- `survivor_spend` = 25000 (from SpendingShift: 50000 × 0.5)
- `annual_spend` = 25000 × (1.03)^(2058-2026) ≈ $64,377 (nominal)

---

## 3. Expense Events — Nominal, Recurring, No Auto-Stop at Death

**File:** `model.py`, lines 2972–2993

```python
elif etype == "Expense":
    if event["year"] == year:
        event_cash_flow += event["amount"]
        # ... chart labels, etc.
```

**Expense amounts are nominal flat values.** A $25K expense in 2057
costs $25K nominal every year it fires — there is no CPI adjustment
for Expense events.

**Recurring expansion** (`_expand_recurring_events`, lines 746–813):
- `repeat_until_year` defaults to `simulation.end_year` when absent
- Each concrete occurrence gets the **same nominal amount** as the template
- Recurrence is purely arithmetic: `anchor_year + occurrence × interval`

**The model does not auto-stop expenses at death.** If a Health Expenses
event runs from 2057 with no `repeat_until_year`, it continues through
2066 (simulation end) regardless of who died. You must manually set
`repeat_until_year = 2057` to terminate at Person 1's death.

**Expense kind semantics:**
- `expense_kind = "mandatory"` → shown with 💸 icon
- `expense_kind = "discretionary"` → shown with 🏖️ icon
- `funding = "cash_reserve_first"` → expense can tap cash reserve before
  retirement buckets (affects withdrawal order priority)

---

## 4. Post-Death Expense Audit Checklist

Every scenario that includes a death-triggered relocation needs:

| Check | What to look for |
|---|---|
| **SpendingShift phase** | Is `phase = "survivor"` preventing `retirement_annual` from being consumed? |
| **Health Expenses (90s)** | Does it have `repeat_until_year` set to the death year? |
| **Caregiving Expenses** | Does it have `repeat_until_year` set to the death year? |
| **Property Taxes / Insurance** | Already capped at 2057 in all scenarios (correct) — but verify for any new scenario |
| **Big Vacation recurring** | Already capped at 2054 in all scenarios — verify for any new scenario |
| **Survivor spending level** | Is the resulting survivor spending reasonable for the post-death location and family support? |

---

## 5. Social Security Income — Flat Nominal, No CPI Growth

**File:** `model.py`, lines 3853–3858

```python
for event in events:
    if event["type"] == "SocialSecurity" and event.get("person") == person_key:
        if year >= event["year"]:
            annual_ss = event.get("monthly_benefit", 0) * 12
            ss_income += annual_ss
```

SS benefits from SSA.gov estimates are treated as **fixed nominal values**.
The `monthly_benefit` from `[person].social_security_benefits.<age>` is
used directly — no inflation growth after the claiming year.

SS income does NOT go through `_project_person_take_home()` which is
where wage growth (raise + inflation) is applied.

---

## 6. SS Survivor Benefit — Steps Up in the Year After Death

**File:** `model.py`, lines 1933–1996

```python
def _apply_survivor_social_security(...):
    # Only fires when year > death_year
    death_year = _death_year(events, deceased_key)
    if death_year is None or int(year) <= death_year:
        return  # survivor applies from year AFTER death onward

    # Survivor gets the higher of their own or deceased's SS
    if deceased_annual > survivor_parts["ss_income"]:
        survivor_parts["ss_income"] = deceased_annual
```

- In the **death year** (`year == death_year`): no survivor benefit adjustment.
  The model treats both as alive for the full year's cash flow.
- From **year + 1** onward: survivor SS steps up to the higher benefit.
- This means the survivor phase shading on the chart starts at `death_year + 1`.

---

## 7. Monte Carlo Failure Clustering

**Where failures happen in post-fix Default (84% success):**
- All failures are in 2051–2057 (pre-Indonesia)
- Peak failure year: 2057 (16%)
- Failures are triggered by pre-2057 spending pressure (retirement spend +
  caregiving + health expenses) under poor market sequences
- The Indonesia-phase corrections (fixing spending from $157K → $64K/yr)
  primarily help the runs that survive past 2057

**Where failures happen in aspirational scenarios (~50% success):**
- Failure range: 2040–2057 (even earlier, driven by earlier retirement)
- Most "failures" are partial spending shortfalls, not full depletion
  (prob NW < $0 is 0–0.8%)
- The failure mode is `spending_shortfall` with `minimum_spending_funded_ratio = 1.0`
  and zero grace period — even $1 of shortfall counts as failure

---

## 8. Withdrawal Order by Phase

**Current Default config:**

| Phase | Order |
|---|---|
| Accumulation | `cash_above_target → taxable → roth → trad_ira → cash_below_target` |
| Retirement | `cash_above_target → trad_ira → taxable → roth → cash_below_target` |
| Survivor | `cash_above_target → trad_ira → taxable → roth → cash_below_target` |

The retirement and survivor phases prefer `trad_ira` before `taxable`.
This is correct only when RMDs are enabled — without RMDs, drawing
trad_ira first generates higher taxable income per dollar with no
compensating benefit (an earlier ~$780K end-state gap was observed).

---

## Quick Debug Commands

```bash
# Validate a single scenario config (fast TOML + model init check)
.venv/bin/python run.py --offline --scenario <slug>

# Check deterministic spending in a specific year
.venv/bin/python -c "
import csv
with open('output/scenarios/default/deterministic/sidecars/projection_yearly.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        if int(row['year']) == 2058:
            print(f'spend={row[\"annual_spend\"]}, events={row[\"event_outflow_total\"]}')
"

# Check MC summary
.venv/bin/python -c "
import json
s = json.load(open('output/scenarios/default/monte_carlo/sidecars/simulation_summary.json'))
print(f'Success: {s[\"success_rate\"]*100:.0f}% P10: \${s[\"terminal_total_net_worth_p10\"]:,.0f}')
"

# List enabled events including runtime-synthesized
.venv/bin/python -c "
import tomllib, json
cfg = tomllib.load(open('scenarios/default.toml','rb'))
for e in cfg.get('event', cfg.get('events', [])):
    if e.get('enabled'):
        print(f'{e[\"type\"]:20s} {e.get(\"label\",\"\"):40s} year={e.get(\"year\",\"\")} until={e.get(\"repeat_until_year\",\"\")}')
"
```
