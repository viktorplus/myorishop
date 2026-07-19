---
phase: 28-central-server-hosting-sync-api
plan: 04
subsystem: sync
tags: [sync-api, pull, cursor-pagination, composite-cursor, ndjson, reference-data, srv-04]
requires: [SYNC-09, "require-device-dependency", "sync-path-bypass", "rate-limiter", serialize_exchange]
provides: [sync-pull-endpoint, pull-cursor-service, composite-cursor, schema-version-probe, both-uis-one-app-assertion]
affects: [app/services/sync.py, app/routes/sync.py, tests/test_sync_api.py]
tech-stack:
  added: []
  patterns:
    - "pure pull-cursor service (no HTTP/FastAPI/Response), thin route calls it then serialize_exchange"
    - "COMPOSITE (cursor_column, id) cursor: inclusive on timestamp, id tie-break guarantees termination"
    - "resume-kind recovered by after_id PK membership probe — before-kinds skipped, resume-kind composite, after-kinds >= since"
    - "per-kind cursor column: created_at for sale (no updated_at), updated_at for the rest"
    - "cursor halves travel as X-Sync-Next-* HTTP headers, not inside the fixed Phase 27 NDJSON envelope"
    - "schema_version derived from live Alembic MigrationContext.get_current_revision(), never hardcoded"
key-files:
  created:
    - app/services/sync.py
  modified:
    - app/routes/sync.py
    - tests/test_sync_api.py
decisions:
  - "resume position is recovered from after_id via a PK membership probe (kinds BEFORE the resume kind are SKIPPED, not re-scanned) — the plan's 'carry the kind forward' option realised without a third header, so paging cannot loop between kinds; the plan's alternative '>= since re-scan of earlier kinds' can non-terminate across kinds and was rejected"
  - "StreamingResponse over the serialize_exchange generator (not a materialised body) to honour the T-28-12 memory-exhaustion mitigation"
  - "SRV-04 marker is 'mobile-tabbar' — a class unique to mobile_base.html, absent from desktop base.html — proving one app object renders two distinct UIs"
metrics:
  duration: ~30min
  tasks: 3
  files: 3
  completed: 2026-07-19
---

# Phase 28 Plan 04: GET /api/sync/pull — Reference-Data-Down (SYNC-09 / SRV-04) Summary

The read half of the sync surface: `GET /api/sync/pull` streams token-authenticated, cursor-paged, reference-ONLY NDJSON through the unmodified Phase 27 serializer, backed by a pure pull-cursor service whose COMPOSITE `(cursor, id)` cursor is inclusive on the timestamp yet always terminates. Plus a standing SRV-04 assertion that one app object renders both the desktop (`/`) and mobile (`/m/`) UIs.

## What Was Built

`app/services/sync.py` is a PURE module (no HTTP, no web framework, no serialization) mirroring the `merge.py` contract. It exposes `PULL_KINDS` (the six reference kinds only — the two ledger kinds are deliberately excluded), `CURSOR_COLUMN` (`created_at` for `sale`, `updated_at` for the rest), `DEFAULT_PULL_LIMIT=500`, `MAX_PULL_LIMIT=2000`, the frozen `PullPage` dataclass, `collect_reference_records`, and `current_schema_version`.

`collect_reference_records` walks `PULL_KINDS` in FK-dependency order, accumulating up to `limit` records. The cursor is **composite `(cursor_column, id)`**: `next_since` is the last record's cursor value and is inclusive, so the primary-key tie-break is what guarantees forward progress across a run of identical timestamps (the documented bulk-edit case). On resume, the kind that owns `after_id` is recovered by a globally-unique-PK membership probe; kinds BEFORE it were already drained and are SKIPPED (so paging can never loop between kinds), the resume kind gets the strictly-greater composite predicate `or_(col > since, and_(col == since, id > after_id))`, and kinds AFTER it are full-scanned (`>= since` when a bound is present). Soft-deleted rows are included (tombstones the client needs). Portable ORM only — no `tuple_`, no dialect SQL. `current_schema_version` reads the live Alembic revision via `MigrationContext`, falling back to `""` for create_all fixtures.

`app/routes/sync.py` gains `GET /api/sync/pull` (plain `def`, read-only, no `session.begin()`/`commit()`): rate-limit → validate `since` as ISO-8601 (400 `INVALID_CURSOR_ERROR` on garbage) → `collect_reference_records` → `serialize_exchange` (UNCHANGED) → `StreamingResponse` with `media_type=application/x-ndjson`. Both cursor halves are exposed as `X-Sync-Next-Since` / `X-Sync-Next-After-Id` response headers (each omitted only when None, never one without the other); a lone `after_id` with no `since` is ignored.

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | `app/services/sync.py` — pure composite-cursor query + record assembly + schema-version probe | `e9de52e` |
| 2 | `GET /api/sync/pull` route — NDJSON via the unmodified Phase 27 serializer, cursor headers | `a393637` |
| 3 | 11 pull + SRV-04 tests appended to `tests/test_sync_api.py` | (this commit) |

## Key Decisions

- **Composite cursor with resume-kind recovery, not a `>= since` re-scan of earlier kinds.** The plan offered two options for resuming across a multi-kind page. The literal "re-scan earlier kinds with `>= since`" option can NON-TERMINATE when an earlier kind holds more boundary-timestamp rows than `limit` (the loop ping-pongs between kinds). I realised the plan's more robust "carry the kind forward" option WITHOUT a third header: `after_id` is a globally-unique UUID, so the resume kind is recovered by a PK membership probe, kinds before it are skipped (already fully delivered), and only the resume kind gets the composite `id`-advance. This is lossless (an earlier kind is skipped only after it was drained) and terminating in all cases, proven by `test_pull_paginates_past_identical_timestamps`.
- **`StreamingResponse` over the generator** rather than a materialised body, honouring the T-28-12 memory mitigation.
- **SRV-04 marker = `mobile-tabbar`** (a class unique to `mobile_base.html`), asserted present in `/m/` and absent from `/`, proving two distinct templates from one app object.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs, missing functionality, or blockers encountered during execution.

### Documented implementation choice (not a deviation from intent)

The plan explicitly instructed "Document whichever form is implemented" for the multi-kind resume strategy. The implemented form (resume-kind recovery + skip-before) is documented in the `collect_reference_records` docstring and in Key Decisions above.

### Out of Scope (logged, not fixed)

Three pre-existing `E501` ruff violations (`app/routes/dictionary.py:73`, `app/routes/products.py:133`, `app/routes/transfers.py:64`) still fail `uv run ruff check app` — already logged in `deferred-items.md` from Plan 03, in routers untouched by this plan (SCOPE BOUNDARY). Every file this plan created or modified passes `ruff check` cleanly.

No architectural changes, no checkpoints, no auth gates, no new packages.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_sync_api.py -q` | **23 passed** (12 push from Plan 03 + 11 new) |
| `uv run pytest -q` (full SQLite suite) | **1066 passed, 11 skipped** (was 1055 before this plan) |
| `git log --oneline 785ccf2..HEAD -- app/services/merge.py` | empty (Phase 27 engine untouched) |
| `grep -c '"operation"' app/services/sync.py` | 0 |
| `grep -c "tuple_" app/services/sync.py` | 0 |
| `grep -Ec "fastapi\|Response\|StreamingResponse\|open\(" app/services/sync.py` | 0 (module is pure) |
| `grep -c "sqlalchemy.dialects" app/services/sync.py` | 0 |
| `grep -c "async def" app/routes/sync.py` | 0 |
| `grep -c "session.commit()" app/routes/sync.py` | 0 |
| `grep -c '@router.get("/api/sync/pull")' app/routes/sync.py` | 1 |
| `ruff check app/services/sync.py app/routes/sync.py tests/test_sync_api.py` | clean |

## Success Criteria

- [x] `GET /api/sync/pull` serves token-authenticated, cursor-paged, reference-only NDJSON the Phase 27 parser round-trips (`test_pull_requires_token`, `test_pull_returns_reference_records`, `test_pull_round_trips_through_parse_exchange`)
- [x] Cursor inclusive on the timestamp and per-kind correct — `created_at` for sales (`test_pull_cursor_is_inclusive`, `test_pull_sale_uses_created_at`)
- [x] Composite `(cursor, id)` cursor terminates across identical-timestamp runs, proven with a hard iteration cap (`test_pull_paginates_past_identical_timestamps`)
- [x] Ledger rows never leak (`test_pull_excludes_ledger_kinds`)
- [x] SRV-04: `/` and `/m/` both 200 from one app object, distinct templates (`test_both_uis_one_app`)
- [x] Phase 27 merge engine unmodified

## Threat Model Coverage

| Threat ID | Disposition | How covered |
|-----------|-------------|-------------|
| T-28-02 (unauthenticated read) | mitigate | pull declares `Depends(require_device)`; `test_pull_requires_token` (401, not 303) |
| T-28-20 (ledger over-exposure) | mitigate | `PULL_KINDS` reference-only (grep 0 for `"operation"`); `test_pull_excludes_ledger_kinds` |
| T-28-21 (SQL injection via `since`) | mitigate | `since` validated with `datetime.fromisoformat`, used only as a bound `select()` param; no string interpolation |
| T-28-12 (unbounded pull) | mitigate | `limit` clamped to `MAX_PULL_LIMIT=2000` inside the service; same token bucket as push; `StreamingResponse` avoids materialising |
| T-28-32 (non-terminating pagination) | mitigate | composite `(cursor, id)` cursor + both headers required; `test_pull_paginates_past_identical_timestamps` asserts termination within a cap |
| T-28-22 (server stamping/trusting synced_at) | mitigate | pull is read-only — no `session.begin()`/`commit()` (grep 0); locked semantic documented in the `sync.py` docstring |
| T-28-23 (divergent wire format) | mitigate | route calls the UNMODIFIED `serialize_exchange`; `test_pull_round_trips_through_parse_exchange` proves one format |
| T-28-SC (supply chain) | accept | zero new packages; `alembic` already a project dependency |

## Known Stubs

None.

## Threat Flags

None. The one new endpoint (`GET /api/sync/pull`) and its two trust boundaries are fully enumerated in the plan's `<threat_model>` and covered above. No new network surface, auth path, file access, or schema change beyond what the plan anticipated.

## Notes for Future Plans

- **Phase 29 client sync** calls `GET /api/sync/pull` and MUST echo BOTH `X-Sync-Next-Since` and `X-Sync-Next-After-Id` back as the `since` and `after_id` query params, repeating until it receives fewer than `limit` records. Sending only `since` loops forever across a run of identical timestamps.
- **Phase 29** owns the CLIENT-side `synced_at` stamping. The SERVER never writes `synced_at` (it stays NULL) — this is the load-bearing locked semantic.
- **Phase 30 OFF-07** depends on `current_schema_version` being truthful — it derives the live Alembic head, never a hardcoded string.
- The reference upsert on the receiving side (Phase 27, Plan 03) is idempotent, so the inclusive `>= since` boundary re-delivery on the first page of a resume costs nothing.

## Self-Check: PASSED

- FOUND: `app/services/sync.py`
- FOUND: `app/routes/sync.py` (GET /api/sync/pull)
- FOUND: `tests/test_sync_api.py` (23 test functions)
- FOUND: commit `e9de52e`
- FOUND: commit `a393637`
