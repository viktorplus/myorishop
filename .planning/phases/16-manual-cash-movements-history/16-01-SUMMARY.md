---
phase: 16-manual-cash-movements-history
plan: 01
subsystem: cash-ledger
tags: [constants, jinja-globals, tdd, finance]
requires: []
provides:
  - "CASH_CATEGORIES extended with 7 manual keys (5 withdrawal + 2 deposit) with RU labels"
  - "CASH_BUCKETS category-set grouping map for the 4 coarse history buckets"
  - "CASH_BUCKET_LABELS bucket->RU label map"
  - "CASH_CATEGORIES + CASH_BUCKET_LABELS registered as Jinja globals"
affects:
  - "app/services/finance.record_manual_movement (Plan 02) allow-list gate"
  - "app/services/finance.cash_history_view (Plan 02) bucket filter"
  - "manual-entry forms + cash-history templates (later plans)"
tech-stack:
  added: []
  patterns:
    - "latin-key -> RU-label dict (mirrors OPERATION_TYPE_LABELS / WRITEOFF_REASONS)"
    - "coarse-bucket -> category-set map for in_() filtering"
    - "model constants exposed as templates.env.globals"
key-files:
  created: []
  modified:
    - app/models.py
    - app/routes/__init__.py
    - tests/test_finance.py
decisions:
  - "Honored D-01: no type column, no migration — direction in amount_cents sign, kind in category prefix"
  - "CASH_BUCKETS kept server-side only (not a Jinja global) — it is a filter map, never rendered"
metrics:
  duration: "~5m"
  completed: "2026-07-15"
  tasks: 2
  files: 3
---

# Phase 16 Plan 01: Cash Category & Bucket Vocabulary Summary

Extended the cash-ledger category vocabulary with the 7 Phase 16 manual keys, added the `CASH_BUCKETS` / `CASH_BUCKET_LABELS` grouping maps, and registered `CASH_CATEGORIES` + `CASH_BUCKET_LABELS` as Jinja globals — the source-of-truth constants the manual write path (Plan 02) and history view depend on.

## What Was Built

- **Task 1 (TDD):** Extended `CASH_CATEGORIES` in `app/models.py` with the 5 withdrawal keys (`withdrawal_supplier` «Оплата поставщику», `withdrawal_salary` «Зарплата», `withdrawal_rent` «Аренда», `withdrawal_utilities` «Коммунальные», `withdrawal_other` «Прочее») and 2 deposit keys (`deposit_opening` «Начальный остаток», `deposit_correction` «Корректировка»). Added `CASH_BUCKETS: dict[str, tuple[str, ...]]` (4 coarse buckets → category-key tuples) and `CASH_BUCKET_LABELS` (bucket → RU). Existing `sale`/`return` keys unchanged. All keys ≤ 20 chars (`withdrawal_utilities` is exactly 20, fits `CashMovement.category` String(20)). No `type` column, no migration (D-01).
- **Task 2:** Registered `CASH_CATEGORIES` and `CASH_BUCKET_LABELS` as `templates.env.globals` in `app/routes/__init__.py`, alongside the existing `WRITEOFF_REASONS` / `OPERATION_TYPE_LABELS` globals (Pitfall 2 fix). `CASH_BUCKETS` deliberately NOT registered — it is a server-side filter map only.

## TDD Flow (Task 1)

- **RED:** Added `test_categories_manual_keys_present` and `test_buckets_cover_categories` to `tests/test_finance.py`; import of the not-yet-existing `CASH_BUCKETS`/`CASH_BUCKET_LABELS` failed collection with `ImportError` (commit `706e166`).
- **GREEN:** Implemented the constants in `app/models.py`; both contract tests pass, all 16 finance tests green (commit `3ead1a6`).
- **REFACTOR:** None needed.

## Verification

- `uv run pytest tests/test_finance.py -k "categories or buckets" -x` — 2 passed.
- `uv run pytest tests/test_finance.py` — 16 passed.
- `uv run pytest` (full suite) — 579 passed.
- `uv run ruff check app/models.py app/routes/__init__.py tests/test_finance.py` — clean.
- `python -c "from app.routes import templates; assert 'CASH_CATEGORIES' in templates.env.globals and 'CASH_BUCKET_LABELS' in templates.env.globals"` — exits 0.
- All plan acceptance-criteria `python -c` commands pass (manual keys present, all keys ≤ 20 chars, no orphan bucket categories, `withdrawal_other` label resolves in globals).

## Deviations from Plan

None - plan executed exactly as written.

## Commits

- `706e166` — test(16-01): add failing contract tests (RED)
- `3ead1a6` — feat(16-01): extend CASH_CATEGORIES + add bucket maps (GREEN)
- `26d4b99` — feat(16-01): register CASH_CATEGORIES + CASH_BUCKET_LABELS as Jinja globals

## Notes for Downstream Plans

- `record_manual_movement` (Plan 02) can now validate categories against the extended `CASH_CATEGORIES` allow-list — the 7 manual keys will pass `record_cash_movement`'s guard.
- `cash_history_view` (Plan 02) must use `CASH_BUCKETS.get(bucket)` → `category.in_(cats)` (unknown bucket → `None` → no filter) — do NOT filter by exact category (Pitfall 3).
- Templates can reference `CASH_CATEGORIES` and `CASH_BUCKET_LABELS` directly (globals); `CASH_BUCKETS` is NOT available in templates by design.

## Self-Check: PASSED

- All modified files present on disk.
- All 3 task commits (`706e166`, `3ead1a6`, `26d4b99`) present in git history.
