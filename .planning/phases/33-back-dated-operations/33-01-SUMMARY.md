---
phase: 33-back-dated-operations
plan: 01
subsystem: sync
tags: [fastapi, sqlalchemy, alembic, ndjson, schema-version, http-409, pytest]

# Dependency graph
requires:
  - phase: 27-merge-engine
    provides: "parse_exchange / apply_merge and the ExchangeBatch.schema_version header field the gate reads"
  - phase: 28-sync-server
    provides: "POST /api/sync/push, require_device, the four RU error constants, current_schema_version"
  - phase: 29-sync-client
    provides: "run_sync_once (stamps synced_at only after raise_for_status) and sync_state.last_sync_at"
provides:
  - "app.services.sync.push_schema_ok — asymmetric client<=server schema predicate with a two-sided empty-string escape hatch"
  - "HTTP 409 schema gate on POST /api/sync/push, refusing only a client AHEAD of the receiver"
  - "SCHEMA_AHEAD_ERROR — the fifth RU error constant on the sync router"
  - "tests/test_sync_schema_gate.py — 7 tests carrying VA-1 and VA-2"
affects: [33-02-backoff, 33-03-migration-tripwires, 33-04-migration-0027, sync, rollout-runbook]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Push-side schema gate: predicate in the service module, HTTP status + RU copy in the route"
    - "Asymmetric (ordered) schema comparison instead of exact match, so a behind client is never cut off"
    - "Explicit schema-version pinning in tests, because create_all fixtures report an empty revision on both sides"

key-files:
  created:
    - tests/test_sync_schema_gate.py
  modified:
    - app/services/sync.py
    - app/routes/sync.py
    - app/__init__.py

key-decisions:
  - "33-01 (D-01): the push schema comparison is ASYMMETRIC (client <= server), not exact-match — only a client AHEAD of the receiver is refused, because that is the single direction in which merge._ledger_row loses a field behind a 200; a BEHIND client merges on purpose so the fleet is never cut off (clients check for updates once at startup)."
  - "33-01 (D-02/AP-5): push_schema_ok is a NEW sibling of current_schema_version in app/services/sync.py — app/services/offline.py::schema_version_ok is neither reused, imported nor modified (byte-unchanged; its result page is locked by 30-UI-SPEC)."
  - "33-01 (D-03): the empty-string escape hatch is on BOTH sides, unlike the offline predicate's server-only hatch — every test fixture builds its schema with Base.metadata.create_all, so current_schema_version returns \"\" on the client half too; a one-sided hatch would redden the shipped sync suite wholesale."
  - "33-01 (D-04): push_schema_ok compares LEXICOGRAPHICALLY, which is only sound while every Alembic revision id is fixed-width numeric; the docstring names tests/test_migrations.py::test_revision_ids_are_fixed_width (plan 33-03) as the tripwire that must hold."
  - "33-01 (D-05): the gate reads the already-parsed batch.schema_version between parse_exchange and the owned transaction — two lines instead of the eight the bundle-upload path needs. Accepted trade-off, stated in the code: a future NEW-KIND schema bump makes parse_exchange raise 400 first, a worse message but not a loss, since any non-2xx returns before the client's synced_at stamp."
  - "33-01 (D-07): SYNC-11 is satisfied by a TEST, not by code — synced_at is stamped only after raise_for_status() and last_sync_at advances only for ok/partial, so a 409 already leaves the client fully re-pushable; test_refused_push_leaves_rows_unsynced pins that against regression."

patterns-established:
  - "Schema gate placement: after structural parsing, before the owned write transaction — no DB touch on a refusal"
  - "409 detail bodies carry only Alembic revision ids, never request bytes or exception text (T-33-02 / T-28-07)"
  - "Cross-boundary refusal tests pin the two halves separately: app.routes.sync.current_schema_version for the receiver, app.services.sync_client.current_schema_version for the driver"

requirements-completed: [SYNC-10, SYNC-11]

# Metrics
duration: 32min
completed: 2026-09-04
---

# Phase 33 Plan 01: Sync Schema Gate Summary

**`POST /api/sync/push` now refuses a client whose Alembic revision is AHEAD of the receiver with HTTP 409 and a Russian message naming both revisions, closing the silent-data-loss window that migration 0027 would otherwise open across a self-updating fleet — while a BEHIND client still merges.**

## Performance

- **Duration:** ~32 min
- **Started:** 2026-09-04T09:05Z
- **Completed:** 2026-09-04T09:37Z
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- **The loss window is closed for the ahead direction.** `merge._ledger_row` projects an incoming
  batch through the RECEIVER's columns, so a self-updated client pushing `business_date` to an
  un-migrated s1 would have had the key dropped, received 200, and stamped `synced_at` — permanent
  and unrecoverable. An ahead client now gets 409 before any DB touch.
- **A behind client is still accepted, deliberately.** The comparison is ordered, not exact
  (D-01), so the fleet is never cut off during the rollout window; those rows land with the new
  columns NULL and bucket via the read-time COALESCE, which is what makes DATE-08 a live property.
- **SYNC-11 is pinned rather than coded.** `synced_at` is stamped only after `raise_for_status()`
  and `last_sync_at` advances only for `ok`/`partial`, so a refusal already loses nothing; the new
  VA-2 test drives a real client→server push over the ASGI bridge and asserts every client row is
  still `synced_at IS NULL`, zero rows reached the server session, and `last_sync_at` is unchanged.
- **`app/services/offline.py` is byte-unchanged** (`git diff --stat` empty across all three
  commits) — the 30-UI-SPEC-locked bundle predicate was not reused, imported or touched.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED scaffold — tests/test_sync_schema_gate.py** — `7c529e4` (test)
2. **Task 2: push_schema_ok in app/services/sync.py** — `13695a3` (feat)
3. **Task 3: 409 gate + SCHEMA_AHEAD_ERROR in app/routes/sync.py** — `3c88252` (feat)

## Files Created/Modified

- `tests/test_sync_schema_gate.py` *(created)* — 7 tests: four `push_schema_ok` unit cases
  (behind / equal / ahead / two-sided hatch), VA-1 as a pair of real device-token pushes
  (`test_ahead_client_push_returns_409`, `test_behind_client_push_merges`), and VA-2 as a full
  driver round trip (`test_refused_push_leaves_rows_unsynced`). Not-yet-existing symbols are
  imported INSIDE the test bodies (Wave-0 idiom) so collection stayed green while execution was red.
- `app/services/sync.py` — `push_schema_ok(client_schema, server_schema)` added directly beneath
  `current_schema_version`; docstring cites D-01/D-02/D-03, states the fixed-width-revision
  precondition and names `test_revision_ids_are_fixed_width` as its tripwire.
- `app/routes/sync.py` — `SCHEMA_AHEAD_ERROR` declared beside the four existing RU constants under
  the same section comment; step (4b) gate between `parse_exchange` and `with session.begin()`,
  referenced exactly once.
- `app/__init__.py` — `__version__` 1.62 → 1.65 (one bump per completed-task commit).

## Decisions Made

All six decisions are recorded in the frontmatter `key-decisions` block (D-01 through D-07 as they
apply to this plan). Nothing was decided outside the plan's own decision set.

One judgement call worth naming: the plan's acceptance criterion `grep -c "offline"
app/services/sync.py` is unchanged from HEAD forced the `push_schema_ok` docstring to describe the
Phase-30 bundle gate WITHOUT spelling the module name (it now says "the Phase-30 bundle-upload gate
`schema_version_ok` … (D-02 / 33-PATTERNS.md AP-5)"). The traceability is preserved through the
decision ids; the count stayed at 1, matching HEAD.

## Deviations from Plan

None — plan executed exactly as written. No deviation rule fired, no auto-fix was needed, no
architectural question arose.

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

- **Cross-test-module import had no precedent.** The plan requires `build_ndjson` from
  `tests/test_merge.py`, but nothing in the suite imports another test module. `tests/` has no
  `__init__.py` and pytest runs in the default `prepend` import mode, so `from test_merge import
  build_ndjson` resolves; confirmed by a clean `--collect-only` (7 tests, exit 0). Ruff's isort
  rule then classified `test_merge` as third-party, so the import block was reordered to satisfy
  `ruff check`.
- **Nothing else.** `current_schema_version(session)` in the new gate autobegins a read
  transaction, but step (5)'s pre-existing `session.rollback()` already discards it before the
  single owned write transaction opens — no change was needed there.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_sync_schema_gate.py -q --collect-only` | 7 tests collected, exit 0 (RED scaffold collects cleanly) |
| `uv run pytest tests/test_sync_schema_gate.py -q` after Task 1 | 6 failed / 1 passed — RED on missing `push_schema_ok` / `SCHEMA_AHEAD_ERROR`, no collection error |
| `uv run pytest tests/test_sync_schema_gate.py tests/test_sync_api.py -q` | **31 passed** (7 + 24) |
| `uv run pytest -q` (full suite) | **4 failed, 1491 passed, 14 skipped** in 441.28s — the 4 are the known-red `tests/test_sync_ui.py` cases (`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`, `test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`), pre-existing since ≤ `49a53d2` |
| `git diff --stat app/services/offline.py` | empty (D-02 / AP-5) |
| `grep -c "offline" app/services/sync.py` | 1 — unchanged from HEAD |
| `grep -c "business_date" app/routes/sync.py` / `app/services/sync.py` | 0 / 0 (Pitfall 16) |
| `grep -n "SCHEMA_AHEAD_ERROR" app/routes/sync.py` | `:56` declaration, `:140` single reference in the push handler |
| `uv run ruff check` on all three touched files | All checks passed |

## Success Criteria

- [x] An ahead-client push returns 409 with the RU constant naming both versions; a behind-client
      push returns 200 and merges (VA-1).
- [x] A refused push leaves `synced_at IS NULL` on every client row and does not advance
      `sync_state.last_sync_at` (VA-2).
- [x] `app/services/offline.py` is byte-unchanged (D-02).
- [x] `business_date` appears nowhere in `app/routes/sync.py` or `app/services/sync.py`
      (Pitfall 16).

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-01 (tampering: silent field drop behind a 200) | Mitigated — unreachable for an ahead client; `_ledger_row` itself untouched (AP-3), its drop still to be pinned by VA-4 in plan 33-03 |
| T-33-02 (info disclosure via the 409 body) | Mitigated — only two Alembic revision ids are interpolated; no request bytes, exception text or token |
| T-33-03 (self-inflicted DoS: a refused client retrying every 300 s) | **Deferred to plan 33-02 by design** — this plan creates the refusal loop, D-09's back-off to `MAX_INTERVAL_SECONDS` closes it |
| T-33-04 (repudiation: a refused client believing it was accepted) | Mitigated — VA-2 pins it |
| T-33-SC (supply chain) | Vacuous — no package installed, `pyproject.toml` untouched |

## Known Stubs

None. Nothing was left hardcoded, placeholdered or unwired.

## Threat Flags

None — no new network endpoint, auth path, file access pattern or schema change was introduced.
The gate adds a refusal branch to an existing authenticated endpoint.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready:** plan 33-02 (SYNC-12/13 client half) can build on `SyncResult` reaching `error` on a
  409; T-33-03's retry back-off is its explicit job.
- **Still blocked:** wave 2 remains gated on the human-only plan 33-04 inputs. Both were measured
  read-only on s1 this session and are recorded here so the migration author does not have to
  re-measure: **`alembic current` = `0026 (head)`**, and the effective **`DISPLAY_TZ` =
  `Europe/Moscow`**, supplied by the `app/config.py:76` fallback (there is no `DISPLAY_TZ` line in
  `.env.production` and the container env value is empty) — that is the literal that must be baked
  into migration `0027`'s backfill.
- **Carry forward:** the gate is asymmetric, so the rollout order in ROADMAP.md still holds and is
  now enforced by code: migrate + redeploy s1 **first**, then cut the client release tag. A client
  tag cut first now fails loudly with 409 instead of losing rows silently.
- **Note for 33-03:** `push_schema_ok`'s lexicographic comparison is a live dependency on
  `test_revision_ids_are_fixed_width`. If that tripwire is ever relaxed, this predicate must switch
  to a parsed comparison in the same commit.

## Self-Check: PASSED

All four claimed files exist on disk; all three task commits (`7c529e4`, `13695a3`, `3c88252`)
are present in `git log`.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
