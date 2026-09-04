---
gsd_state_version: 1.0
milestone: v5.0
milestone_name: Corrections, Dates & Currency
status: executing
stopped_at: "Completed 33-02-PLAN.md (SYNC-10 client half: schema_mismatch status + D-09 back-off)"
last_updated: "2026-09-04T09:32:26.460Z"
last_activity: 2026-09-04
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 15
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-04)

**Core value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.
**Current focus:** Phase 33 — back-dated-operations

## Current Position

Phase: 33 (back-dated-operations) — EXECUTING
Plan: 3 of 15
Status: Ready to execute
Last activity: 2026-09-04

**Phase set for v5.0:**

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 33 | Back-Dated Operations | 15 (6 waves) | Executing — 2/15 done (33-01, 33-02) |
| 34 | One-Tap Reversal (сторно) & Currency Render Coverage | TBD | Not started |
| 35 | Mobile Card Editing | TBD | Not started |

**Phase 33 wave-2 inputs — MEASURED on s1, read-only, 2026-09-04 (V13/V14 answered):**
`alembic current` = **`0026 (head)`**; effective **`DISPLAY_TZ` = `Europe/Moscow`**, supplied by the
`app/config.py:76` fallback — there is no `DISPLAY_TZ` line in `.env.production` and the container
env value is empty. That timezone is the literal that must be baked into migration `0027`'s
backfill (plan 33-04). Do not re-measure; do not assume `.env.production` sets it.

## Performance Metrics

**Velocity:**

- Total plans completed: 110 (v1.0-v2.0)
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-24 (v1.0-v2.0) | 86 | - | - |
| 25-30 (v3.0) | TBD | - | - |
| 28 | 6 | - | - |
| 29 | 5 | - | - |
| 31 | 8 | - | - |
| 32 | 5 | - | - |
| 33 (v5.0) | 15 planned | - | - |
| 34-35 (v5.0) | TBD | - | - |

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
| Phase 31 P01 | 12min | 3 tasks | 4 files |
| Phase 31 P03 | 18min | 3 tasks | 5 files |
| Phase 31 P04 | 22min | 3 tasks | 3 files |
| Phase 31 P05 | 16min | 3 tasks | 5 files |
| Phase 32 P01 | 13min | 2 tasks | 2 files |
| Phase 32 P02 | 5min | 2 tasks | 3 files |
| Phase 32 P03 | 20m | 2 tasks | 2 files |
| Phase 32 P05 | 20m | 2 tasks | 5 files |
| Phase 31 P06 | 34min | 2 tasks | 4 files |
| Phase 31 P07 | 38min | 2 tasks | 4 files |
| Phase 31 P08 | 33min | 3 tasks | 5 files |
| Phase 33 P01 | 32min | 3 tasks | 4 files |
| Phase 33 P02 | 24min | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table (v1.0-v2.0 milestone decisions archived there and in `.planning/RETROSPECTIVE.md`).

**v5.0 roadmap-level decisions (2026-09-04):**

- **Three phases, forced ordering: 33 → 34 → 35.** Phase 33 (back-dated operations) → Phase 34 (one-tap reversal + the currency render tail) → Phase 35 (mobile card editing). 33 → 34 is a **hard** dependency, not a preference: a reversal must inherit the origin's business date AND the readers must already bucket by it, or the feature ships visibly broken — and there is no retrofit, because the ledger is append-only.
- **Coverage:** all 36 v5.0 requirements mapped exactly once — SYNC-10..13 + DATE-01..08 → Phase 33; REV-01..11 + CUR-03..08 → Phase 34; MOB-02..08 → Phase 35. No orphans, no duplicates (REQUIREMENTS.md Traceability filled 2026-09-04). REQUIREMENTS.md's stated total of "34" was an arithmetic error against its own five-group breakdown; corrected to 36 with a note, no REQ-ID touched.
- **Sync hardening is Phase 33's first plans, not a separate phase.** `merge._ledger_row` projects an incoming batch through the *receiver's* columns and `POST /api/sync/push` has no `schema_version` gate, so a client that self-updates ahead of the s1 rebuild pushes `business_date`, the server drops it, returns 200, and the client stamps `synced_at` — permanent, unrecoverable loss behind a success response. SYNC-12 also *determines the new columns' definitions* (all four must be nullable).
- **All four ledger columns land in ONE migration** (`operations.business_date`, `cash_movements.business_date`, `operations.reverses_op_id`, `cash_movements.reverses_movement_id`): one dual-dialect trigger rewrite, one five-artifact lockstep, one fleet skew window instead of two. The two `reverses_*_id` columns ship unused but trigger-guarded; Phase 34 only starts writing them.
- **Migration internal order is LOCKED:** `add_column` → timezone-correct backfill → THEN extend the append-only trigger's column enumeration. Reversed, the backfill trips the guard it just installed and `alembic upgrade head` aborts mid-upgrade on the live server. The **five-artifact lockstep is one commit**: migration (both dialect branches + both `downgrade()` halves) + `app/db.py::APPEND_ONLY_TRIGGERS` + both `IMMUTABLE_*_COLUMNS` frozensets + the two test constants. Migration `0026` exists solely because this was missed once.
- **Rollout order:** migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → only then cut the client release tag.
- **Currency render coverage (CUR-03..08) is a PLAN inside Phase 34, not a phase.** The feature shipped 2026-08-10 (quick task `260810-2g3`, migrations 0023–0026); the tail has no schema work and blocks nothing, but the reversal control, the currency marker and the business-date column all edit `operations.py::history_view` + `history_rows.html` + `history_cards.html` — so it sits adjacent to the reversal work (those files edited once, not three times) and completes before Phase 35 so the mobile product form ships with the final money render. Do not parallelize it with a reversal plan touching the История templates.
- **Research flags:** Phase 34 needs `--research-phase` at plan time (transfer sibling-resolution has no handle in existing data; the non-SUM aggregate audit spans four service modules — both discovery work). Phases 33 and 35 do **not** — the migration ritual is written verbatim in `0017`/`0018`/`0024`/`0026`, and `mobile_batches.py` is an exact shipped route-pair precedent.
- **Locked product decisions (operator, 2026-09-04):** sales are excluded from storno (use «Возврат»); back-dating is unbounded with a «задним числом» marker, future dates rejected; mobile customer editing reaches **full desktop parity including all four `CONTACT_KINDS` with multi-value add/remove** — which closes the delete-by-omission trap by construction rather than by a guard, and makes Phase 35 meaningfully larger than a flat-field form.
- **All 16 `needs verification` items from research are assigned:** V1/V2/V3 (blocking) + V4 + V13/V14 (pre-rollout) + V15 (advisory) → Phase 33; V5/V6 (reversal) + V7..V12 (currency plan) → Phase 34; V16 closed at requirements time by operator decision 1. None dropped — each is written into its owning phase's detail section in ROADMAP.md.
- **All 26 numbered pitfalls are owned:** 1, 2, 3, 4, 14, 15, 16, 20, 21 → Phase 33; 5, 6, 7, 9, 10, 11, 12, 13, 19, 23, 25, 26 → Phase 34; 8, 17, 18, 22, 24 → Phase 35.

**v4.0 roadmap-level decisions (2026-07-22):**

- **Two dependency-ordered phases, forced ordering:** Phase 31 (packaging + stable launcher + code/data physical separation + signed-release pipeline) MUST land before Phase 32 (in-app self-update) — there is nothing safe to update *to*, and no safe over-the-top swap, until code/data separation + a launcher + a signed release format exist. Phase 32 cannot even be end-to-end tested until two real signed releases exist (cut throwaway v1.N/v1.N+1 tags to exercise the round trip).
- **Coverage:** all 12 v4.0 requirements mapped exactly once — PKG-01..05 → Phase 31, UPD-01..07 → Phase 32. No orphans, no duplicates (REQUIREMENTS.md Traceability filled 2026-07-22).
- **Locked product decisions (from milestone questioning):** apply policy = notify-and-confirm (never silent auto-apply, UPD-03); release signing = OFFLINE minisign key with the public key vendored in the client (PKG-05/UPD-02); installer = UNSIGNED + documented one-time SmartScreen "Run anyway" (code-signing cert deferred, PKG-02). The central server is a hard no-op throughout (UPD-06, dialect-gated).
- **Data preservation by physical layout, not careful code (PKG-03):** the SQLite DB, .env, per-install secret_key/device_id, and backups/ must be *siblings* of the swappable app directory, never children — so a directory swap physically cannot reach operator state. Relocating this state out of the install/CWD-relative defaults is the Phase-31 prerequisite; getting it wrong wipes the only copy of the operator's ledger.
- **Reused shipped mechanisms (not new work):** `backup.create_backup()` VACUUM INTO as the pre-update anchor (UPD-04); the `engine.dialect.name == "sqlite"` gate for the server no-op (UPD-06); the `_auto_sync_loop` background-loop shape for the startup/periodic check; the `APP_VERSION` header global / `app/__init__.py` `__version__` for the version tie-in (UPD-05).
- **Version-compare is a known pitfall:** the "1.<N>" scheme breaks under string compare ("1.9" > "1.10" is True) — compare the integer N and apply only if strictly newer (anti-downgrade, UPD-05); test the 9→10 boundary.
- **Both phases are research-flagged:** Phase 31 — a small spike to settle bundled-runtime strategy (Python embeddable vs PyInstaller `--onedir`) before writing `build_release.py`. Phase 32 — security-critical, carries a threat model; expect `/gsd-plan-phase 32 --research-phase` for the trust model + controlled-shutdown/IPC (`pending.json`) contract.

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
- [Phase 31]: 31-01: Wave-0 RED scaffold pins PKG-01..05 contracts as executable tests — build_release/launcher.swap/launcher.adapters imported INSIDE test bodies so collection stays green while execution is RED; minisign roundtrip + vendored-pubkey skip-gated (binary + app/minisign.pub absent). API surface fixed for Plans 02-05 (assemble_onedir/generate_iss/write_manifest/verify_manifest/assert_tag_matches_version/VENDORED_APP_ASSETS; swap.Paths/Pending/apply_update/parse_pending; adapters.backup_restore). parse_pending raises ValueError on both traversal and malformed markers.
- [Phase ?]: Phase 31-03: launcher is stdlib-only, imports no app.* (importing app would lock app\ and break the os.replace swap)
- [Phase ?]: Phase 31-03: swap is a pure callback-injected apply_update state machine; Windows side effects live in thin adapters (OS-agnostic unit-testable)
- [Phase ?]: Release Stage A uses automatic github.token (permissions: contents: write), never a configured repo secret — minisign secret key stays offline (T-31-02)
- [Phase ?]: CI release-verify added as a separate ubuntu-latest job so pg-parity is untouched; apt-installed minisign flips the round-trip test from skip to run
- [Phase ?]: 32-01: Wave-0 RED scaffold pins UpdateStatus state vocabulary (available/offline/noop/up_to_date) + the app.services.update / minisign_verify + launcher health_ok(expected_version) surfaces Waves 02-05 must satisfy; service imported in-body so collection stays green while execution is RED
- [Phase ?]: 32-02: cryptography (PyCA) 49.0.0 Ed25519 provider, human-approved supply-chain checkpoint (T-32-SC verified on pypi.org)
- [Phase ?]: 32-02: repo viktorplus/myorishop kept PUBLIC — unauthenticated /releases/latest works, no read-only GitHub token fallback provisioned into .env
- [Phase ?]: 32-02: only the PUBLIC key (app/minisign.pub, RW-prefixed) vendored; secret signing key stays offline, .gitignore blocks *.key (T-31-02/T-32-07)
- [Phase ?]: Update: trusted version read from Ed25519-verified manifest version=, never git tag_name (T-32-04)
- [Phase ?]: Update check: dialect no-op on non-sqlite + offline-safe never raises; __version__ kept at 1.15 as anti-downgrade baseline
- [Phase ?]: 32-05: #update-panel self-contained div swapped via hx-swap=outerHTML so the target id survives every swap (test_manual_check contract)
- [Phase ?]: 32-05: apply route echoes release notes from cached status so autoescaped notes render deterministically regardless of update.apply network outcome
- [Phase ?]: Plan 31-06: launcher boot() reuses the shipped adapters.migrate (migrate-then-start); a failed migration aborts the boot with SystemExit(1) so the app never serves an unmigrated schema
- [Phase 31]: Rollback is proportional: backup_restore fires only when the migration was attempted — A failure before the swap cannot have changed the schema; restoring an older DB there would discard operator writes made since the backup (T-31-06b)
- [Phase 31]: Every directory rename clears its destination first — Windows os.replace refuses an existing directory with WinError 5 even when it is empty (measured), so a stale app.prev/app.failed would otherwise block the swap or the rollback itself (T-31-06c)
- [Phase 31]: The pending marker is always consumed - quarantined to data/pending.failed.json on failure — A stuck marker made main()'s 2-second watch loop replay an unsatisfiable cycle and destroy the install (31-UAT GAP-3, T-31-04)
- [Phase 31]: 31-08: the launcher gets its OWN embeddable runtime in launcher\ (second extraction of the same SHA-256-verified zip, no second download); the .iss shortcut targets {app}\launcher\python.exe -m launcher, a file the installer actually ships. Its ._pth is exactly python313.zip / . / .. — a ._pth forces isolated mode (cwd and PYTHONPATH ignored) so only .. resolves the sibling package; Lib\site-packages and app are omitted to keep the launcher stdlib-only
- [Phase 31]: 31-08: no launcher.exe stub is built or promised anywhere (PyInstaller is rejected by CLAUDE.md); every path the generated .iss references is existence-asserted by test_iss_referenced_paths_exist_in_dist before the installer is compiled — a dead target in a user-writable per-user install root is a plant-and-hijack surface (T-31-08)
- [Phase ?]: 33-01 (D-01): the push schema comparison is ASYMMETRIC (client <= server), not exact-match — only a client AHEAD of the receiver is refused with 409, because that is the single direction in which merge._ledger_row loses a field behind a 200; a BEHIND client merges on purpose so the self-updating fleet is never cut off (clients check for updates once at startup).
- [Phase 33]: 33-01 (D-02/AP-5): push_schema_ok is a NEW sibling of current_schema_version in app/services/sync.py — app/services/offline.py::schema_version_ok is neither reused, imported nor modified (byte-unchanged; its result page is locked by 30-UI-SPEC).
- [Phase 33]: 33-01 (D-03): push_schema_ok's empty-string escape hatch is on BOTH sides, unlike offline.schema_version_ok's server-only hatch — every fixture builds its schema with Base.metadata.create_all, so current_schema_version returns "" on the client half too; a one-sided hatch would redden the shipped sync suite wholesale. Consequence: the gate's own tests MUST pin both revisions explicitly or every assertion is vacuous.
- [Phase 33]: 33-01 (D-04): push_schema_ok compares LEXICOGRAPHICALLY, sound only while every Alembic revision id stays fixed-width numeric; the docstring names tests/test_migrations.py::test_revision_ids_are_fixed_width (plan 33-03) as the tripwire — relax that test and this predicate must switch to a parsed comparison in the same commit.
- [Phase 33]: 33-01 (D-05): the 409 gate sits between parse_exchange and the owned transaction, reading the already-parsed batch.schema_version (two lines, vs the eight the bundle-upload path needs). Stated trade-off: a future NEW-KIND schema bump makes parse_exchange raise 400 MALFORMED_BATCH_ERROR first — a worse message but not a loss, since any non-2xx returns before the client's synced_at stamp.
- [Phase 33]: 33-01 (D-07): SYNC-11 needs a TEST, not code — synced_at is stamped only after raise_for_status() and last_sync_at advances only for ok/partial, so a 409 already leaves every client row re-pushable; test_refused_push_leaves_rows_unsynced drives a real client->server push over the ASGI bridge and pins it. Refused-client retry back-off (T-33-03) is deliberately deferred to plan 33-02.
- [Phase ?]: 33-02 (D-08): a 409 push refusal gets its own SyncResult status and one fixed RU sentence; #sync-badge is deliberately NOT suppressed, since its growing count is the pressure signal SYNC-11 guarantees is recoverable
- [Phase ?]: 33-02 (D-09): the auto-sync back-off to MAX_INTERVAL_SECONDS is derived from the already-persisted sync_state.last_status, so it needs no new column and self-clears on the first non-mismatch tick

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

- ⚠️ [v5.0 roadmap, 2026-09-04] **Nothing about the s1 server was verified by research** —
  no shell was run by any research agent. `V13` (is s1's `alembic_version` at `0026`?)
  and `V14` (what `display_tz` does s1's `.env.production` set? — it parameterises the
  backfill) must both be answered before Phase 33's rollout runbook is executable.
  Every count and `path:line` in the research documents is a snapshot at `b4ca98c`;
  re-measure at plan time rather than quoting them.

- ℹ️ [v5.0 roadmap, 2026-09-04] The 4 known-flaky `tests/test_sync_ui.py` failures are
  pre-existing (project memory, `sync_client._run_lock` held by the lifespan auto-sync
  thread) and must not be attributed to any phase of this milestone.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-2w6 | Replace Dictionary + CatalogPrice with a single-catalog-per-code import from oriflame_prices_with_calculations_fixed.xlsx (ДЦ->consultant_cents, ПЦ->consumer_cents) | 2026-07-14 | 3f0a7e3 | [260714-2w6-update-dictionary-pricelist](./quick/260714-2w6-update-dictionary-pricelist/) |
| 260714-fix | Catalog consumer price (ПЦ) now also autofills "Цена продажи" on product form and goods receipt (D-02 in receipts.py superseded); ДЦ still cost-only | 2026-07-14 | 53c3c92 | [260714-fix-catalog-sale-autofill](./quick/260714-fix-catalog-sale-autofill/) |
| 260714-o1z | Kill stale server on port 8000 in run.bat before starting a new one (fixes /dictionary 500 caused by an old process serving stale code) | 2026-07-14 | 5014787 | [260714-o1z-kill-stale-server-port](./quick/260714-o1z-kill-stale-server-port/) |
| 260720-wqc | Show read-only Категория column on /dictionary (Dictionary.rubric); autofill Product.category from rubric on product form's code lookup, independently of Название autofill | 2026-07-21 | 5faf403 | [260720-wqc-rubric](./quick/260720-wqc-rubric/) |
| 260721-doa | Add missing «Пользователи» link on /settings pointing to /settings/users (route/page existed since Phase 25 but was never linked in the nav) | 2026-07-21 | 1c56366 | [260721-doa-add-a-users-link-to-settings-page](./quick/260721-doa-add-a-users-link-to-settings-page/) |
| 260721-ebn | Fix dictionary pull crash: local/server Dictionary rows independently imported (different UUIDs per code) caused a UNIQUE(code) IntegrityError degrading sync to 'partial' forever; now partitions/upserts the dictionary pull kind by code, not id | 2026-07-21 | c195ad8 | [260721-ebn-fix-dictionary-pull-crashing-on-code-bas](./quick/260721-ebn-fix-dictionary-pull-crashing-on-code-bas/) |
| 260721-egc | Hide header «Синхронизировать» widget when sync_server_url is unconfigured (meaningless on the central server, which is never a sync client); give the top nav a dark server-mode style only when database_url resolves to PostgreSQL (the deployed server), so operators can't confuse it with a local SQLite client | 2026-07-21 | be59323 | [260721-egc-hide-header-sync-button-status-when-this](./quick/260721-egc-hide-header-sync-button-status-when-this/) |
| 260721-f39 | Add category filter dropdown to /products (converted free-text input to a <select> sourced from category_options) and /dictionary (brand-new filter <select> sourced from the fixed RUBRICS list, exact match on Dictionary.rubric) | 2026-07-21 | b9c3bdb | [260721-f39-add-category-filter-dropdown-to-products](./quick/260721-f39-add-category-filter-dropdown-to-products/) |
| 260721-fu0 | Add scripts/reset_business_data.py (dialect-aware wipe of products/customers/sales/operations/cash/batches only, typed-confirmation gated, no --force bypass, works on local SQLite and server PostgreSQL) and scripts/load_test_data.py (10 customers + exactly 10 operations of each of the 9 ledger types, service-layer only) | 2026-07-21 | 8061a99 | [260721-fu0-add-reset-business-data-and-load-test-da](./quick/260721-fu0-add-reset-business-data-and-load-test-da/) |
| 260721-oti | Merge 121 corrected product names from reports/dictionary_refresh_results.json into app/services/rubric_overrides.json (name field only, 1784 entries preserved, conf/rubric untouched); full-replace re-import applied locally (mismatch=0) and on s1 (git pull + docker compose up -d --build image rebuild + containerized import, since rubric_overrides.json is COPY-baked into the ori-app image, not volume-mounted) | 2026-07-21 | 5940b3f | [260721-oti-merge-121-dictionary-name-fixes-into-rub](./quick/260721-oti-merge-121-dictionary-name-fixes-into-rub/) |
| 260810-2g3 | Currency correctness part 2 (continues cdcec66): cash_movements.currency + batches.cost_cents (migrations 0024/0025/0026); per-currency balance/history/cash-flow/stock-valuation/sales-profit/dashboard behind a mandatory currency filter (never a cross-currency SUM); mixed-currency sale baskets rejected pre-write; cross-currency transfers require a destination-currency cost; «Валюта» column on CSV exports; legacy NULL-batch ledger rows bucket as RUB via the shared operation_currency_clause (outer join + COALESCE, never an inner join) | 2026-08-10 | bb0b759 | [260810-2g3-currency-correctness-part-2-per-currency](./quick/260810-2g3-currency-correctness-part-2-per-currency/) |
| 260813-ezt | Fix broken hx-vals tojson attributes in double-quoted HTML attrs: Jinja's `\|tojson` escapes `'` but not `"`, so the browser truncated `hx-vals` at the payload's first double quote — mobile batch cards fired batch-pick with an empty batch_id (sale/correction/write-off/transfer wizards could not select a batch at all, «Далее» stayed disabled); 5 attributes re-delimited to single quotes across 4 templates + 3 regression tests | 2026-08-13 | e574a00 | [260813-ezt-fix-broken-hx-vals-tojson-attributes-in-](./quick/260813-ezt-fix-broken-hx-vals-tojson-attributes-in-/) |
| 260813-i28 | Batch editing: new `update_batch` service (name/expiry/location/comment/price/cost, RU validation, empty->NULL, quantity/warehouse_id/product_id/is_legacy structurally excluded) + desktop `/batches/{id}/edit` and mobile `/m/batches/{id}/edit` routes, reachable from the desktop product batch table, desktop+mobile `/reports/expiry`, and mobile product detail; `?code=` prefill added to `/writeoff` + `/m/writeoff` (mirrors `/transfers`, already supported) | 2026-08-13 | 21cbbff | [260813-i28-batch-editing-edit-every-batch-field-exc](./quick/260813-i28-batch-editing-edit-every-batch-field-exc/) |
| 260813-l0y | Breadcrumbs + active-section nav: shared `partials/breadcrumbs.html` (last crumb non-link, `aria-current="page"`) and an object-identity line on the 4 desktop edit forms (batch/product/customer/warehouse) + the 2 mobile screens (batch edit, product detail, where the trail replaces the generic «← Главная»); one shared `nav_section()` prefix→section map in `app/routes/__init__.py` consumed by BOTH navs, so nested paths (`/batches/*`, `/receipts`, `/writeoff`, `/transfers`, `/corrections`, `/categories`, `/dictionary`, `/catalogs`, `/warehouses`, `/m/search/*`) keep their section highlighted instead of highlighting nothing | 2026-08-13 | 879a03e | [260813-l0y-breadcrumbs-on-edit-screens-active-secti](./quick/260813-l0y-breadcrumbs-on-edit-screens-active-secti/) |
| 260814-je0 | Backfill the dictionary from products it doesn't cover: new admin page `GET /dictionary/missing` (portable LEFT JOIN products→dictionary on code, active products with a non-empty code only, same filter/sort/paging idiom as `list_entries`) with a one-click «Добавить в справочник» per row (`POST /dictionary/missing/{id}/add`, row disappears on re-render), plus the same CTA on the desktop product edit card and the mobile product detail (`POST /dictionary/from-product/{id}`, shows «Есть в справочнике» once covered); both write paths funnel through one `add_entry_from_product` wrapper over `add_entry` — dictionary stays a helper table (D-24): no FK, no Product writes, no ledger; entry points added to both desktop and mobile «Справочники» toolbars | 2026-08-14 | 0ca3581 | [260814-je0-backfill-dictionary-from-products-missin](./quick/260814-je0-backfill-dictionary-from-products-missin/) |
| 260902-1d1 | Fill the 34 «НЕТ В СПРАВОЧНИКЕ» codes in the «Офис» inventory (43 rows in CSV + XLSX) — 19 names sourced from official Oriflame registration PDFs, 15 marked «Не опознан»; all 34 added to rubric_overrides.json and the master-pricelist importer now emits dictionary rows for override-only codes (catalogs=[], no CatalogPrice) with an additive --only-missing mode | 2026-09-01 | 8fa2c26 | [260902-1d1-fill-inventory-names-and-add-codes-to-di](./quick/260902-1d1-fill-inventory-names-and-add-codes-to-di/) |
| 260902-eyv | Import the «Офис» inventory as a receipt: scripts/import_inventory_receipt.py, dry-run by default, batch key = code + year-month + condition marker from the note, prices from catalog_prices or left NULL. Dry run on the empty local DB: 413 rows / 2204 units / 332 new products / 397 new batches / 16 in-file merges / 44 codes without price. NOT applied to s1 — the server dictionary is still the 6894-code master-pricelist subset, so 86 inventory codes have no dictionary row and 76 would lose a price they have locally | 2026-09-02 | 06a27e6 | [260902-eyv-import-office-inventory-receipt-into-s1](./quick/260902-eyv-import-office-inventory-receipt-into-s1/) |
| 260902-m9g | Import the whole price-list archive (118 .xls + 115 .xlsx) into catalog_prices, and remove the reason the archive and the master snapshot kept annihilating each other: BOTH importers used to DELETE the whole table, so whichever ran last won. Now a source owns only its own (year, number, code) triples via the existing UniqueConstraint — no whole-table delete survives anywhere — and an incoming NULL never overwrites a stored value (the master price list has no ББ column at all, so a naive upsert would have nulled 233 346 bonus points on its next run). catalog_prices 15 798 → 239 184 rows / 12 372 → 12 446 codes / 0 → 233 346 non-NULL points; 0 codes lost, 0 prices lost, 0 latest-issue regressions. Transport to s1 is now gzip: catalogs/catalog_prices.json.gz (4.8 MB) replaces catalog_prices.json (2.9 MB), proven a superset of it AND round-tripped at scale into an empty database before the old file was removed. Verified: 7/7 must-haves, price cells for issue 2025-01 render 3/3 real prices instead of «—» | 2026-09-02 | a12f211 | [260902-m9g-xls-xlsx-catalog-prices](./quick/260902-m9g-xls-xlsx-catalog-prices/) |
| 260902-tev | Fix the three BLOCKER findings of the 260902-m9g code review, on branch `fix/260902-import-blockers`, one revertible commit each. CR-01: `apply_master_import` wiped `dictionary` with no guard at all — a «Последний каталог» format drift would have deleted ~13 000 rows and put back only the override-only ones, with the statistics printed after the commit. Now `DictionaryReplaceRefused` fires inside the function (so direct callers are covered too) on an empty price list and on any shrink, the threshold is 0 % on purpose (clean install writes into an empty table, so the guard is silent there; it fires on a re-run against a loaded server, 12 582 → 6 856 = 45 %, which a 20 % tolerance would not have caught anyway), the refusal names both counts plus the `import_catalogs.py --only-missing` recovery step and `--force`, the skip statistics moved ahead of the write, and a VACUUM INTO snapshot is taken and printed before the first row is deleted (a printed no-op on PostgreSQL; a failed snapshot aborts the import). CR-02: `validate_records` checked 3 of the 7 export keys, so a float or a string in the shipped .gz reached the INTEGER money columns and `upsert_price_rows` overwrote correct values with it — all 7 are now enforced (`>= 0`, not `> 0`, so a stored zero survives a re-export). CR-03: three writers truncated their destination before the payload existed, and these files are accumulative — they hold rows in no database; one `atomic_write` (same-directory temp + `os.replace`) now serves all three, with the temp name keeping the destination suffix so the gzip branch of `_open_export` still applies. A fourth commit closes a gap the verifier found in the rollback promise itself: `create_backup` is `VACUUM INTO`, i.e. SQLite-only, so on the s1 PostgreSQL deployment it snapshotted NOTHING — `snapshot_dictionary()` now dumps the table through the existing `import_catalogs.export_dictionary()` into `backups/dictionary-*.json` with no dialect involved, and prints the restore command the refusal message already names. +26 tests; full suite 4 failed / 1450 passed / 13 skipped, the 4 being the known pre-existing `test_sync_ui.py` set. NOT merged into main | 2026-09-02 | 352f51a | [260902-tev-fix-the-three-code-review-blockers-in-th](./quick/260902-tev-fix-the-three-code-review-blockers-in-th/) |
| 260903-31d | Publish the 2026-09-03 «Офис» goods-receipt report on the app's own domain, because claude.ai is unreachable from Russia: a fourth page in the existing `app/routes/public_pages.py` mechanism — static `FileResponse`, no DB query, no query parameters — at `/code/artifact/143c5a2c-d93f-4361-ae44-0059c828962a`, the same path the artifact has on claude.ai, plus that exact path in `PUBLIC_PATHS`. The HTML body is a byte-identical copy of the artifact (proven by `cmp` on the 29 512-byte payload); unlike the three neighbouring pages the wrapper deliberately sets NO `color-scheme:light`, background or font on `body`, because this page ships its own light and dark token sets — two new tests in `tests/test_public_page.py` pin that, so a future copy-paste of the neighbours' light header fails loudly. Version 1.55 → 1.56 | 2026-09-03 | 1d5331f | [260903-31d-publish-office-receipt-report-on-own-dom](./quick/260903-31d-publish-office-receipt-report-on-own-dom/) |

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
| uat_gap | Phase 31: 31-UAT.md — 2 pending scenarios, both human-only: (1) install `dist\Output\MyOriShop-Setup-1.60.exe` on a bare Windows machine, (2) the first real tag-triggered signed release. Neither is a code defect; see `31-VERIFICATION.md` → `## Acknowledged Gaps` | partial | 2026-09-03 (v4.0 close) |
| uat_gap | Phase 31: 31-UAT-STEPS.md — manual step script, no status marker (parsed as `unknown`); superseded by 31-UAT.md | unknown | 2026-09-03 (v4.0 close) |
| uat_gap | Phase 28: 28-UAT.md — status `passed` with 0 pending scenarios; flagged only by the audit parser, no real gap | passed | 2026-09-03 (v4.0 close) |
| verification_gap | Phase 25: 25-VERIFICATION.md — `human_needed` | human_needed | 2026-09-03 (v4.0 close) |
| verification_gap | Phase 26: 26-VERIFICATION.md — `human_needed` | human_needed | 2026-09-03 (v4.0 close) |
| debug | finance-report-nav-entry-missing — hypothesis CONFIRMED, session never marked resolved | diagnosed | 2026-09-03 (v4.0 close) |
| debug | history-return-button-and-code-column — hypothesis CONFIRMED, session never marked resolved | diagnosed | 2026-09-03 (v4.0 close) |
| debug | receipt-batch-chooser-ux — hypothesis CONFIRMED (three root causes), session never marked resolved | diagnosed | 2026-09-03 (v4.0 close) |
| debug | sale-batch-picker-not-submitted — hypothesis CONFIRMED, investigation complete for goal=find_root_cause_only | diagnosed | 2026-09-03 (v4.0 close) |
| todo | `2026-08-31-price-lists-backfill.md` — докачать недостающие прайс-листы и пополнить справочник | pending | 2026-09-03 (v4.0 close) |
| quick_task | 17 quick tasks carry no completion marker and parse as `unknown`: 260714-2w6, 260720-wqc, 260721-doa, 260721-ebn, 260721-egc, 260721-f39, 260721-fu0, 260721-oti, 260813-ezt, 260813-i28, 260813-l0y, 260814-je0, 260902-eyv, 260902-g1q, 260902-m9g, 260902-tev, 260903-31d. Their full records (description, date, commit, directory) are in the quick-task table above in this file — most shipped and were simply never status-stamped | unknown | 2026-09-03 (v4.0 close) |

Re-generate this list any time with `node ~/.claude/gsd-core/bin/gsd-tools.cjs query audit-open`.

## Session Continuity

Last session: 2026-09-04T09:32:26.430Z
Stopped at: Completed 33-02-PLAN.md (SYNC-10 client half: schema_mismatch status + D-09 back-off)
Resume file: None

## Operator Next Steps

- **Next: `/gsd-plan-phase 33`** (Back-Dated Operations). Phase 33 does **not** need `--research-phase`; Phase 34 does; Phase 35 does not.
- **Before Phase 33's rollout runbook is executable**, answer the two server questions no research agent could (`V13`: is s1's `alembic_version` at `0026`? `V14`: what `display_tz` does s1's `.env.production` set — it parameterises the backfill). Re-measure the research documents' counts at plan time; every one is a snapshot at `b4ca98c`.
- **Before v4.0 can honestly be called shipped to an operator:** run `dist\Output\MyOriShop-Setup-1.60.exe` on a bare Windows machine, then cut the first real signed release by pushing a `v1.<N>` tag and following the offline-signing runbook. Both are the two acknowledged Phase-31 gaps; nothing in code blocks them. Unaffected by v5.0.
- **v3.0 was never archived** — there is no `.planning/milestones/v3.0-ROADMAP.md` and no v3.0 entry in MILESTONES.md, even though phases 25-30 are all complete. Run `/gsd-complete-milestone` for v3.0 retroactively if that history matters.
- Still-open hygiene, non-blocking: no SECURITY.md for phases 29 and 30; `25-VERIFICATION.md` and `26-VERIFICATION.md` are `human_needed`; 4 debug sessions sit at `diagnosed` without a resolution stamp. Full list in `## Deferred Items`.
