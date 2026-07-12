---
phase: 09-batch-tracking-ledger-integration
plan: 05
subsystem: ledger
tags: [sqlalchemy, fastapi, jinja2, htmx, batch-tracking, returns, history, ledger, tdd]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration (Plan 01)
    provides: "Batch model, legacy_batch helper, record_operation batch_id dual projection + ownership guard, ru_date filter, is_legacy marker"
  - phase: 09-batch-tracking-ledger-integration (Plan 02)
    provides: "receipt batch birth path — every receipt op supplies a batch_id"
  - phase: 09-batch-tracking-ledger-integration (Plan 03)
    provides: "sale batch picker — every sale op supplies a batch_id"
  - phase: 09-batch-tracking-ledger-integration (Plan 04)
    provides: "write-off + correction batch pick — those ops supply a batch_id"
provides:
  - "register_return batch inheritance (D-08): return restores stock to origin.batch_id, or the product's legacy batch, LAZILY creating it (is_legacy=1, frozen D-14 fields) when absent — the deliberate third batch birth path (Open Q1)"
  - "resolve_return_batch read helper: the display-side (no-create) batch resolution for the read-only return form line"
  - "history_view LEFT OUTER JOIN Batch: each /history row dict carries a \"batch\" key (None for a pre-Phase-9 op) — read-time attribution, the ledger is never rewritten (D-15)"
  - "record_operation MANDATORY D-12 guard: STOCK_AFFECTING_TYPES require a batch_id (ValueError otherwise); audit types reject a batch_id — the phase's single-write-path enforcement backstop (LOT-05)"
affects: [returns, history, ledger, all-stock-writers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Third batch birth path: lazy-create the legacy batch inside register_return's transaction (frozen D-14 contract, quantity 0), then increment via the single write path"
    - "Read-time legacy attribution: NULL batch_id resolved to a label via LEFT OUTER JOIN at render time, never a ledger UPDATE (D-15)"
    - "Mandatory write-path invariant: STOCK_AFFECTING_TYPES frozenset gates batch requirement in the single record_operation choke point"

key-files:
  created: []
  modified:
    - "app/services/returns.py"
    - "app/routes/returns.py"
    - "app/templates/partials/return_form.html"
    - "app/services/operations.py"
    - "app/templates/partials/history_rows.html"
    - "app/services/ledger.py"
    - "tests/test_returns.py"
    - "tests/test_history.py"
    - "tests/test_ledger.py"
    - "tests/test_batches.py"
    - "tests/test_reports.py"
    - "tests/test_backup.py"
    - "tests/test_export.py"
    - "tests/test_receipts.py"

key-decisions:
  - "Legacy return fallback lazily CREATES the legacy batch (not reject) — the only way D-08 works for every pre-Phase-9 sale; frozen D-14 fields re-declared in returns.py, never imported from the migration"
  - "The return form is read-only for the batch (no picker) — the batch is server-resolved from the validated origin op, never client-supplied (D-08 / T-09-17)"
  - "/history batch info is a muted SECOND line inside the «Товар» cell, not a 9th column (D-15 / RESEARCH Open Q3) — table stays 8 columns"
  - "app/routes/history.py needed NO change — the existing rows context passthrough already carries the new \"batch\" row key to the template"
  - "test_batches::test_record_operation_without_batch_still_works repurposed to assert the flipped mandatory guard (its Plan-01 optional-batch premise is superseded by D-12)"

requirements-completed: [LOT-05]

# Metrics
duration: ~40 min
completed: 2026-07-12
---

# Phase 9 Plan 05: Return Batch Inheritance, /history Attribution & the Mandatory D-12 Guard Summary

**Returns now inherit the origin sale line's batch (lazily creating a legacy batch for pre-Phase-9 sales), /history renders read-time batch attribution (legacy label for NULL batch_id) without touching the append-only ledger, and record_operation enforces the mandatory D-12 batch guard — closing the phase with the full 326-test suite green.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-07-12
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 14 (0 created, 14 modified)
- **Test count:** 309 → 326 (+17)

## Accomplishments
- **Return batch inheritance (D-08, Task 1):** `register_return` resolves the target batch from `origin.batch_id`; for a pre-Phase-9 (NULL batch_id) origin it targets the product's legacy batch, LAZILY creating one (`is_legacy=1`, comment «Остаток до внедрения партий», frozen D-14 fields) inside the return transaction when none exists — the deliberate third batch birth path (Open Q1). The return op now carries `batch_id` through the single write path (dual projection). The return form shows the target batch as a read-only muted line with NO picker: batched → «Возврат в партию: {срок|без срока}{ — comment}»; legacy/NULL → «Возврат в партию: Остаток до внедрения партий».
- **/history batch attribution (D-15, Task 2):** `history_view` LEFT OUTER JOINs `Batch` and each row dict gains a `"batch"` key. `history_rows.html` renders a muted second line inside the existing «Товар» cell — «Партия: {срок|без срока}{ — comment}» for a batched op, «До внедрения партий» for a NULL-batch stock op, and nothing for audit types — entirely at read time; the append-only ledger is never rewritten. The table stays 8 columns.
- **Mandatory D-12 guard (Task 3):** added `STOCK_AFFECTING_TYPES = frozenset({receipt, sale, writeoff, return, correction})`; `record_operation` now raises `ValueError` for a stock-affecting op with no `batch_id`, and raises for an audit op given a `batch_id`. This is the LOT-05 write-path enforcement backstop for all current and future callers. The full suite is green because Plans 02–04 and Task 1 already thread `batch_id` through every stock writer.

## Task Commits

Each task was executed TDD (RED test commit → GREEN implementation commit):

1. **Task 1: Return batch inheritance + legacy lazy-create + read-only origin line**
   - `439ed3a` (test) → `ca3b44e` (feat)
2. **Task 2: /history batch attribution (read-time, D-15)**
   - `70e16b8` (test) → `f403a41` (feat)
3. **Task 3: Flip the D-12 mandatory batch guard + full-suite sweep**
   - `a991f29` (test) → `642a237` (feat)

## Files Modified
- `app/services/returns.py` — `resolve_return_batch` (display) + `_resolve_or_create_return_batch_id` (write, lazy-create) helpers; frozen `DEFAULT_WAREHOUSE_ID`/`LEGACY_BATCH_COMMENT` constants; `batch_id` threaded into the `record_operation` call; docstring notes the third birth path.
- `app/routes/returns.py` — `origin_batch` added to the form contexts via `resolve_return_batch`.
- `app/templates/partials/return_form.html` — read-only muted origin-batch line (no picker, D-08).
- `app/services/operations.py` — `history_view` LEFT OUTER JOIN `Batch` + `"batch"` row key.
- `app/templates/partials/history_rows.html` — muted batch second line in the «Товар» cell (legacy label for NULL batch_id).
- `app/services/ledger.py` — `STOCK_AFFECTING_TYPES` + the mandatory/audit D-12 guard branches in `record_operation`.
- `tests/test_returns.py`, `tests/test_history.py`, `tests/test_ledger.py` — new TDD tests (inheritance, lazy-create, read-only line, read-time attribution, mandatory guard).
- `tests/test_batches.py`, `tests/test_reports.py`, `tests/test_backup.py`, `tests/test_export.py`, `tests/test_receipts.py` — signature-change sweep: batch-wired straggler seeds (or repurposed the obsolete optional-batch test) so every stock-affecting caller supplies a batch after the flip.

## Decisions Made
- **Lazy-create over reject for the legacy-return fallback** (Open Q1) — a product sold out at migration (ledger stock ≤ 0) has no seeded legacy batch; the return lazily creates one with the exact frozen D-14 contract, re-declared in `returns.py` (never imported from migration 0008), so D-08 holds for every legacy sale while the single-write-path invariant is preserved.
- **`app/routes/history.py` unchanged** — the plan's `files_modified` listed it, but the existing rows context passthrough already forwards the new `"batch"` row key to the template; touching the route would have been churn with no behavior change.
- **Repurposed `test_record_operation_without_batch_still_works`** (test_batches) into `test_record_operation_batch_guard_is_mandatory` — its Plan-01 "batch stays optional" premise is exactly what Plan 05 flips; the test now asserts a batch-less stock op raises while an audit op still writes batch-less.
- **Pre-Phase-9 legacy ops are simulated via direct `Operation` inserts** in tests (bypassing the guarded write path), mirroring the real legacy ledger shape that the return-inheritance and /history-attribution paths must handle.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Signature-change sweep beyond the plan's listed files**
- **Found during:** Task 3 (full-suite run after the D-12 flip)
- **Issue:** Flipping the guard turned 21 tests red across `test_batches`, `test_reports`, `test_backup`, `test_export`, `test_receipts` — seed helpers that staged stock-affecting ops without a batch. The plan named `test_ledger`/`test_smoke` explicitly but the real blast radius (RESEARCH Pitfall 1 / 09-VALIDATION Wave 0) is wider.
- **Fix:** Added a local resolve-or-create `_ensure_batch` helper (or an inline batch seed) in each straggler file and threaded `batch_id` into every stock-affecting `record_operation` seed; converted two `test_batches` legacy tests to a direct-insert / repurposed-assert shape.
- **Files modified:** tests/test_batches.py, tests/test_reports.py, tests/test_backup.py, tests/test_export.py, tests/test_receipts.py
- **Verification:** `uv run pytest -q` → 326 passed.
- **Committed in:** `642a237` (Task 3 GREEN)

---

**Total deviations:** 1 auto-fixed (blocking signature sweep, anticipated by RESEARCH Pitfall 1).
**Impact on plan:** Required to keep the suite green after the mandatory-guard flip; production behavior matches the D-08/D-12/D-15 contracts exactly. No scope creep.

## Deferred Issues
Pre-existing lint debt only, unrelated to this plan's changes: `tests/test_export.py:124` `E501` (a test docstring, explicitly deferred by Plan 01). I added one `batch_id=` line to that test function but did not author the over-length docstring; per the scope boundary I left it. All production code (`app/`) passes `ruff check` clean; every new test I authored is lint-clean.

## Known Stubs
None — every artifact is wired and exercised by tests. `Batch.expiry`/`price_cents`/`location`/`comment` remain intentionally nullable (populated by the receipt flow, Plan 02); the return and /history surfaces read whatever those fields hold and fall back to «без срока»/legacy label correctly.

## Threat Flags
None — no new network endpoints or trust boundaries introduced. The plan's registered mitigations are all implemented: T-09-16 (mandatory D-12 guard in `record_operation`), T-09-17 (return batch server-resolved, never client-supplied), T-09-18 (legacy /history label resolved at read time via LEFT OUTER JOIN, ledger never rewritten), T-09-19 (Jinja autoescape on batch comment/expiry in both the return form and /history — no `|safe`).

## Issues Encountered
None beyond the deviation above. The two pre-existing warnings (`test_backup` httpx-TestClient deprecation, `test_returns::test_web_return_survives_unexpected_error` SAWarning) are unrelated to this plan; the full suite is green (326 passed).

## Next Phase Readiness
- ROADMAP criterion 3 complete: the return path is batch-attributed via inheritance (no re-ask) — LOT-05 fully covered across sale, write-off, correction, and return.
- ROADMAP criterion 5 (display side): legacy operations show as belonging to a default legacy batch on /history and the return form, with no ledger rewrite (D-15).
- The mandatory D-12 guard is enforced at the single write path — the phase's write-path invariant is closed. Phase 09 is ready for `/gsd-verify-work`.
- Requirement LOT-05 marking and STATE.md/ROADMAP.md updates are left to the orchestrator's post-merge central pass (worktree mode).

## Self-Check: PASSED
- All 14 modified key files present on disk (verified with `[ -f ]` during execution; edits succeeded).
- All 6 task commits present in `git log ad64011..HEAD` (3 RED test + 3 GREEN feat); TDD gate sequence (test → feat) intact per task.
- `uv run pytest -q` → 326 passed. `ruff check app/` clean. Repo-wide `ruff check .` red only on the one pre-existing `test_export.py:124` E501 (Plan-01 deferred debt).

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
