---
phase: 27-shared-idempotent-merge-core
plan: 01
subsystem: api
tags: [ndjson, sync, merge, dataclasses, json, exchange-format]

# Dependency graph
requires:
  - phase: 26-postgresql-portability-append-only-parity
    provides: dual-dialect append-only parity + single settings.database_url engine surface (the merge engine inherits it)
  - phase: 25-authentication-roles-user-attribution
    provides: author_id/created_by attribution + per-install device_id carried verbatim on the wire
provides:
  - "app/services/merge.py — the pure engine module (format half): FORMAT_VERSION, RECORD_KINDS, KIND_TO_MODEL, KIND_TO_FIELDS"
  - "Value-object dataclasses ExchangeRecord, ExchangeBatch, Conflict, MergeReport (Conflict/MergeReport populated in Plans 02-03)"
  - "parse_exchange(lines) -> ExchangeBatch and serialize_exchange(records, *, schema_version, source_device_id, generated_at) -> Iterator[str] — verbatim round-trip NDJSON codec"
  - "tests/test_merge.py — NDJSON batch factory (build_ndjson / record_line / record_from_orm) + round-trip + rejection suite"
affects: [28-central-server-sync-api, 29-online-client-sync, 30-offline-self-uploading-file, 27-02, 27-03]

# Tech tracking
tech-stack:
  added: []  # stdlib json + dataclasses only — no new packages
  patterns:
    - "NDJSON wire format: one header envelope line first, per-line kind discriminator, one json.dumps/loads per line (streamable)"
    - "Schema-derived allowed-field / money-field sets via model.__mapper__.columns (auto-tracks the ORM schema, no hand-maintained lists)"
    - "Frozen dataclass value objects for pure-function boundaries (ExchangeRecord)"

key-files:
  created:
    - app/services/merge.py
    - tests/test_merge.py
  modified: []

key-decisions:
  - "Money-field float guard is schema-driven: derive *_cents columns from KIND_TO_FIELDS rather than a hardcoded list, so the type-confusion gate auto-tracks the schema"
  - "parse_exchange treats source_device_id as None and schema_version as '' when the header omits them (dataclass has no defaults for those fields)"
  - "serialize_exchange emits a counts map in the header (records-per-kind) for cheap transport-side inspection without parsing the body"

patterns-established:
  - "Pattern: NDJSON codec — header-first, per-line kind, verbatim carriage of origin id/device_id/seq/author_id/created_by; synced_at forced to None on parse"
  - "Pattern: strict input validation before any DB touch — malformed line, bad format_version, unknown/duplicate kind, missing header, missing ledger provenance, float money all raise ValueError (ASVS V5)"

requirements-completed: [SYNC-04]

# Metrics
duration: ~14min
completed: 2026-07-19
---

# Phase 27 Plan 01: Shared Exchange Format (NDJSON codec) Summary

**The single SYNC-04 wire contract: a pure NDJSON parse/serialize codec (header-first, per-line `kind`) with verbatim round-trip carriage and strict pre-DB validation, plus the four engine dataclasses and the shared NDJSON test factory Plans 02-04 build on.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-07-19T10:36:00Z
- **Completed:** 2026-07-19T10:50:00Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- Defined the ONE exchange format: `FORMAT_VERSION`, the nine-kind `RECORD_KINDS`, the `kind`→ORM `KIND_TO_MODEL` map, and the schema-derived `KIND_TO_FIELDS`.
- Declared the four value-object dataclasses (`ExchangeRecord`, `ExchangeBatch`, `Conflict`, `MergeReport`) so the contract Plans 02-03 populate is stable now.
- Implemented `parse_exchange`/`serialize_exchange` as a pure codec with proven verbatim round-trip identity (origin `id/device_id/seq/author_id/created_by` survive field-for-field).
- Hardened parse against untrusted NDJSON: rejects malformed/non-object lines, unsupported `format_version`, unknown/duplicate `kind`, missing header, missing ledger provenance, and float money — all before any DB touch (ASVS V5). `synced_at` is forced to `None` (server-owned).
- Shipped the reusable NDJSON factory (`build_ndjson` / `record_line` / `record_from_orm`) the whole later merge suite depends on.

## Task Commits

Each task was committed atomically:

1. **Task 1: merge.py contracts + NDJSON test factory (interface-first)** - `03141a8` (feat)
2. **Task 2: parse_exchange + serialize_exchange — verbatim round-trip + strict validation** - `a0d0931` (feat)

**Plan metadata:** (this docs commit)

## Files Created/Modified
- `app/services/merge.py` - Pure engine module: format constants, `kind`→model map, four dataclasses, and the `parse_exchange`/`serialize_exchange` NDJSON codec. No HTTP, no file I/O, no FastAPI, no `sqlalchemy.dialects`.
- `tests/test_merge.py` - NDJSON batch factory + import smoke test (Task 1) and the round-trip / rejection / synced-at / blank-line format suite (Task 2). 12 tests, all green.

## Decisions Made
- **Schema-driven money guard:** the float-cents rejection derives `*_cents` fields from `KIND_TO_FIELDS` (built from `model.__mapper__.columns`) instead of a hardcoded list, so the guard auto-tracks the schema. Matches the plan's "no hand-maintained column list can drift" instruction.
- **Header defaults on parse:** absent `schema_version` → `""`, absent `source_device_id` → `None` (the `ExchangeBatch` dataclass declares no defaults for these per RESEARCH; parse supplies them).
- **`counts` in the header envelope:** `serialize_exchange` emits a records-per-kind `counts` map (matching the RESEARCH NDJSON example) for transport-side inspection.

## Deviations from Plan

None - plan executed exactly as written. (The plan's Task-1 instruction to keep parse/serialize as stubs meant `json` was temporarily unimported in Task 1 to keep ruff clean; it was re-added in Task 2 when the bodies landed. This is the plan's own interface-first sequencing, not a deviation.)

## Issues Encountered
None. Ruff flagged the expected transient unused-import (`json` in the Task-1 stub state, `pytest` before the Task-2 tests existed); both were resolved by the plan's own task sequencing.

## User Setup Required
None - no external service configuration required (this phase installs no packages; stdlib `json`/`dataclasses` only).

## Next Phase Readiness
- `merge.py` is a pure, importable module ready for Plan 02's `apply_merge` (reference upsert + idempotent ledger append + `recompute_derived`).
- `Conflict`/`MergeReport` are declared and constructible, so Plan 03's reference-conflict/collision logic has a stable target.
- The NDJSON factory (`build_ndjson`/`record_line`/`record_from_orm`) is in place for the Plan 02-04 dimension tests.
- No Alembic migration was created (RESEARCH A8: the engine runs on the existing 0001→0017 schema) — unchanged and correct.

## Self-Check: PASSED

- FOUND: app/services/merge.py
- FOUND: tests/test_merge.py
- FOUND: .planning/phases/27-shared-idempotent-merge-core/27-01-SUMMARY.md
- FOUND commit: 03141a8 (Task 1)
- FOUND commit: a0d0931 (Task 2)

---
*Phase: 27-shared-idempotent-merge-core*
*Completed: 2026-07-19*
