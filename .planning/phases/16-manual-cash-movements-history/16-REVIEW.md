---
phase: 16-manual-cash-movements-history
reviewed: 2026-07-15T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - app/models.py
  - app/routes/__init__.py
  - app/routes/finance.py
  - app/routes/mobile_finance.py
  - app/services/finance.py
  - app/templates/pages/finance.html
  - app/templates/partials/cash_balance.html
  - app/templates/partials/withdraw_form.html
  - app/templates/partials/deposit_form.html
  - app/templates/partials/cash_negative_balance.html
  - app/templates/partials/cash_history_rows.html
  - app/templates/mobile_pages/finance.html
  - app/templates/mobile_partials/cash_history_cards.html
  - app/templates/mobile_partials/cash_history_load_more.html
  - tests/test_finance.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-07-15
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the Phase 16 manual cash-movements + history feature: the extended
`CASH_CATEGORIES`/`CASH_BUCKETS` model constants, the single-write finance
service (`record_manual_movement` / `record_cash_movement` / `compute_balance`
/ `cash_history_view`), the desktop and mobile finance routers, the shared
withdraw/deposit form partials, the desktop table + mobile card history views,
and the test suite.

The implementation is strong against the stated invariants:
- **Money** is integer kopecks everywhere; `to_cents` is the only parser and
  rejects blank/zero/negative/non-finite input server-side.
- **Portable ORM only** — the service uses `select`/`func`/`in_`; no
  SQLite-specific SQL in production code.
- **Autoescape XSS** — `note` and category labels never use `|safe`; two tests
  (`test_web_cash_history_escapes_note`, `test_mobile_cash_history_escapes_note`)
  prove markup is escaped.
- **Single write path** — both routers delegate parse/sign/allow-list/comment/
  negative-gate to the service; the sign is derived server-side from the
  category, never trusted from the client.

No blockers found. One warning concerns an unhandled result branch on the
deposit route (defense-in-depth gap), plus three minor info items.

## Warnings

### WR-01: Deposit route ignores the service's `negative_balance` result branch

**File:** `app/routes/finance.py:163-203` (and mirror `app/routes/mobile_finance.py:171-211`)
**Issue:**
`finance_deposit` calls `record_manual_movement(...)` *without* `confirm` and
then branches only on `if errors:`, otherwise returning `_movement_success(...)`.
It never inspects `result` for a `negative_balance` key.

Direction in the service is derived from the **category**, not the endpoint
(`is_withdrawal = category in CASH_BUCKETS["withdrawal"]`, service line 114).
A crafted POST to `/finance/deposit` (or `/m/finance/deposit`) with a
`withdrawal_*` category therefore makes `is_withdrawal=True` and can reach the
negative-balance gate (service lines 143-147), which returns
`({"negative_balance": {...}}, {})` with **zero writes**. Because `errors` is
empty, the deposit route falls through to `_movement_success` and renders a
"success" response (fresh empty form) even though nothing was recorded.

No data is corrupted (the service correctly wrote no row, and the OOB balance /
history refresh reflect the true unchanged state), and the path is not reachable
through the UI (the deposit form only offers `deposit_*` options). But the
shared service exposes a result shape the deposit route neither handles nor
guards against, in a security-sensitive write path the phase explicitly wants
hardened. The symmetric mismatch (a `withdrawal_*` category posted to the
deposit endpoint when the balance covers it) writes a real расход row via the
"deposit" endpoint — allow-listed and correctly signed, but endpoint semantics
and movement direction diverge.

**Fix:** Enforce endpoint↔direction at the route as defense-in-depth, e.g. in
`finance_deposit` reject any non-`deposit_*` category before/around the service
call, or explicitly treat a `negative_balance` result as an error on the deposit
route:
```python
result, errors = record_manual_movement(
    session, category=category, amount_raw=amount, note=note
)
# Deposits must never resolve to a withdrawal direction; a negative_balance
# result means a withdrawal_* category reached this endpoint.
if result and result.get("negative_balance"):
    errors = {"category": DEPOSIT_CATEGORY_ERROR}
```
Alternatively, gate on bucket membership in the route:
`if category not in CASH_BUCKETS["deposit"]: errors["category"] = DEPOSIT_CATEGORY_ERROR`.

## Info

### IN-01: `compute_balance` queried twice in the negative-balance gate

**File:** `app/services/finance.py:143-147`
**Issue:** The gate runs `compute_balance(session)` once in the `if` condition
(line 143) and again to build the warn payload (line 145) — two identical
`SUM(amount_cents)` queries. Correctness is unaffected under the single-writer
model, but it is a redundant round-trip.
**Fix:** Compute once and reuse:
```python
if is_withdrawal and confirm != "1":
    balance = compute_balance(session)
    if balance + amount_cents < 0:
        return {"negative_balance": {"balance": balance, "amount": -amount_cents}}, {}
```

### IN-02: Unvalidated `bucket` echoed back into render context

**File:** `app/services/finance.py:210` (`"bucket": bucket or ""`) → consumed in
`app/templates/partials/cash_history_rows.html:26-27`,
`app/templates/mobile_pages/finance.html:25-27`,
`app/templates/mobile_partials/cash_history_load_more.html:11`
**Issue:** `cash_history_view` returns the **raw** client bucket string, not a
normalized/validated value. For a tampered bucket (e.g. `?bucket=bogus`) the
rows are correctly unfiltered (unknown bucket ignored), but the «Тип» dropdown
marks neither «Все типы» (`{% if not bucket %}` is false for a truthy junk
value) nor any real option as `selected`, so the control desyncs from the
displayed (unfiltered) result. The mobile load-more button also interpolates
`bucket={{ bucket }}` into its `hx-get` URL unencoded. Autoescape prevents XSS;
this is cosmetic/robustness only and self-inflicted via URL tampering.
**Fix:** Return the normalized bucket from the service — e.g.
`"bucket": bucket if CASH_BUCKETS.get(bucket) else ""` — so an unknown value
resolves to «Все типы» in the UI and never reaches the load-more URL.

### IN-03: `SAVE_FAILED_ERROR` constant duplicated across three modules

**File:** `app/services/finance.py:27`, `app/routes/finance.py:32`,
`app/routes/mobile_finance.py:33` (and `DEPOSIT_CATEGORY_ERROR` in both routers)
**Issue:** The same RU copy strings are re-declared in three places. Drift risk
if one copy is edited later.
**Fix:** Define the copy once (e.g. in `app.services.finance`) and import it
into the routers, or centralize UI copy constants in one module.

---

_Reviewed: 2026-07-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
