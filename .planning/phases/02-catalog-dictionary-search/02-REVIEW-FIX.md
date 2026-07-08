---
phase: 02-catalog-dictionary-search
fixed_at: 2026-07-08T20:05:00Z
review_path: .planning/phases/02-catalog-dictionary-search/02-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-07-08T20:05:00Z
**Source review:** .planning/phases/02-catalog-dictionary-search/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (fix_scope=critical_warning: 1 Critical + 4 Warnings; 6 Info findings out of scope)
- Fixed: 5
- Skipped: 0

Verification: full suite `uv run pytest -q` — 74 passed (baseline 70 + 4 new regression tests); `uv run ruff check .` — all checks passed. All fixes were applied in an isolated worktree and fast-forwarded onto `main` (8ebbb41 → 440478e).

## Fixed Issues

### CR-01: Dictionary validation errors are never shown — htmx does not swap 422 responses

**Files modified:** `app/templates/base.html`, `tests/test_dictionary.py`
**Commit:** c47d83d
**Applied fix:** Added the `<meta name="htmx-config">` tag opting 422 into `responseHandling` swaps (reviewer's option 1 — the 422 status contract is kept). Added web test `test_web_add_invalid_returns_swappable_422_partial` covering: blank code → 422 + RU error in the rows partial, duplicate code on inline edit → 422 + RU duplicate message, and a config-level assertion that every full page carries `{"code":"422","swap":true}` in the htmx-config meta. This also closes the test gap flagged in IN-06.

### WR-01: Autofill race can overwrite the operator's in-progress name input

**Files modified:** `app/templates/pages/product_form.html`
**Commit:** 73724e1
**Applied fix:** Added a swap-time guard on the product form that discards the `#name-wrap` lookup fragment when the operator has meanwhile typed a non-empty name. The reviewer's suggested attribute `hx-on::htmx:before-swap` was adapted to `hx-on::before-swap` — in htmx 2 the `::` shorthand already expands to the `htmx:` prefix, so the suggested spelling would listen for a nonexistent `htmx:htmx:before-swap` event.
**Status note:** fixed: requires human verification — the guard is browser-side JS behavior that the TestClient suite cannot exercise; a quick manual check (type a code, immediately start typing a name before the 300 ms lookup returns, confirm the typed name survives) is recommended.

### WR-02: Dictionary UNIQUE(code) violation surfaces as an unhandled 500

**Files modified:** `app/services/dictionary.py`, `tests/test_dictionary.py`
**Commit:** 1309f1d
**Applied fix:** Wrapped `session.commit()` in both `add_entry` and `update_entry` with `try/except IntegrityError` → `session.rollback()` → `(None, {"code": DUPLICATE_ERROR})`, exactly per the review suggestion. Added regression test `test_add_entry_duplicate_race_returns_ru_error_not_500` that simulates the check-then-act race by monkeypatching `_validate` to skip the SELECT-based duplicate check, asserting the DB constraint is translated into the RU error and the session stays usable.

### WR-03: Multi-field product update is not atomic despite the docstring's atomicity claim

**Files modified:** `app/services/ledger.py`, `app/services/catalog.py`
**Commit:** 1873875
**Applied fix:** Added `commit: bool = True` parameter to `record_operation` (default preserves all existing call sites). `update_product` now stages every `price_change`/`product_edited` op with `commit=False` and issues a single `session.commit()` at the end, so the product mutation and the complete audit trail land in one transaction. `next_seq` remains correct: autoflush flushes pending ops before its `max(seq)` query (confirmed by the existing multi-op tests, e.g. `test_update_two_prices_emits_two_ops`).

### WR-04: Duplicate active product codes possible — uniqueness enforced only in Python

**Files modified:** `app/models.py`, `app/services/catalog.py`, `alembic/versions/0003_products_code_active_unique.py` (new), `tests/test_catalog.py`
**Commit:** 440478e
**Applied fix:**
- New migration 0003 creates the partial unique index `uq_products_code_active` on `products(code) WHERE deleted_at IS NULL` (portable: `sqlite_where` + `postgresql_where`), per the review's suggested code.
- The same index was added to `Product.__table_args__` in `app/models.py` so `Base.metadata.create_all` test fixtures enforce it too (test DBs are built from metadata, not Alembic).
- `create_product` and `update_product` catch `IntegrityError`, roll back, and return the existing RU duplicate-code error (message extracted into the `DUPLICATE_CODE_ERROR` constant).
- New tests: `test_duplicate_active_code_blocked_by_db_index` (direct insert of a duplicate active code raises `IntegrityError`) and `test_create_duplicate_code_race_returns_ru_error_not_500` (blinds the SELECT check to simulate the double-submit race; asserts RU error + clean rollback). The existing `test_soft_deleted_code_can_be_reused` confirms the partial WHERE clause still allows deleted-code reuse; `test_migration_0002_fresh_db_and_backfill` upgrades to `head` and thus exercises migration 0003 on a fresh DB with data.
- The review's optional "disable the submit button" suggestion was not applied — the DB constraint plus error translation fully closes the correctness gap; the plain-POST form UX tweak is cosmetic and out of minimal-fix scope.

## Skipped Issues

None — all in-scope findings were fixed.

Out of scope (fix_scope=critical_warning): IN-01..IN-06 were not addressed, except that IN-06's missing web test for the dictionary validation-error path was effectively added as part of the CR-01 fix.

---

_Fixed: 2026-07-08T20:05:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
