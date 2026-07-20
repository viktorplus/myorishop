---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Operator Sync, Central Server & Roles
status: verifying
stopped_at: Phase 30 UI-SPEC approved
last_updated: "2026-07-20T15:51:37.988Z"
last_activity: 2026-07-20
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 31
  completed_plans: 31
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18)

**Core value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.
**Current focus:** Phase 30 — offline-self-uploading-file

## Current Position

Phase: 30 (offline-self-uploading-file) — EXECUTING
Plan: 4 of 4
Status: Phase complete — ready for verification
Last activity: 2026-07-20

Progress: [██████████] 100%

**v3.0 phase map (Phases 25-30):**

1. Phase 25 — Authentication, Roles & User Attribution (AUTH/USER/ROLE + RPT-01, 16 reqs) — local, testable first
2. Phase 26 — PostgreSQL Portability & Append-Only Parity (SRV-01/02)
3. Phase 27 — Shared Idempotent Merge Core (SYNC-02/03/04/05) — **research flag** (server-authoritative Tier-B conflict policy + `Product.code` collision rule)
4. Phase 28 — Central Server: Hosting & Sync API (SRV-04, SYNC-09)
5. Phase 29 — Online Client Sync (SYNC-01/06/07/08, SRV-03)
6. Phase 30 — Offline Self-Uploading File (OFF-01..07) — **research flag** (self-contained-file mechanism + trust/version model)

## Performance Metrics

**Velocity:**

- Total plans completed: 97 (v1.0-v2.0)
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-24 (v1.0-v2.0) | 86 | - | - |
| 25-30 (v3.0) | TBD | - | - |
| 28 | 6 | - | - |
| 29 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion. Per-plan v1.0-v2.0 timings archived with their milestones.*
| Phase 25 P01 | ~10min | 2 tasks | 5 files |
| Phase 25 P02 | ~8min | 3 tasks | 3 files |
| Phase 25 P03 | ~18min | 3 tasks | 5 files |
| Phase 25 P04 | ~30min | 3 tasks | 8 files |
| Phase 25 P05 | ~25min | 3 tasks | 7 files |
| Phase 25 P06 | 12min | 3 tasks | 4 files |
| Phase 25 P07 | ~15min | 2 tasks | 3 files |
| Phase 25 P08 | 25 min | 3 tasks | 6 files |
| Phase 25 P09 | 5min | 1 tasks | 2 files |
| Phase 26 P01 | ~12min | 2 tasks | 4 files |
| Phase 26 P02 | ~3min | 2 tasks | 2 files |
| Phase 26 P03 | ~6min | 3 tasks | 3 files |
| Phase 27 P01 | ~14min | 2 tasks | 2 files |
| Phase 27 P02 | ~20min | 2 tasks | 3 files |
| Phase 27 P03 | ~18min | 2 tasks | 2 files |
| Phase 27 P04 | ~9min | 2 tasks | 2 files |
| Phase 28 P01 | ~35min | 3 tasks | 5 files |
| Phase 28 P02 | ~20min | 3 tasks | 4 files |
| Phase 28 P03 | 23min | 3 tasks | 7 files |
| Phase 28 P04 | ~30min | 3 tasks | 3 files |
| Phase 28 P05 | ~13min | 3 tasks | 6 files |
| Phase 28 P06 | ~22min | 3 tasks | 10 files |
| Phase 29 P01 | 25min | 3 tasks | 7 files |
| Phase 29 P02 | 15min | 2 tasks | 2 files |
| Phase 29 P03 | 40min | 2 tasks | 3 files |
| Phase 29 P04 | 40min | 2 tasks | 5 files |
| Phase 29 P05 | 45min | 2 tasks | 5 files |
| Phase 30 P01 | 8min | 2 tasks | 1 files |
| Phase 30 P02 | ~12min | 3 tasks | 5 files |
| Phase 30 P03 | ~20min | 3 tasks | 3 files |
| Phase 30 P04 | 15min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table (v1.0-v2.0 milestone decisions archived there and in `.planning/RETROSPECTIVE.md`).

**v3.0 roadmap-level decisions (2026-07-18):**

- **Dependency-ordered build:** identity/auth first (locally testable, unblocks attribution) → prove one model set on PostgreSQL → harden the shared merge engine in isolation → server + sync API → online client sync → offline self-uploading file last. The shared idempotent merge engine (Phase 27) is built and hardened before either transport (Phases 29/30) — both are thin callers of one engine.
- **Operator revisions override research where they disagree:** mobile is server-only (SRV-04, no offline mobile install); the offline path is upload-only via a self-contained self-uploading file to a server with no app installed (OFF-01..07, not peer import); Tier-B mutable master-data conflict resolution is server-authoritative (SYNC-05).
- **RPT-01 placed in Phase 25** (attribution phase) alongside USER-06 — same operator-filter pattern, cleanest coverage.
- **Device identity** (per-install unique `device_id`, replacing the static `device-01` default) is a Phase 25 pre-flight for all later sync.
- [Phase ?]: Phase 25: secret_key + per-install device_id persisted under gitignored data/ outside synced DB; env overrides win
- [Phase ?]: Phase 25: author_id added via native op.add_column (never batch_alter_table) so append-only triggers survive; pre-auth rows stay NULL (no backfill)
- [Phase ?]: Phase 25-03: security core is pure-Python and unit-tested with the plain session fixture before any app wiring; author_fields() falls back to settings.operator_name so existing tests stay green
- [Phase 25]: Phase 25-04: app-level auth boundary ON — single Depends(auth_guard) + SessionMiddleware + NotAuthenticated handler (303 HTML / 401+HX-Redirect HTMX) guards every route incl. export/backup; legacy suite kept green via an authenticated client fixture that overrides the whole guard
- [Phase ?]: Phase 25-05: admin boundary enforced server-side via require_role on warehouses/dictionary/settings/users include_router calls (operator 403 before route body); /settings/users create/deactivate/reactivate/reset ships with scoped CSRF hx-headers until Plan 06 adds the base-chrome line
- [Phase ?]: Plan 25-06: logout is a hrefless hx-post chrome control; NAV-08 smoke count retargeted to href-bearing links to preserve its 8-nav-item intent
- [Phase 25]: USER-05: author_id stamped at both single write paths via author_fields(); contextvars->threadpool propagation proven end-to-end (no explicit-param fallback needed)
- [Phase 25]: Plan 25-08: History «Кто» column resolves the LIVE display_name via a LEFT OUTER JOIN on author_id (never inner, so pre-auth NULL-author rows survive, shown as muted frozen created_by «operator»); the «Пользователь» filter select on /reports/sales lives INSIDE the innerHTML-swapped sales_report_results.html partial so the shared period_filter hx-include (#sales-results select) reaches it and it survives swaps
- [Phase ?]: Phase 25-09: /finance/report nav highlight moved from admin «Настройки» to «Финансы» (operator-visible per UAT test 1); active-state CSS-class only, no route/gate change
- [Phase 26]: settings.database_url is the single DB-URL source of truth (sqlite default filled in _resolve_local_identity; DATABASE_URL env wins), read by alembic/env.py and app/db.py in Plan 03; no PG credential hardcoded (T-26-02)
- [Phase 26]: PG-parity tests match append-only rejection on the message SUBSTRING 'append-only' (PG raises a driver exception, not SQLite IntegrityError); tests/test_pg_parity.py skips on SQLite, RED in CI until Plans 02-03
- [Phase ?]: Phase 26-02: append-only trigger DDL is dialect-branched IN-PLACE inside frozen migrations 0001/0013 via op.get_bind().dialect.name (PL/pgSQL RAISE EXCEPTION on PG, unchanged SQLite RAISE(ABORT) path); trigger names + 'append-only' message substrings identical across dialects (WR-06 additive-only)
- [Phase 26]: Phase 26-03: settings.database_url wired through build_engine_from_url (app/db.py) + alembic/env.py; PRAGMA listener, parent-dir mkdir, render_as_batch dialect-gated to sqlite; CI pg-parity job on postgres:17 proves SRV-01/SRV-02 (build_engine(db_path) signature preserved, conftest untouched)
- [Phase 27]: Phase 27-01: the ONE NDJSON exchange format (SYNC-04) lives in app/services/merge.py — header-first, per-line `kind`, verbatim carriage of origin id/device_id/seq/author_id/created_by; parse_exchange rejects malformed/bad-version/unknown-kind/missing-header/float-money before any DB touch (ASVS V5) and forces wire synced_at→None (server-owned); money-field float guard is schema-derived from model.__mapper__.columns (no hand-maintained list). Pure module (no HTTP/file/dialects). Conflict/MergeReport dataclasses declared now, populated in Plans 02-03
- [Phase 27]: Phase 27-02: apply_merge (SYNC-02/03) appends operations+cash_movements VERBATIM by origin UUID via a PORTABLE pre-select set-difference (_insert_new, chunked at 500) — no sqlalchemy.dialects, no on_conflict, no re-mint through the write path; synced_at forced None. It NEVER commits (caller owns the all-or-nothing transaction — a poisoned record rolls back to 0 rows). recompute_derived(session) extracted from rebuild_stock (non-committing, invariant-asserting); rebuild_stock delegates then commits (behavior-preserving). Post-merge Product.quantity/Batch.quantity recomputed from the ledger; cash balance stays a live SUM. Reference-upsert seam left BEFORE the ledger stage for Plan 03. merge-twice==once proven byte-identical
- [Phase 27]: Phase 27-04 (SYNC-02/04/05): new tests/test_merge_pg.py proves the ONE engine portable on PostgreSQL — merge-twice==once idempotency (portable pre-select set-difference, not a dialect on_conflict) + Product.code collision rename against PG's postgresql_where partial index uq_products_code_active. Reuses the Phase 26 harness (module skipif on settings.database_url, _engine/_upgrade_head, sessionmaker + try/finally engine.dispose); literal-constant/fixed-UUID seeds only (V5) so it re-runs against a standing PG server (ledger rows never DELETEd → set-difference finds them present); idempotency asserted on a snapshot of derived state + report2 inserted==0/skipped==1, not on fresh-vs-rerun counts. The existing pg-parity CI job (postgres:17) got ONE new step running the slice with DATABASE_URL set — no new job, no engine/ledger change, no migration. Phase 27 COMPLETE (4/4); Phases 28/30 are thin callers of a both-dialects-proven engine
- [Phase 27]: Phase 27-03 (SYNC-05): apply_merge now upserts reference rows insert-if-new + ROW-level server-wins (existing UUID discarded, never field-merged/resurrected/deleted from client input), in FK order (warehouses→products→customers→dictionary→batches→sales) driven by KIND before the ledger — a shuffled file merges identically, a missing parent fails the child FK and the caller rolls back all-or-nothing. Inline deleted_at tombstones: a new soft-deleted row inserts, a server row is never flipped. Cross-device Product.code duplicate → RENAME the incoming loser deterministically (_suffix_code = base truncated + '~' + first 4 hex of the losing UUID, ≤ String(20)), KEEP its UUID (ops stay valid), incumbent keeps the clean code, reported in MergeReport.conflicts; re-merge renames identically. Shared _partition_new set-difference backs both _insert_new + _upsert_reference; _reference_row zeroes wire quantity (recompute is truth). Insert-only + portability grep gates == 0. NOT done: same-batch two-new-same-code tie-break (hits the uq_products_code_active DB backstop → rollback; deferred to Phase 28/29 admin reconciliation)
- [Phase ?]: Phase 28-01 (SRV-02/SYNC-01): the two ledger *_no_update triggers are now COLUMN-SCOPED via migration 0018 — a value-based FOR EACH ROW WHEN guard enumerating every immutable column (14 ops / 10 cash), so synced_at can be stamped while a mixed 'SET synced_at=..., qty_delta=99' statement is still rejected wholesale (value-based, NOT 'UPDATE OF', which fires on mention and would leave that smuggling path open). DELETE triggers untouched. PG guard MUST cast NEW.payload::text (sa.JSON -> pg json has no equality operator; uncast raises 'operator does not exist: json = json'). The 0001/0013 PL/pgSQL functions are reused, never dropped. LOCKSTEP: app/db.py::APPEND_ONLY_TRIGGERS (the live source for tests/conftest.py fixtures, which never use Alembic) must move in the SAME commit as any trigger migration; tests/test_append_only_cursor.py carries two tripwires (schema-derived + DDL-derived) so a future ledger column fails loudly instead of silently escaping the guard. Verified on postgres:17 locally. Note: an append-only probe written as 'SET col = col' is now a permitted no-op and false-greens (fixed in test_batches.py 0008 case).
- [Phase ?]: SHA-256 (not Argon2) for device tokens: 256-bit CSPRNG entropy makes a slow KDF pointless while adding ~50-100ms per sync request (RESEARCH A1)
- [Phase ?]: No token expiry — revocation-only; token_prefix is a non-secret index key for one-read verification
- [Phase ?]: Plan 28-03: require_device in security.py keeps devices.py FastAPI-free; route rolls back the expire_on_commit read txn before with session.begin()
- [Phase ?]: Pull cursor is composite (cursor_column, id): inclusive on timestamp, id tie-break guarantees termination; resume kind recovered by after_id PK membership probe (28-04)
- [Phase ?]: SYNC-09 admin surface /settings/devices mirrors /settings/users verbatim; no new design tokens (no-UI-SPEC phase decision)
- [Phase ?]: Phase 28-06 (SRV-04): startup_backup() gains an explicit engine.dialect.name != sqlite early return (OQ-6) so a PostgreSQL boot can never reach VACUUM INTO; the regression test forces settings.db_path to an EXISTING file so the file-missing accident cannot mask the guard. session_https_only (env SESSION_HTTPS_ONLY, default False) wires the session-cookie Secure flag into SessionMiddleware, true only on the server (T-28-27). deploy/ ships a provider-agnostic systemd unit (ExecStartPre alembic upgrade head mirroring run.bat, uvicorn bound 127.0.0.1), Caddyfile (TLS at proxy, max_size 32MB twin of MAX_PUSH_BYTES), a daily pg_dump timer (Persistent, 30-day retention) and a 269-line DEPLOY.md — no VPS provider, tier, real domain or public IP chosen.
- [Phase ?]: 29-01: sync_token is an .env-only secret (like secret_key), never a sync_state/DB column, so a copied myorishop.db cannot leak the device credential (T-29-01)
- [Phase ?]: 29-01: sync_state uses an Integer singleton PK (id=1), a local-only never-synced table, exempt from the UUID-PK convention that targets synced entities
- [Phase ?]: 29-01: auto-sync toggle/interval live on sync_state (runtime-mutable, D-15), not static .env
- [Phase 29]: sync_client state+presentation layer (29-02): SyncResult, single-row sync_state persistence (D-10), fresh+clamped auto-sync config (D-08/D-15), unsynced badge (D-11), LOCKED D-12 RU formatter — built and unit-tested ahead of the Plan-03 network driver
- [Phase ?]: 29-03: D-14 client pull upsert uses Core update() with server values set explicitly so onupdate keeps the server's updated_at; id+quantity excluded and recompute_derived rebuilds stock from the local ledger — server wins on master data while local stock is preserved
- [Phase ?]: 29-04: manual sync surface — POST /sync/run always-200 OOB handler (SYNC-06) + every-page context processor + base.html nav trigger/status/badge (D-01/D-02); unsynced badge styled inline with locked price-cue token values, no new CSS token
- [Phase ?]: 29-05: interval auto-sync runs as a zero-dependency asyncio loop in the FastAPI lifespan (D-06); the blocking driver is offloaded via anyio.to_thread.run_sync with a fresh Session (D-07); the whole tick is broad-guarded so any error is swallowed and the loop never dies (D-08); cancelled cleanly on shutdown
- [Phase ?]: 29-05: admin Settings «Синхронизация» control persists auto_enabled + interval clamped 60..3600 to sync_state (D-03/D-15); a bad interval is defaulted/clamped, never a 5xx; sync_token never surfaced (T-29-07)
- [Phase ?]: 30-01: Wave-0 offline scaffold pins the D-08 payload_sha256 (record-lines-only, LF-joined) + D-03 token contract (salt offline-upload, scope offline_upload) as the RED-test contract Waves 1-3 must satisfy; not-yet-built offline modules imported INSIDE test bodies so collection stays green
- [Phase ?]: 30-02: payload_digest is the ONE integrity checksum shared by serialize_exchange emit + 30-03 upload verify (D-08)
- [Phase ?]: 30-02: offline upload token = itsdangerous URLSafeTimedSerializer(secret_key, salt='offline-upload'), scope 'offline_upload', TTL 300s (D-03)
- [Phase 30]: 30-03: offline ingest routes are thin callers of Phase-27 apply_merge; the only additions over sync_push are the SHA-256 integrity check (D-08) and the exact-match schema-version gate (D-09), both before any DB touch; in-body upload token means no CSRF and a single narrow ACAO scoped to /api/offline/login (D-05)
- [Phase ?]: Phase 30 offline export (GET /offline/export) is read-only — never stamps synced_at (D-07); client half ships OFF-01/02/03/06 with a self-contained self-uploading HTML file

### Pending Todos

None yet.

### Coverage Gate Overrides

- **Phase 8 (2026-07-11):** The globally-installed `gsd-tools` on PATH (an older `gsd-sdk` build) flagged D-03, D-07, D-08, D-10 as "uncovered" via its `decision-coverage-plan` check. Re-ran the project's own `$HOME/.claude/gsd-core/bin/gsd-tools.cjs gap-analysis` (the up-to-date tool) which confirmed all 11 items (WH-01 + D-01..D-10) are covered — the older global binary's matcher choked on compound citations like `(D-06/D-07)`. The semantic gsd-plan-checker agent also independently confirmed full coverage (Dimension 7: Context Compliance — PASS). No re-plan needed.

### Blockers/Concerns

- ℹ️ [Phase 16] Advisory (cosmetic, desktop only): a movement saved with an empty
  comment renders literal `None` in the `/finance` «Комментарий» column (mobile
  cards handle it correctly). Guard the desktop template cell with
  `{{ movement.note or "" }}` when next touching finance templates. Non-blocking.

- ℹ️ [v2.0 close, 2026-07-18] Phase 22 (Sales Page Rebuild) shipped with 4 manual-only
  test cases (live basket-total arithmetic, incomplete-row marker, customer-mode
  radio round-trip, mobile basket preservation on batch re-tap) never confirmed in
  a live browser — no `22-UAT.md`, unlike the equivalent Phase 18/20 items which
  both have a completed UAT file. All 4 are backed by passing server-side tests;
  only the felt client-side JS behavior is unconfirmed. See
  `.planning/v2.0-MILESTONE-AUDIT.md` for the full breakdown. Recommend a short
  manual browser pass before relying heavily on the rebuilt sale form.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-2w6 | Replace Dictionary + CatalogPrice with a single-catalog-per-code import from oriflame_prices_with_calculations_fixed.xlsx (ДЦ->consultant_cents, ПЦ->consumer_cents) | 2026-07-14 | 3f0a7e3 | [260714-2w6-update-dictionary-pricelist](./quick/260714-2w6-update-dictionary-pricelist/) |
| 260714-fix | Catalog consumer price (ПЦ) now also autofills "Цена продажи" on product form and goods receipt (D-02 in receipts.py superseded); ДЦ still cost-only | 2026-07-14 | 53c3c92 | [260714-fix-catalog-sale-autofill](./quick/260714-fix-catalog-sale-autofill/) |
| 260714-o1z | Kill stale server on port 8000 in run.bat before starting a new one (fixes /dictionary 500 caused by an old process serving stale code) | 2026-07-14 | 5014787 | [260714-o1z-kill-stale-server-port](./quick/260714-o1z-kill-stale-server-port/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 01: 01-UAT.md — offline run.bat launch + browser correction flow + restart persistence (1 pending scenario) | testing | 2026-07-10 (v1.0 close) |
| verification_gap | Phase 01: 01-VERIFICATION.md — same offline run.bat flow | human_needed | 2026-07-10 (v1.0 close) |
| code_review | transfers.py/writeoffs.py: batch-ownership leak, unstripped qty echo (2 advisory) | resolved | 2026-07-13 (v1.1 close) — closed by Phase 20 (D-10/D-11, 20-05/20-06-SUMMARY.md, 2026-07-16) |
| verification_gap | Phase 15: 15-VERIFICATION.md — manual browser check of `/finance` and `/m/finance` balance display through real sale/return forms | confirmed_working | 2026-07-14 (phase 15 execution), confirmed by operator 2026-07-15 |
| doc_drift | `export.py`: `stream_customers_csv` docstring claims a *"Full customer profile dump"* — becomes false once Phase 21 ships address + contacts. Out of scope by design (contacts are 1-to-many and don't fit the flat CSV shape). If `address` is ever added it must go through the existing `_csv_safe`. | acknowledged | 2026-07-17 (phase 21 planning) — accepted debt, close in a future phase |
| uat_gap | Phase 22: no 22-UAT.md for 4 human_needed items (live basket-total math, incomplete-row marker, customer-mode round-trip, mobile basket preservation) — server-side tests all pass, only client-side JS behavior unconfirmed | testing | 2026-07-18 (v2.0 close) — see `.planning/v2.0-MILESTONE-AUDIT.md` |

## Session Continuity

Last session: 2026-07-20T15:50:59.254Z
Stopped at: Phase 30 UI-SPEC approved
Resume file: None

## Operator Next Steps

- Phase 27 (Shared Idempotent Merge Core) is COMPLETE — the one merge engine is proven portable on SQLite + PostgreSQL. Next: `/gsd-plan-phase 28` (Central Server — Hosting & Sync API)
- Phase-gate follow-up: push and confirm the GitHub Actions `pg-parity` job is GREEN including the new `PostgreSQL merge portability` step (postgres:17) — CI is the deliverable proof of the merge PG slice
- Phase 30 is research-flagged — expect a `--research-phase` pass at its plan time
- Optional, non-blocking: a short manual browser pass on Phase 22's 4 unconfirmed items (see Blockers/Concerns above)
