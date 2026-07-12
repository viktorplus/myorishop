---
phase: 09-batch-tracking-ledger-integration
plan: 09
subsystem: data
tags: [alembic, sqlalchemy, sqlite, receipts, batches, jinja2, gap-closure]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration
    provides: batches table + Batch model (0008), resolve-or-create receipt chooser
  - phase: 09-batch-tracking-ledger-integration
    provides: fieldset/legend chooser restructure + code_entered flag (09-08)
provides:
  - Nullable batches.name column (migration 0009, native add-column)
  - Auto-generated «{product name} — {dd.mm.yyyy}» batch label at receipt time
  - Chooser top-up label surfaces batch.name (fallback for nameless legacy batches)
affects: [09-verify-work, receipts-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Native op.add_column on a trigger-free table (batches) — never an Alembic batch/move-and-copy rebuild, which would drop the operations append-only triggers"
    - "Stored (snapshotted) auto-generated label over a read-time derived one, so the name survives later product renames — consistent with the append-only/snapshot philosophy"

key-files:
  created:
    - alembic/versions/0009_batch_name.py
  modified:
    - app/models.py
    - app/services/receipts.py
    - app/templates/partials/receipt_batch_chooser.html
    - tests/test_batches.py

key-decisions:
  - "Stored nullable column chosen over a read-time derived label: the name is snapshotted at batch creation so it survives later product renames (project snapshot/append-only philosophy). Legacy/pre-0009 batches keep NULL and fall back to the expiry/price description."
  - "Date derived from utcnow_iso()[:10] (UTC) rather than settings.display_tz. Single local operator, label only; the test asserts the dd.mm.yyyy PATTERN, not a fixed value, so UTC vs local tz is immaterial for correctness and keeps the write path dependency-light."

patterns-established:
  - "Pattern: auto-generated snapshotted label «{entity} — {date}» set server-side at creation, no manual operator input field"

requirements-completed: [LOT-01, LOT-04]

# Metrics
duration: ~20min
completed: 2026-07-12
---

# Phase 9 Plan 09: Batch auto-name (schema + write path + chooser) Summary

**Every new batch now gets an auto-generated, snapshotted name «{product name} — {dd.mm.yyyy}» via a nullable batches.name column (native migration 0009), surfaced in the chooser top-up label — closing UAT test 1 symptom 3.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files created:** 1
- **Files modified:** 4

## Accomplishments
- Added a nullable `batches.name` column via migration 0009 using a NATIVE `op.add_column` (SQLite supports ADD COLUMN natively; `batches` has no triggers). No move-and-copy rebuild, so the append-only `operations_no_update`/`operations_no_delete` ledger triggers are untouched. No data backfill — only NEW batches get a name.
- `register_receipt` now auto-generates the batch name «{product.name} — {dd.mm.yyyy}» when creating a new batch, using the existing `format_ru_date`/`utcnow_iso` core helpers. The top-up path leaves the chosen batch's stored name untouched.
- The chooser top-up radio label prepends `{{ batch.name }} · ` when present (Jinja autoescape, never `|safe` — the name embeds the untrusted-at-rest product name); nameless/legacy batches keep the exact prior expiry/price/qty description.
- Four new tests cover the model column, the migration 0009 add-column/downgrade replay (asserting the two append-only triggers survive), the auto-name write path (new + top-up), and the web chooser label.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the batches.name column (migration 0009 + model)** - `abfe113` (feat)
2. **Task 2: Auto-generate the batch name and surface it in the chooser** - `525fb62` (feat)
3. **Task 3: Tests for the column, migration, auto-name, and chooser label** - `f588ce9` (test)

## Files Created/Modified
- `alembic/versions/0009_batch_name.py` (created) - native `op.add_column("batches", sa.Column("name", sa.String(200), nullable=True))`; downgrade drops it. No app-module imports (WR-06); docstring restates the frozen "never convert to an Alembic batch rebuild" caveat.
- `app/models.py` - `Batch.name: Mapped[str | None] = mapped_column(String(200))` next to `location`/`comment`; existing columns untouched.
- `app/services/receipts.py` - imports `format_ru_date`/`utcnow_iso` from `app.core`; sets `name=f"{product.name} — {format_ru_date(utcnow_iso()[:10])}"` on the new-batch `Batch(...)`. Top-up branch unchanged.
- `app/templates/partials/receipt_batch_chooser.html` - top-up label prepends `{% if batch.name %}{{ batch.name }} · {% endif %}` after "Пополнить партию: ". New-batch fields, fieldset/legend, and helper text from 09-08 untouched.
- `tests/test_batches.py` - added `re` + `register_receipt` imports and 4 tests (`test_batch_model_has_name_column`, `test_migration_0009_adds_batch_name_column`, `test_register_receipt_autogenerates_batch_name`, `test_web_chooser_shows_batch_name_in_topup_label`).

## Decisions Made
- **Stored column over derived label:** snapshots the name at creation so it survives product renames (append-only/snapshot philosophy). Legacy rows keep NULL and fall back to the expiry/price description.
- **UTC date source:** `utcnow_iso()[:10]` rather than `settings.display_tz`/`iso_to_local`. Single local operator, label only; the test asserts the date PATTERN not a fixed value, so tz choice is immaterial and keeps the write path dependency-light.

## Deviations from Plan

None - plan executed exactly as written.

## Verification
- `uv run alembic upgrade head` then `uv run alembic downgrade 0008` both succeed; `batches.name` present after upgrade, gone after downgrade.
- `uv run pytest tests/test_batches.py -q` → 20 passed (16 existing + 4 new). `uv run pytest tests/test_receipts.py -q` → 39 passed (chooser template change regression-clean).
- `uv run ruff check app/services/receipts.py app/models.py alembic/versions/0009_batch_name.py tests/test_batches.py` → clean.

## Threat Surface
- T-09-09-01 (Tampering, migration): mitigated — native add-column only; test 2 asserts the two `operations_no_%` triggers survive (no ledger rebuild).
- T-09-09-02 (Information disclosure, batch.name rendering): mitigated — Jinja autoescape kept on the chooser label, never `|safe`.
No new security surface introduced beyond the plan's threat model.

## Next Phase Readiness
- UAT test 1 symptom 3 (batch needs a name) addressed. Remaining browser UAT (live receipt → later top-up shows «{product} — {today}») is verified manually per the plan's verification note.
- No stubs introduced; all data paths wired.

## Self-Check: PASSED

All created/modified files present on disk; all three task commits (abfe113, 525fb62, f588ce9) verified in git history.

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
