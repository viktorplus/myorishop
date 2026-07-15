---
phase: 15-cash-ledger-foundation
verified: 2026-07-14T21:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open /finance and /m/finance in a real browser after a real sale + real return through the UI forms"
    expected: "«Баланс кассы» shows the current figure with no currency glyph; registering a sale through the sale form visibly raises the balance by the total; registering a return against it visibly restores the pre-sale balance"
    why_human: "Plan 15-04's own <verification> section explicitly defers this to end-of-phase human-check (human_verify_mode = end-of-phase) — visual rendering/format polish and a full click-through via the actual HTML forms (not direct service calls) cannot be fully confirmed by static grep/pytest, even though the same claims are already proven at the service+route-render layer by automated tests"
---

# Phase 15: Cash Ledger Foundation Verification Report

**Phase Goal:** Every sale credits the till and every return debits it symmetrically, and the operator can see the resulting balance in a new «Финансы» section
**Verified:** 2026-07-14T21:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator sees a new «Финансы» nav section showing the current cash balance | ✓ VERIFIED | `app/templates/base.html:39` has `href="/finance"` nav link labeled «Финансы»; `app/templates/mobile_pages/home.html:14` has `href="/m/finance"` mobile tile; both routes registered in `app/main.py:72,83` and render `pages/finance.html`/`mobile_pages/finance.html` with `<h1>Баланс кассы</h1>` |
| 2 | Registering a sale immediately increases the displayed cash balance by the sale's total amount | ✓ VERIFIED | `app/services/sales.py:271-277` stages `finance.record_cash_movement(category="sale", amount_cents=total_cents, sale_id=header.id, commit=False)` inside `register_sale`'s existing transaction, before the single `session.commit()`. Proven by `tests/test_finance.py::test_sale_credits_till` (exactly one +T cash row) and `test_sale_rollback_writes_zero_cash` (rollback path writes zero) |
| 3 | Registering a return against that sale immediately decreases the balance by the same amount, restoring it to the pre-sale value | ✓ VERIFIED | `app/services/returns.py:165-179` computes `debit = qty * (origin.unit_price_cents or 0)` independently and stages `finance.record_cash_movement(category="return", amount_cents=-debit, ...)` in the same transaction as the return op (`record_operation(..., commit=False)` flip + one trailing `session.commit()`). Proven by `test_full_return_restores_balance` (balance returns to exact pre-sale value), `test_partial_return_debits_independently` (independent partial computation), and `test_return_is_atomic` (return op count == return cash row count) |
| 4 | The cash_movements ledger is append-only at the DB level (FIN supporting invariant, D-00a) | ✓ VERIFIED | Triggers `cash_movements_no_update`/`cash_movements_no_delete` exist in both `app/db.py:34-42` (live source, conftest installs on fixture engine) and `alembic/versions/0013_cash_movements.py:37-48` (frozen copy). Proven by `test_cash_movement_append_only_update_is_rejected` / `_delete_is_rejected` — both raise with "append-only" in the message |
| 5 | cash_movements has a single sanctioned write path with a live-SUM balance, no cache (D-00b) | ✓ VERIFIED | `app/services/finance.py` — `record_cash_movement` is the only function that constructs/inserts `CashMovement`; `compute_balance` is `SELECT COALESCE(SUM(amount_cents), 0)` with no WHERE, no cached column on the model. Grep confirms no `CashMovement(` construction anywhere outside `app/services/finance.py` and `tests/` |
| 6 | No route writes cash directly (D-00c) | ✓ VERIFIED | `grep -rn "record_cash_movement" app/routes/` returns only a docstring comment in `app/routes/finance.py:3`, not an import/call; both `finance.py` and `mobile_finance.py` import `compute_balance` only |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `CashMovement` class + `CASH_CATEGORIES` | ✓ VERIFIED | Lines 62-65 (`CASH_CATEGORIES`), 327-358 (`CashMovement`) — Integer `amount_cents`, String(36) UUID PK, `UniqueConstraint("device_id","seq")`, named FK `fk_cash_movements_sale_id_sales` |
| `app/db.py` | Append-only triggers in `APPEND_ONLY_TRIGGERS` | ✓ VERIFIED | Lines 22-43, tuple widened to `tuple[str, ...]`, two cash triggers present |
| `alembic/versions/0013_cash_movements.py` | Table + frozen trigger DDL, revises 0012 | ✓ VERIFIED | `down_revision = "0012"`; `uv run alembic heads` → single head `0013` |
| `app/services/finance.py` | `next_seq`, `record_cash_movement`, `compute_balance` | ✓ VERIFIED | All three defined and exported; category allow-list guard; live SUM |
| `app/services/sales.py` | sale credit hook wired into `register_sale` | ✓ VERIFIED | Line 271-277, before `session.commit()` |
| `app/services/returns.py` | return debit hook + atomic commit | ✓ VERIFIED | Lines 152-179, `commit=False` flip + independent debit computation + one trailing commit |
| `app/routes/finance.py` | `GET /finance` → `pages/finance.html` w/ `balance_cents` | ✓ VERIFIED | Read-only, `compute_balance` only |
| `app/routes/mobile_finance.py` | `GET /m/finance` → `mobile_pages/finance.html` | ✓ VERIFIED | Mirrors desktop route |
| `app/templates/pages/finance.html` | «Баланс кассы» + cents-formatted figure | ✓ VERIFIED | `<h1>Баланс кассы</h1>` + `{{ balance_cents \| cents }}`, balance-only, no movement list |
| `app/templates/mobile_pages/finance.html` | Same, mobile | ✓ VERIFIED | Same shape, extends `mobile_base.html` |
| `tests/test_finance.py` | Append-only + balance + contract + integration + page tests | ✓ VERIFIED | 14 tests, all passing (`uv run pytest tests/test_finance.py -q` → 14 passed) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/conftest.py` engine fixture | `app/db.py APPEND_ONLY_TRIGGERS` | trigger-install loop | ✓ WIRED | Cash triggers included in the constant conftest loops over |
| `CashMovement.sale_id` | `sales.id` | FK `fk_cash_movements_sale_id_sales` | ✓ WIRED | Confirmed in both model and migration |
| `finance.record_cash_movement` | `settings.device_id`/`settings.operator_name` | audit-field stamping | ✓ WIRED | `app/services/finance.py:59,62` |
| `finance.compute_balance` | `cash_movements` | `func.coalesce(func.sum(...))` | ✓ WIRED | `app/services/finance.py:76` |
| `sales.register_sale` | `finance.record_cash_movement` | staged `commit=False` credit before `session.commit()` | ✓ WIRED | `app/services/sales.py:271-280` |
| `returns.register_return` | `finance.record_cash_movement` | staged `commit=False` debit, same transaction | ✓ WIRED | `app/services/returns.py:165-179` |
| `app/routes/finance.py` | `finance.compute_balance` | `GET /finance` handler | ✓ WIRED | `app/routes/finance.py:18` |
| `app/templates/base.html` | `/finance` | desktop nav link | ✓ WIRED | Line 39 |
| `app/templates/mobile_pages/home.html` | `/m/finance` | mobile hub tile | ✓ WIRED | Line 14 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `pages/finance.html` | `balance_cents` | `app/routes/finance.py` → `compute_balance(session)` → live `SUM(amount_cents)` over `cash_movements` | Yes — real DB aggregate, not static/hardcoded | ✓ FLOWING |
| `mobile_pages/finance.html` | `balance_cents` | same `compute_balance` via `app/routes/mobile_finance.py` | Yes | ✓ FLOWING |
| `cash_movements` rows | `amount_cents` | `register_sale`/`register_return` compute real `total_cents`/`debit` from actual basket/return data, not stubbed | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Cash ledger tests all pass | `uv run pytest tests/test_finance.py -q` | 14 passed | ✓ PASS |
| Full suite has no regression | `uv run pytest -q` | 577 passed, 0 failed | ✓ PASS |
| Single Alembic head | `uv run alembic heads` | `0013 (head)` | ✓ PASS |
| No cash-write import in routes | `grep -rn "record_cash_movement" app/routes/` | Only a docstring mention in `finance.py:3`, no import/call | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FIN-01 | 15-01, 15-02, 15-03 | Касса автоматически пополняется на сумму каждой продажи | ✓ SATISFIED | `register_sale` credit hook + `test_sale_credits_till` |
| FIN-02 | 15-01, 15-02, 15-03 | Касса автоматически списывается при возврате товара симметрично | ✓ SATISFIED | `register_return` debit hook + `test_full_return_restores_balance`, `test_return_is_atomic` |
| FIN-06 | 15-04 | Отдельный раздел UI «Финансы» с текущим балансом кассы | ✓ SATISFIED | `/finance`, `/m/finance` routes + nav/tile + page tests |

No orphaned requirements — ROADMAP.md maps only FIN-01/02/06 to Phase 15, and all three appear in plan frontmatter `requirements:` fields and are addressed above.

Note: `.planning/REQUIREMENTS.md` still shows FIN-01/02/06 checkboxes as `[ ]` (unchecked) and the coverage table as "Pending" — this is a tracking-document staleness issue (updated at milestone close, not per-phase), not a code gap. Flagged for awareness, not blocking.

### Anti-Patterns Found

None. Scanned all phase-modified files (`app/models.py`, `app/db.py`, `app/services/finance.py`, `app/services/sales.py`, `app/services/returns.py`, `app/routes/finance.py`, `app/routes/mobile_finance.py`, `alembic/versions/0013_cash_movements.py`, both `finance.html` templates) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` — zero matches.

Two pre-existing, unrelated issues were found and logged (not introduced by this phase, not blocking):
- `alembic upgrade head --sql` (offline mode) fails inside migration `0002` (pre-existing Phase 2 bug) — logged in `deferred-items.md`, doesn't affect the online path used by the app/tests.
- A test-order flake in `tests/test_mobile_sales.py` observed once during Plan 02's full-suite run, not reproduced in this verification's own full-suite run (577 passed, 0 failed) — logged in `deferred-items.md`.

### Human Verification Required

### 1. Real-browser click-through of the balance flow

**Test:** Open `/finance` and `/m/finance` in a browser. Register a real sale through the sale form (not a direct service call) and observe the balance. Register a return against that sale through the return form and observe the balance again.
**Expected:** «Баланс кассы» displays with no currency glyph (e.g. "125,00", not "125,00 ₽"); the balance visibly rises by the sale total immediately after the sale is submitted; the balance visibly falls back to the pre-sale value immediately after the return is submitted.
**Why human:** Plan `15-04-PLAN.md`'s own `<verification>` section explicitly names this an end-of-phase human-check (`human_verify_mode = end-of-phase`) for visual/UX confirmation through the actual HTML forms. Automated tests already prove the same claims at the service+route-render layer (`test_sale_credits_till`, `test_full_return_restores_balance`, `test_page_shows_balance`), so this is a final visual-polish/full-click-through sanity check, not evidence of a functional gap.

### Gaps Summary

No functional gaps found. All 3 ROADMAP.md success criteria and all 6 derived observable truths are verified against the actual codebase: the `cash_movements` table is append-only at the DB level (triggers in both `app/db.py` and migration `0013`), `app/services/finance.py` is the single write path with a live-SUM balance, both `register_sale` and `register_return` stage their cash movements inside their existing transactions (proven atomic via integration tests, not code inspection alone), and the balance is observable through both `/finance` and `/m/finance` reachable from desktop nav and mobile hub. Full test suite (577 tests) and the phase's own 14 finance tests are green with no regressions. The only open item is a browser-based visual sanity check that the plan itself deferred to end-of-phase human verification — this does not indicate any missing functionality.

---

*Verified: 2026-07-14T21:00:00Z*
*Verifier: Claude (gsd-verifier)*
