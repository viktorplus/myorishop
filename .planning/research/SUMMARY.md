# Project Research Summary

**Project:** MyOriShop — Oriflame Warehouse Inventory
**Domain:** Local-first SQLite app gaining multi-operator sync (online + offline USB), a central PostgreSQL server, and mandatory auth with admin/operator roles (v3.0)
**Researched:** 2026-07-18
**Confidence:** HIGH

## Executive Summary

MyOriShop v3.0 is not a green-field sync project — it is the moment the app *activates* machinery that was deliberately seeded since v1.0. The `operations` and `cash_movements` tables are already append-only ledgers with UUID4 PKs, per-device `seq`, a `UNIQUE(device_id, seq)` guard, an unused `synced_at` cursor column, and UPDATE/DELETE-blocking triggers whose own code comment anticipates "the v2 sync milestone relaxes the UPDATE trigger." All four researchers independently reached the same conclusion: because ledger rows are immutable and globally UUID-keyed, **sync is a set-union-by-UUID plus a `rebuild_stock()` recompute — no CRDT, no conflict-resolution UI, no last-write-wins on operational data, and no background-job infrastructure (Kafka/Celery/Redis) whatsoever.** The stated hard problem of most sync projects is deleted by the existing architecture.

The recommended approach is therefore small and surgical. A **separate, idempotent, verbatim merge path** (`ingest_batch`, INSERT-if-absent by UUID) must be built — synced rows must NOT be routed through `record_operation()`, which re-stamps `device_id`/`seq`, runs the IN-01 deleted-product guard, and increments caches non-idempotently. **One serialization format (NDJSON) serves both online HTTP and offline USB** — the transports are two thin callers of the same pure serialize/ingest core. Auth is the app's first-ever security boundary and must cover **two mirrored route trees** (desktop and mobile `/m/`) plus the high-value `export`/`backup` endpoints, enforced as a global default with a router-enumeration test. The new stack additions are minimal and version-verified: `psycopg` 3 (server only), `pwdlib[argon2]` (NOT passlib — its `crypt` dependency was removed in Python 3.13), Starlette `SessionMiddleware` + `itsdangerous`, and sync `httpx`.

The genuinely hard, under-appreciated risk is **mutable master-data conflict** — products, customers, warehouses, batches, dictionaries — which the append-only story does *not* cover. Two devices independently creating the same `Product.code` will violate the `uq_products_code_active` partial unique index on first sync, and naive "last-write-wins by client `updated_at`" is unreliable because client wall-clocks drift. This needs an explicit product decision (server-authoritative vs. LWW-by-server-timestamp) and is the top open decision for the roadmapper to surface. Secondary risks are all preventable with discipline: never ship the derived stock/batch caches; relax the append-only trigger only column-scoped to `synced_at`; give every install a unique `device_id`; and stand up real PostgreSQL in CI early to catch SQLite-permissiveness traps (batch-mode migrations, Cyrillic case-folding shadow columns).

## Key Findings

### Recommended Stack

The v1/v2 stack (Python 3.13, FastAPI 0.139, SQLAlchemy 2.0 sync, SQLite+WAL, HTMX 2.0.10 vendored, Jinja2, Alembic, uv, Ruff) is settled and unchanged. v3.0 adds only what sync + auth + a server require, and the existing models are already dialect-portable (String UUIDs, integer cents, TEXT timestamps, partial indexes carrying both `sqlite_where` and `postgresql_where`). One model set and one Alembic history serve both dialects; `render_as_batch` and trigger DDL become dialect-gated.

**Core technologies (new for v3.0):**
- **psycopg 3 (3.3.4, `postgresql+psycopg://`)**: PostgreSQL driver for the server engine — server-only optional dependency group; clients keep SQLite. Native SQLAlchemy 2.0 dialect.
- **pwdlib[argon2] (0.3.0 + argon2-cffi 25.1.0)**: password hashing (Argon2id, OWASP first choice) — explicitly chosen over passlib, which is unmaintained and depends on the stdlib `crypt` module removed in Python 3.13 (PEP 594).
- **Starlette SessionMiddleware + itsdangerous 2.2.0**: signed-cookie login session — already in the tree via FastAPI; stateless, no session table. Declare `itsdangerous` explicitly (middleware asserts it at startup).
- **httpx 0.28.1 (sync `httpx.Client`)**: client→server push/pull transport — promote from dev-only TestClient to a runtime dependency; sync matches the all-sync codebase.
- **stdlib `json` → NDJSON + pydantic `SyncEnvelope`**: one serialization format for BOTH online HTTP body and offline USB file — no marshmallow, no custom binary format.

### Expected Features

The milestone splits cleanly into Auth/Roles/Attribution and Sync (online + USB), on top of the fixed v1/v2 foundation. Multi-currency is explicitly out of scope.

**Must have (table stakes):**
- Login/logout + Argon2 hashing + signed session; first-run admin bootstrap (no shipped default credentials).
- Admin user management (create / assign role / deactivate — never delete / reset password); two fixed roles (administrator, operator).
- Server-side route guards on every protected route (the real boundary) PLUS role-based menu hiding (cosmetic) — both, guards non-optional.
- Real `created_by` = logged-in user, stamped at the single `record_operation()` choke point; operator column in History.
- Single versioned exchange format + idempotent UUID merge + `rebuild_stock()` recompute; USB export/import; online push/pull with manual «Синхронизировать» button, status, last-sync time, plain-language result.
- Offline-safe failure (sync error never blocks local work); mobile parity for login and sync trigger.

**Should have (competitive):**
- "What will change" dry-run preview before applying a USB import (undo-anxiety killer).
- Unsynced-count badge; optional automatic/interval background sync (opt-in, degrades silently offline).
- Filter Reports (not just History) by operator; USB exchange integrity/version check.

**Defer (v3.x / v4+):**
- Third "report-viewer" role (deferred AUTH-V2-01); optional idle session timeout/auto-lock; multi-currency (out of scope).

**Do NOT build (anti-features):** interactive per-row conflict-resolution UI, real-time/continuous multi-master sync, syncing stock quantities directly, password policies/rotation/lockout/2FA/email reset, self-service registration, dynamic permission matrix/custom roles, hard-deleting users, selective/partial sync, aggressive idle timeout.

### Architecture Approach

Two-tier replication over one model set. **Tier A (append-only ledgers: `operations`, `cash_movements`)** replicates by log-shipping + idempotent verbatim replay keyed by UUID — nothing to reconcile because rows never change. **Tier B (mutable reference rows: products, customers, warehouses, batches, dictionaries)** replicates by last-write-wins on a *server-authoritative* version/timestamp, with soft-delete tombstones. The derived caches (`Product.quantity`, `Batch.quantity`) are never shipped — they are recomputed by `rebuild_stock()` after every merge. The `sync/` package is transport-agnostic by construction: pure `serialize.py` + `ingest.py` + `collect.py`, with `client.py` (HTTP) and `usb.py` (file) as thin callers, so "USB reuses the online format" is true by design, not discipline.

**Major components:**
1. `ingest_batch()` (NEW) — verbatim replay + dedup-by-UUID + FK-ordered insert; a *separate* write path from `record_operation()`.
2. `record_operation()` (MODIFIED) — now stamps `user_id` from the authenticated session instead of `settings.operator_name`; `device_id` still from per-install config.
3. Auth layer (NEW) — `SessionMiddleware` + `require_user`/`require_admin` router-level dependencies applied across both desktop and mobile trees; `users` table (UUID PK, login, password_hash, role).
4. Sync client + server API (NEW) — `/sync/push`, `/sync/pull` with per-device token; watermark/cursor tracking (`synced_at` push high-water, `sync_state` pull-per-device).
5. `rebuild_stock()` (REUSED) — the correctness backstop; asserts the stock invariant after every merge.
6. One Alembic history / two dialects (MODIFIED) — dialect-gated `render_as_batch` and trigger DDL; PG engine builder without the SQLite PRAGMA listener.

### Critical Pitfalls

1. **Replaying synced rows through `record_operation()`** — double-counts stock, mints new IDs (defeats dedup), destroys origin device/author. Build a dedicated verbatim `ingest_batch()`; never reuse `record_operation()` for merge.
2. **Mutable master-data conflict (top open decision)** — `Product.code` collisions violate `uq_products_code_active` on first multi-device sync; the append-only story does nothing here. Decide server-authoritative vs. server-timestamp LWW per table, with a defined `code`-collision rule, BEFORE writing merge code.
3. **Static `device_id="device-01"` / `created_by="operator"`** — every unmodified install collides on `UNIQUE(device_id, seq)` at first sync. Generate a persistent unique `device_id` (UUID) at first run; take `created_by` from the session user.
4. **Auth gating only the desktop tree** — the mirrored `/m/` mobile routers plus `export`/`backup` stay public (role escalation, full-dataset exfiltration). Enforce a global-default gate and a test that enumerates every router in `main.py`.
5. **Over-broad append-only trigger relaxation** — dropping the trigger to write `synced_at` reopens the ledger to tampering. Use a column-scoped `WHEN` clause (only `synced_at` NULL→value), mirrored on PostgreSQL, with a test proving `qty_delta`/`amount_cents` updates still ABORT. Never ship the derived caches; recompute via `rebuild_stock()`. Don't trust client wall-clocks for ordering — use `(device_id, seq)`.

## Implications for Roadmap

Based on combined research, six dependency-ordered phases. **Reconciling the build-order tension:** ARCHITECTURE recommends Auth first (identity unblocks attribution, fully testable on one SQLite client before any server exists); PITFALLS emphasizes the shared merge engine as the highest-risk artifact and pushes device-identity + merge-engine to the front. Both agree on the load-bearing constraint — **the shared idempotent merge engine must be built and hardened in isolation before either transport.** The reconciliation: Auth and device-identity are *independent* of the merge engine, cheap, and locally testable, so they come first and unblock correct attribution that the merge core will carry verbatim; PostgreSQL portability is proven next (the server cannot exist until the one model set provably runs on PG); then the merge core is built and hardened as pure functions with no transport; only then do the server API and the two transports layer on. This satisfies both researchers: identity-first (Architecture) AND engine-before-transports with device-identity done up front (Pitfalls).

### Phase 1: Auth, Roles & Identity Foundation
**Rationale:** First security boundary and the identity every downstream row is attributed to; fully testable on one SQLite client before any server. Device identity is fixed here because Pitfall 3 is a pre-flight for all sync.
**Delivers:** `users` table; Argon2 hashing; `/login` + `SessionMiddleware` + session rotation + CSRF on HTMX POSTs; `require_user`/`require_admin` classified across every desktop AND mobile router (+ `export`/`backup` admin-gated); first-run admin bootstrap; per-install unique `device_id`; `user_id` added to `operations`/`cash_movements`/`sales` and threaded through `record_operation()`.
**Addresses:** login/logout, bootstrap, user CRUD, two roles + guards, real `created_by`, operator column in History.
**Avoids:** P3 (static device_id/created_by), P9 (unguarded mobile/export/backup), P10 (password/session/CSRF).

### Phase 2: PostgreSQL Portability
**Rationale:** The server cannot exist until one model set + one Alembic history provably runs on PostgreSQL. No sync logic yet.
**Delivers:** Dialect-conditional `render_as_batch`; dialect-branched append-only trigger DDL (plpgsql `RAISE EXCEPTION`); dialect-guarded connect-event PRAGMAs; PG engine builder (`postgresql+psycopg://`); `psycopg[binary]` server-only group; real Postgres in CI running the full Alembic history + Cyrillic search parity tests.
**Uses:** psycopg 3, dialect-gated Alembic env.py.
**Avoids:** P11 (SQLite→Postgres portability traps found only on a live server).

### Phase 3: Shared Merge Core (highest-risk artifact)
**Rationale:** The single implementation both transports depend on — build and harden in isolation as pure functions, no HTTP, no file I/O. This is where the milestone's correctness lives.
**Delivers:** NDJSON `SyncEnvelope` format; `serialize.py`/`collect.py`; `ingest_batch()` verbatim replay + UUID dedup + FK-ordered insert covering BOTH ledgers atomically; `rebuild_stock()` after merge; `sale_id` reconciliation check; the explicit **mutable-master-data conflict policy** (Tier-B LWW by server-authoritative timestamp + `Product.code` collision rule + soft-delete tombstones).
**Implements:** Tier-A/Tier-B two-tier replication; verbatim-ingest-is-separate-path pattern.
**Avoids:** P1 (replay via record_operation), P2 (caches not recomputed), P4 (dual-ledger inconsistency), P6 (mutable master conflicts), P7 (clock trust).

### Phase 4: Server Sync API + Trigger Relaxation
**Rationale:** Needs the merge core (3) and identity/token (1). Wires the shared core to HTTP endpoints.
**Delivers:** `/sync/push` (ingest + ack watermark), `/sync/pull` (other-device rows since watermark), per-device token auth; the column-scoped append-only UPDATE-trigger relaxation migration (SQLite + PG, `synced_at`-only); client `sync_state` cursor table.
**Avoids:** P8 (over-broad trigger relaxation).

### Phase 5: Online Client Sync
**Rationale:** Wires the client to the API from (4).
**Delivers:** `sync/client.py` collect→push→stamp `synced_at`, watermark→pull→ingest→recompute; manual «Синхронизировать» button + status/last-sync/result UI (desktop + mobile parity); offline-safe failure handling; idempotent retry after dropped connections.
**Addresses:** manual sync button, status, last-sync time, plain-language result, offline-safe failure.

### Phase 6: Offline USB Sync
**Rationale:** Pure reuse of the core (3) — smallest increment, built last because the format and watermark semantics must be final. Depends on nothing new except file plumbing (reuse VACUUM-INTO mechanics).
**Delivers:** `sync/usb.py` export/import of the same NDJSON envelope through the same `ingest_batch()`; single all-or-nothing import transaction; schema-version header + integrity checksum/signed manifest + re-run write-path validations; optional "what will change" dry-run preview.
**Avoids:** P5 (partial USB apply), P12 (untrusted exchange file).

### Phase Ordering Rationale
- **Dependencies:** identity (1) → PG proof (2) → shared core (3) → API needs core+identity (4) → online needs API (5) → USB reuses core (6). Each phase's prerequisites are fully satisfied by earlier ones.
- **Architecture grouping:** the transport-agnostic `sync/` core is deliberately isolated in Phase 3 so both transports (5, 6) are thin callers — one merge algorithm, never two.
- **Pitfall avoidance:** device-identity and auth-coverage are front-loaded (pre-flights for everything); the riskiest code (merge engine) is hardened alone before any transport; USB (highest-risk transport, untrusted input) ships last on a proven engine.

### Research Flags

Phases likely needing `--research-phase` during planning:
- **Phase 3 (Shared Merge Core):** the mutable master-data conflict policy is the top open decision — needs a concrete per-table resolution rule and `Product.code` collision handling before implementation. Highest design uncertainty in the milestone.
- **Phase 6 (Offline USB Sync):** exchange-file trust model (signed manifest vs. checksum-only), schema-version compatibility rule, and re-running write-path validations on the bulk path warrant a focused pass.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Auth):** well-documented — Starlette SessionMiddleware + pwdlib + router dependencies are established; the work is classification + coverage tests, not novel design.
- **Phase 2 (PG portability):** mechanical — dialect gating in Alembic/db.py; the models are already portable.
- **Phase 4 / Phase 5:** standard request/response wiring once the core exists.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI JSON on 2026-07-18; passlib-vs-pwdlib rationale (PEP 594) verified. |
| Features | MEDIUM-HIGH | Web-informed UX best practices + established auth/RBAC/local-first patterns; no exotic libraries; foundation facts codebase-grounded (HIGH). |
| Architecture | HIGH | Grounded directly in the current codebase — the sync foundation (UUID PKs, `device_id`/`seq`, `synced_at`, append-only triggers) was seeded deliberately since v1.0. |
| Pitfalls | HIGH (codebase) / MEDIUM (sync-design consensus) | Tied to this app's real structures; sync-design recommendations are practitioner consensus. |

**Overall confidence:** HIGH

### Gaps to Address
- **Mutable master-data conflict policy (top gap):** must be decided explicitly in Phase 3 — server-authoritative vs. server-timestamp LWW per Tier-B table, plus a concrete `Product.code` cross-device collision rule (reject/rename loser vs. globally coordinated codes) and soft-delete tombstone propagation. Do NOT event-source Tier-B now (YAGNI); note the latent upgrade path.
- **USB exchange-file trust model:** signed manifest vs. checksum-only, and how to bind claimed `created_by`/`device_id` to a trusted origin when there is no authenticating server in the loop — resolve during Phase 6 planning.
- **Collect vs. full-snapshot for Tier-B:** whether to walk referenced entities (`collect.py`) or ship full Tier-B snapshots per sync (cheap at this data scale). Decide in Phase 3; snapshot is the simpler fallback.
- **CSRF mechanism for the all-HTMX UI:** per-session token via `hx-headers` vs. hidden field — pin during Phase 1.

## Sources

### Primary (HIGH confidence)
- Codebase — `app/models.py` (UUID PKs, `device_id`/`seq` UNIQUE, `synced_at`, portable partial indexes, integer cents), `app/db.py:16-21` (APPEND_ONLY_TRIGGERS + "v2 sync relaxes UPDATE trigger" note), `app/services/ledger.py` (`record_operation`, `next_seq`, `rebuild_stock`, IN-01 guard), `app/main.py` (~40 routers, desktop + mobile trees, no auth), `app/config.py` (static `device_id`/`operator_name`), `alembic/env.py` (`render_as_batch=True`).
- PyPI JSON (verified 2026-07-18) — psycopg 3.3.4, pwdlib 0.3.0, argon2-cffi 25.1.0, itsdangerous 2.2.0, httpx 0.28.1, bcrypt 5.0.0, passlib 1.7.4 (unmaintained since 2020).
- `.planning/PROJECT.md` — v3.0 scope, admin/operator split, append-only-ledger sync decisions (D-05..D-11); `CLAUDE.md` Stack Patterns by Variant.
- PEP 594 (removal of `crypt` in Python 3.13); OWASP Password Storage (Argon2id first choice).

### Secondary (MEDIUM confidence)
- Local-first / offline-first sync UX sources (manual trigger, status badges, last-sync, non-technical conflict handling) — Medium (J. Topic), DEV, Evil Martians, Hasura, daily.dev.
- Practitioner consensus — idempotent-merge-by-UUID, delta-sync cursor, server-authoritative vs. client-clock LWW, OWASP session-fixation/CSRF guidance.

### Tertiary (LOW confidence)
- None — all findings trace to verified versions, the live codebase, or multi-source consensus.

---
*Research completed: 2026-07-18*
*Ready for roadmap: yes*
