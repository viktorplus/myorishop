# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- ✅ **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (shipped 2026-07-13)
- ✅ **v1.2 Catalog Pricing UX & List Ergonomics** — Phases 12-14 (shipped 2026-07-14)
- ✅ **v1.3 Финансы / Касса** — Phases 15-17 (shipped 2026-07-15)
- ✅ **v2.0 UX Overhaul & Navigation Restructure** — Phases 18-24 (shipped 2026-07-17)
- 🚧 **v3.0 Multi-Operator Sync, Central Server & Roles** — Phases 25-30 (in progress)
- ✅ **v4.0 Distribution & Delivery** — Phases 31-32 (shipped 2026-09-03)
- 🚧 **v5.0 Corrections, Dates & Currency** — Phases 33-35 (in progress)

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order. Phase numbering is continuous across milestones (never restarts at 1).

<details>
<summary>✅ v1.0 MVP (Phases 1-6) — SHIPPED 2026-07-10</summary>

- [x] Phase 1: Foundation & Ledger Core (3/3 plans) — completed 2026-07-08
- [x] Phase 2: Catalog, Dictionary & Search (4/4 plans) — completed 2026-07-08
- [x] Phase 3: Goods Receipt & Backup (3/3 plans) — completed 2026-07-09
- [x] Phase 4: Sales & Customers (6/6 plans) — completed 2026-07-09
- [x] Phase 5: Stock Operations & History (9/9 plans) — completed 2026-07-10
- [x] Phase 6: Reports & Data Export (6/6 plans) — completed 2026-07-10

Full phase details archived in `.planning/milestones/v1.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.1 Multi-Warehouse & Batch Tracking (Phases 7-11) — SHIPPED 2026-07-13</summary>

- [x] Phase 7: Category Browsing & Minimum Price Guardrail (4/4 plans) — completed 2026-07-10
- [x] Phase 8: Warehouses (2/2 plans) — completed 2026-07-11
- [x] Phase 9: Batch Tracking & Ledger Integration (9/9 plans) — completed 2026-07-12
- [x] Phase 10: Warehouse Transfers & Expiry Reporting (3/3 plans) — completed 2026-07-12
- [x] Phase 11: Dedicated Mobile Flow (10/10 plans) — completed 2026-07-13

Full phase details archived in `.planning/milestones/v1.1-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.2 Catalog Pricing UX & List Ergonomics (Phases 12-14) — SHIPPED 2026-07-14</summary>

- [x] Phase 12: Code & Name Autofill (4/4 plans) — completed 2026-07-13
- [x] Phase 13: Mobile Wizard Context & Navigation (6/6 plans) — completed 2026-07-14
- [x] Phase 14: List Pagination, Filtering, Sorting & Quick Delete (7/7 plans) — completed 2026-07-14

Full phase details archived in `.planning/milestones/v1.2-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.3 Финансы / Касса (Phases 15-17) — SHIPPED 2026-07-15</summary>

- [x] Phase 15: Cash Ledger Foundation (4/4 plans) — completed 2026-07-14
- [x] Phase 16: Manual Cash Movements & History (4/4 plans) — completed 2026-07-15
- [x] Phase 17: Financial Reports, Export & Dashboard Analytics (5/5 plans) — completed 2026-07-15

Full phase details archived in `.planning/milestones/v1.3-ROADMAP.md`.

</details>

<details>
<summary>✅ v2.0 UX Overhaul & Navigation Restructure (Phases 18-24) — SHIPPED 2026-07-17</summary>

- [x] Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) (8/8 plans) — completed 2026-07-16
- [x] Phase 19: Products Page Rebuild (1/1 plan) — completed 2026-07-16
- [x] Phase 20: Warehouses & Batch-Split Transfers (7/7 plans) — completed 2026-07-16
- [x] Phase 21: Customer Profiles & Purchase Insights (5/5 plans) — completed 2026-07-17
- [x] Phase 22: Sales Page Rebuild (7/7 plans) — completed 2026-07-17
- [x] Phase 23: Dashboard & History Rebuild (7/7 plans) — completed 2026-07-17
- [x] Phase 24: Navigation Restructure & Settings (6/6 plans) — completed 2026-07-17

Full phase details archived in `.planning/milestones/v2.0-ROADMAP.md`.

</details>

### 🚧 v3.0 Multi-Operator Sync, Central Server & Roles (In Progress)

**Milestone Goal:** Turn the single-operator local app into a multi-operator system built around a central PostgreSQL server. The server hosts two online interfaces (browser + mobile — mobile is server-only). A local desktop client keeps working offline on SQLite and syncs online when internet is available; when it isn't, work accumulates and rides a USB flash drive as a single self-contained file that uploads itself to the server from any internet computer with no app installed. Everything is gated behind mandatory login with an administrator/operator split.

**Build order (dependency-ordered):** identity/auth first (locally testable, unblocks attribution) → prove one model set on PostgreSQL → harden the shared merge engine in isolation → stand up the server + sync API → wire online client sync → ship the offline self-uploading file last, reusing the proven engine.

- [x] **Phase 25: Authentication, Roles & User Attribution** - Mandatory login over the whole app (desktop + mobile + export/backup), two roles, user management, and per-user attribution of every operation (completed 2026-07-18)
- [x] **Phase 26: PostgreSQL Portability & Append-Only Parity** - One model set and one Alembic history proven to run on PostgreSQL with the same append-only ledger guarantee (completed 2026-07-18)
- [x] **Phase 27: Shared Idempotent Merge Core** - The single server-side merge engine and exchange format: UUID-idempotent ledger replay, post-merge recompute, and server-authoritative reference-data conflict policy, proven portable on SQLite + PostgreSQL in CI (completed 2026-07-19)
- [x] **Phase 28: Central Server — Hosting & Sync API** - The VPS PostgreSQL server hosting both online interfaces plus token-authenticated push/pull sync endpoints and the column-scoped trigger relaxation (completed 2026-07-19)
- [x] **Phase 29: Online Client Sync** - «Синхронизировать» push/pull, sync status + last-sync time, unsynced-count badge, optional interval sync, offline-safe failure (completed 2026-07-20)
- [x] **Phase 30: Offline Self-Uploading File** - Upload-only USB path: export not-yet-uploaded work to a self-contained file that authenticates, previews, and uploads itself through the same merge engine (completed 2026-07-20)

#### Phase 25: Authentication, Roles & User Attribution

**Goal**: Add the app's first security boundary — mandatory login gates every desktop and mobile route (plus export/backup), users have a profile and one of two roles, and every operation and cash movement is attributed to the logged-in user. Fully testable on one SQLite client before any server exists. Also fixes device identity (per-install unique `device_id`) as a pre-flight for all later sync.
**Depends on**: Phase 24 (previous milestone; first phase of v3.0)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, USER-01, USER-02, USER-03, USER-04, USER-05, USER-06, ROLE-01, ROLE-02, ROLE-03, ROLE-04, RPT-01
**Success Criteria** (what must be TRUE):

  1. On first run with no users, the app guides creation of an initial administrator (no default credentials shipped); thereafter every desktop and mobile page — plus the `export` and `backup` endpoints — requires login, enforced by a server-side guard on every router, and redirects unauthenticated visitors to the login screen. (AUTH-01, AUTH-04, ROLE-02)
  2. A user can log in with login + password (stored only as Argon2id hashes), stay logged in across a browser refresh via a signed cookie, and log out to end the session; state-changing HTMX POST forms are protected against CSRF. (AUTH-02, AUTH-03, AUTH-05)
  3. An administrator can create a user with a display name/login/role, deactivate a user (soft-disable) without deleting them, and reset another user's password; a deactivated user can no longer log in but their past operations stay attributed; exactly two roles exist (administrator, operator). (USER-01, USER-02, USER-03, USER-04, ROLE-01)
  4. An operator can perform receipts, sales, write-offs/returns/corrections, and cash movements, but administrator-only sections (user management, warehouses, dictionaries, settings) are both hidden and server-side-blocked; an administrator has full access to everything plus every operator action. (ROLE-03, ROLE-04)
  5. Every operation and cash movement records the logged-in user as its author at the single `record_operation()` write path, and both the History page and period Reports show the operating user and can be filtered by user. (USER-05, USER-06, RPT-01)

**Plans**: 8 plans (5 waves)

- [x] 25-01-PLAN.md — Dependencies (argon2-cffi/itsdangerous), persisted secret_key, per-install device_id (wave 1)
- [x] 25-02-PLAN.md — Data layer: User model, author_id columns, ROLES, migration 0017 + trigger-survival regression (wave 1)
- [x] 25-03-PLAN.md — Auth/user/security services: Argon2id hashing, user CRUD, guard/require_role/contextvars/CSRF core (wave 2)
- [x] 25-04-PLAN.md — Flip auth on: SessionMiddleware + app-level guard + login/logout/setup + authenticated conftest fixture (wave 3)
- [x] 25-05-PLAN.md — Admin role gating (require_role on admin routers) + user-management page /settings/users (wave 4)
- [x] 25-06-PLAN.md — Chrome: CSRF hx-headers + logout control + role-conditioned menu-hide (desktop + mobile) (wave 4)
- [x] 25-07-PLAN.md — Attribution at both write paths + contextvars threadpool-propagation proof (wave 4)
- [x] 25-08-PLAN.md — History + Reports author display & «Пользователь» filter (wave 5)

**UI hint**: yes

#### Phase 26: PostgreSQL Portability & Append-Only Parity

**Goal**: Prove the server's database layer before any server exists — the identical data models and the single Alembic migration history run unchanged on PostgreSQL, and PostgreSQL enforces the same append-only ledger guarantee as the SQLite client. Mechanical dialect-gating work (conditional `render_as_batch`, dialect-branched trigger DDL, dialect-guarded connect-event PRAGMAs, a `postgresql+psycopg://` engine builder) with a real Postgres instance in CI. No sync logic yet.
**Depends on**: Phase 25
**Requirements**: SRV-01, SRV-02
**Success Criteria** (what must be TRUE):

  1. The full Alembic migration history applies cleanly against an empty PostgreSQL database in CI, producing the same schema the SQLite client uses from the same single history. (SRV-01)
  2. Cyrillic case-insensitive search returns identical results on PostgreSQL and SQLite (the shadow-column approach holds uniformly on both dialects). (SRV-01)
  3. On PostgreSQL, any attempt to UPDATE or DELETE a row in `operations` or `cash_movements` is rejected at the database, exactly as on SQLite. (SRV-02)

**Plans**: 3 plans (2 waves)

- [x] 26-01-PLAN.md — psycopg dependency + `settings.database_url` single source of truth + PG-parity test scaffold (wave 1)
- [x] 26-02-PLAN.md — Dialect-branch append-only trigger DDL in frozen migrations 0001 + 0013 (wave 1)
- [x] 26-03-PLAN.md — Dialect-gate engine (app/db.py) + Alembic env + GitHub Actions CI with postgres:17 (wave 2)

#### Phase 27: Shared Idempotent Merge Core

**Goal**: Build and harden the milestone's highest-risk artifact in isolation — one shared NDJSON exchange format and one server-side merge engine, as pure functions with no HTTP and no file I/O. It replays both append-only ledgers verbatim and idempotently by UUID, recomputes derived stock and cash after every merge, and resolves mutable reference-data conflicts server-authoritatively. This is where the milestone's correctness lives; both later transports are thin callers of this one engine.
**Depends on**: Phase 26
**Requirements**: SYNC-02, SYNC-03, SYNC-04, SYNC-05
**Success Criteria** (what must be TRUE):

  1. Merging a batch of operations and cash movements inserts each row verbatim keyed by UUID (preserving origin `id`/`device_id`/`seq`/author), and merging the same batch twice changes nothing — no duplicated operations, no double-counted stock or cash. (SYNC-02)
  2. After any merge, derived stock quantities and cash balances are recomputed from the ledger so counts and figures stay correct. (SYNC-03)
  3. Both ledgers merge together atomically through a single exchange format and a single merge engine that online sync and the offline upload will both reuse — never two divergent implementations. (SYNC-04)
  4. Conflicting edits to mutable reference data (products, customers, warehouses, batches, dictionary) from different devices resolve to the server's version, including a defined rule for a duplicate `Product.code` created on two devices. (SYNC-05)

**Plans**: 4 plans (4 waves)

- [x] 27-01-PLAN.md — NDJSON exchange format + parse/serialize (verbatim round-trip, strict validation) (wave 1)
- [x] 27-02-PLAN.md — recompute_derived extraction + apply_merge idempotent ledger append + recompute (SYNC-02/03) (wave 2)
- [x] 27-03-PLAN.md — reference upsert (server-wins, FK-order, tombstone) + Product.code collision rename (SYNC-05) (wave 3)
- [x] 27-04-PLAN.md — PostgreSQL portability slice + pg-parity CI wiring (one engine, both dialects) (wave 4)

> **Research flag (resolved):** The per-phase research pass ran (`27-RESEARCH.md`). The three flagged design decisions are resolved as researcher-recommended defaults (no `27-CONTEXT.md`): per-table = insert-if-new + server-wins-on-existing (row-level); `Product.code` collision = rename the incoming loser (keep UUID, incumbent keeps code, report); tombstones = inline `deleted_at`, never resurrect/delete a server row. Traced as DD-1/DD-2/DD-1b in the plans for later sign-off.

#### Phase 28: Central Server — Hosting & Sync API

**Goal**: Bring the central server alive — a VPS PostgreSQL deployment that hosts both online interfaces (browser + mobile) and exposes token-authenticated push/pull sync endpoints wired to the Phase 27 merge engine, plus the column-scoped append-only trigger relaxation that lets the `synced_at` cursor advance without reopening the ledger to tampering.
**Depends on**: Phase 27 (merge engine) and Phase 25 (per-device identity/token)
**Requirements**: SRV-04, SYNC-09
**Success Criteria** (what must be TRUE):

  1. The central server hosts a browser (desktop) UI and a mobile UI online; the mobile UI is server-only, with no offline/local mobile install — mobile users always work against the server online. (SRV-04)
  2. The server exposes push and pull sync endpoints that a client authenticates to with a per-device token; a request without a valid token is rejected. (SYNC-09)
  3. A ledger row's `synced_at` cursor can be stamped, but any attempt to change an immutable ledger column (`qty_delta`, `amount_cents`, author) is still rejected at the database — on both SQLite and PostgreSQL — enabling the sync cursor (SYNC-01) without weakening the append-only guarantee.

**Plans**: 6 plans
Plans:
**Wave 1**

- [x] 28-01-PLAN.md — Append-only trigger relaxation: migration 0018 + APPEND_ONLY_TRIGGERS lockstep + SQLite/PostgreSQL SC-3 proof (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 28-02-PLAN.md — Device-token core: DeviceToken model + migration 0019 + mint/verify/revoke service (SYNC-09) (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 28-03-PLAN.md — /api/sync/ guard bypass + require_device Bearer dependency + POST /api/sync/push (SYNC-09, SC-2) (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 28-04-PLAN.md — GET /api/sync/pull cursor service + route + SRV-04 both-UIs-one-app assertion (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 28-05-PLAN.md — Admin device-token surface at /settings/devices (mint show-once, revoke, operator 403) (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 28-06-PLAN.md — PostgreSQL-safety guards (backup dialect gate, session Secure flag) + provider-agnostic deploy/ runbook (SRV-04) (wave 6)

> **Open user decision (does not gate the phase):** the VPS provider, plan size and domain name (RESEARCH OQ-1) are deliberately NOT chosen by these plans. All deployment artifacts are provider-agnostic and every success criterion is provable locally and in CI.

#### Phase 29: Online Client Sync

**Goal**: Wire the local desktop client to the server's sync API — a manual «Синхронизировать» action pushes operations and cash movements up and pulls server-authoritative reference data down, with clear status, an unsynced-count badge, an optional interval-based background sync, and offline-safe failure that never blocks local work.
**Depends on**: Phase 28
**Requirements**: SYNC-01, SYNC-06, SYNC-07, SYNC-08, SRV-03
**Success Criteria** (what must be TRUE):

  1. When online, the operator clicks «Синхронизировать» and the client pushes its operations and cash movements to the server and pulls server-authoritative reference data down, leaving stock counts and figures correct afterward. (SYNC-01)
  2. The sync UI shows sync status, last-sync time, and a plain-language Russian result; a sync failure surfaces clearly and never blocks continued local work. (SYNC-06)
  3. A badge shows the count of local operations not yet synced to the server. (SYNC-07)
  4. The operator can enable an optional interval-based automatic background sync that silently stops attempting while offline; with it disabled, only the manual button syncs. (SYNC-08)
  5. The desktop client keeps working fully offline on local SQLite — the central server is needed only for sync, never for day-to-day local work. (SRV-03)

**Plans**: 5 plans (4 waves)

Plans:
**Wave 1**

- [x] 29-01-PLAN.md — Foundation: httpx runtime dep + sync URL/token config + SyncState table + synced_at partial indexes + migration 0020 + PG parity (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 29-02-PLAN.md — Sync state + badge count + D-12 Russian result formatter + fresh auto-sync config read (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 29-03-PLAN.md — Sync driver core: push + D-13 reference closure + pull-apply with D-14 server-wins-on-update + offline-safe + single-run lock (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 29-04-PLAN.md — «Синхронизировать» button + header OOB status/badge partial + POST /sync/run + every-page context (wave 4)
- [x] 29-05-PLAN.md — Optional interval auto-sync lifespan loop + Settings auto-sync toggle/interval (wave 4)

**UI hint**: yes

#### Phase 30: Offline Self-Uploading File

**Goal**: Ship the upload-only offline path last, reusing the proven Phase 27 engine — the client exports all not-yet-uploaded work to a single self-contained file on a USB drive that, opened on any internet computer with no app installed, authenticates with login/password, shows a preview, and uploads its own data through the same idempotent merge, with server-side integrity and schema-version validation.
**Depends on**: Phase 29 (final exchange-format and watermark semantics) and Phase 27 (merge engine)
**Requirements**: OFF-01, OFF-02, OFF-03, OFF-04, OFF-05, OFF-06, OFF-07
**Success Criteria** (what must be TRUE):

  1. With no internet, the local desktop client keeps recording operations normally and accumulates everything not yet uploaded, then exports it to a single self-contained file on a USB flash drive. (OFF-01, OFF-02)
  2. On any internet-connected computer with no application installed, the operator opens the file (leading approach: an HTML file in any browser) and it uploads its own data to the central server after authenticating with a login and password; a wrong credential is rejected with a clear message and no data is sent. (OFF-03, OFF-04)
  3. Before uploading, the file shows a preview of what will be sent (count of operations/records) and requires an explicit confirm. (OFF-06)
  4. The server ingests the file through the same idempotent UUID merge as online sync — uploading the same file twice changes nothing, and an interrupted upload never leaves a half-applied batch (all-or-nothing on the server). (OFF-05)
  5. The server validates every uploaded file (integrity checksum + schema-version compatibility) and rejects a tampered or incompatible file with a clear message. (OFF-07)

**Plans**: 4 plans (Waves 0-3)

Plans:
**Wave 0**

- [x] 30-01-PLAN.md — Nyquist test scaffold: tests/test_offline.py RED map + fixtures/helpers (OFF-01..07 + token/bypass/escaping/CRLF/rate-limit) (wave 0)

**Wave 1** *(blocked on Wave 0 completion)*

- [x] 30-02-PLAN.md — Foundation contracts: payload_sha256 serializer field + public collect_push_records + /api/offline/ guard bypass + offline token/schema service (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 30-03-PLAN.md — Server ingest: POST /api/offline/login (two-step, narrow CORS) + POST /api/offline/upload (integrity + schema gate + all-or-nothing apply_merge) + RU result pages (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 30-04-PLAN.md — Client export: GET /offline/export + self-contained self_upload.html (preview + confirm + form-POST) + S3 export CTA (wave 3)

**UI hint**: yes

> **Research flag:** This phase needs a per-phase research pass at plan time. The self-contained-file mechanism (final form of the "HTML + embedded data opened in a browser" leading approach) and the file trust/version model (signed manifest vs. checksum-only, how to bind claimed origin without an authenticating server in the loop, schema-version compatibility rule, re-running write-path validations on the bulk path) warrant a focused pass.

<details>
<summary>✅ v4.0 Distribution & Delivery (Phases 31-32) — SHIPPED 2026-09-03</summary>

- [x] Phase 31: Packaging, Launcher & Signed-Release Pipeline (8/8 plans) — completed 2026-09-03
- [x] Phase 32: In-App Secure Self-Update (5/5 plans) — completed 2026-09-03

**Two acknowledged, human-only gaps at close** (not code defects): the bare-Windows install run of `dist\Output\MyOriShop-Setup-1.60.exe`, and the first real tag-triggered signed release. See `.planning/MILESTONES.md` and STATE.md `## Operator Next Steps`.

Full phase details archived in `.planning/milestones/v4.0-ROADMAP.md`.

</details>

### 🚧 v5.0 Corrections, Dates & Currency (In Progress)

**Milestone Goal:** Let the operator repair and correctly date their own data — reverse a wrong operation from История, record an operation with the date it actually happened, and fix product and customer cards from the phone. The per-warehouse currency feature shipped 2026-08-10; its render-coverage tail rides along as a plan, not a phase.

**Build order (dependency-driven, not preference-driven):** sync-skew hardening before any schema change reaches a self-updating client → ONE migration carrying all four ledger columns, plus every reader switched to the business date in one pass → reversal, which can only be correct once the business date exists **and** the readers bucket by it → mobile editing last, against the finished feature set and the final money render.

- [ ] **Phase 33: Back-Dated Operations** — sync-skew hardening first, then one migration adding all four ledger columns with a timezone-correct backfill, and every period-scoped surface switched to the business date in a single pass
- [ ] **Phase 34: One-Tap Reversal (сторно) & Currency Render Coverage** — a confirmed «сторно» control in История writing a same-type, opposite-sign compensating row that inherits the origin's business date, plus the counted `| cents` → `| money(...)` sweep and its tripwire
- [ ] **Phase 35: Mobile Card Editing** — mobile edit route pairs for the product card and the full customer profile (all four contact kinds, multi-value), reusing the desktop services unchanged

#### Phase 33: Back-Dated Operations

**Goal**: The operator can record an operation with the date it actually happened, and every period-scoped figure in the app buckets by that date — while the technical timestamp keeps all three of its existing jobs (audit trail, display order, sync selection), and while the milestone's own schema change cannot open a silent data-loss window across the self-updating client fleet.
**Depends on**: Phase 32 (previous milestone; first phase of v5.0)
**Requirements**: SYNC-10, SYNC-11, SYNC-12, SYNC-13, DATE-01, DATE-02, DATE-03, DATE-04, DATE-05, DATE-06, DATE-07, DATE-08
**Success Criteria** (what must be TRUE):

  1. On every operation-writing form — 6 desktop forms and 5 mobile wizards — the operator can set the date the operation actually happened, pre-filled with today; a future date is refused with a Russian message and any past date is accepted. (DATE-01, DATE-02)
  2. Every period-scoped figure — dashboard day/week/month totals, the sales-profit report, the cash-flow report, the stock and write-off reports, customer spend, История's date filter and the period CSV exports — buckets by the business date, switched in ONE pass, so no two surfaces disagree about the same week; and changing an operation's business date never moves it in the sync queue or alters its audit record. (DATE-03, DATE-04)
  3. **A fixed past period's `sales_profit_report` returns byte-identical totals before and after the migration** — the backfill is timezone-correct, not a naive UTC-prefix cut — and an operation arriving from a client that has not yet updated still appears in every report, bucketed by its entry date, rather than vanishing from the period. (DATE-07, DATE-08)
  4. История and the CSV exports show both dates whenever they differ, and a row whose business date differs from its entry date is marked «задним числом» and can be filtered on that in История. (DATE-05, DATE-06)
  5. A push carrying a schema version the receiver does not understand is refused with a clear Russian message instead of being accepted with fields silently dropped; the refused client's rows stay unsynced (`synced_at` NULL) so the next successful push re-sends them; a cash movement pushed by a client that predates a column's introduction lands correctly instead of bricking that client's sync; and the append-only triggers are proven live against a database built by `alembic upgrade head`, not only one built by `create_all`. (SYNC-10, SYNC-11, SYNC-12, SYNC-13)

**Ordering constraints — LOCKED. A later planner may not silently reorder these:**

  1. **SYNC-10..13 land BEFORE the migration, as the first plans of this phase.** They are not polish: `merge._ledger_row` projects an incoming batch through the *receiver's* columns, so a client that self-updates ahead of the s1 rebuild pushes `business_date`, the server drops it, returns 200, and the client stamps `synced_at` — permanent, unrecoverable loss behind a success response. SYNC-12's answer also *determines the new columns' definitions* (an explicit `None` in the insert dict versus `server_default` decides whether any of the four can ever be NOT NULL — the research answer is that all four must be **nullable**).
  2. **All four new ledger columns land in ONE migration** — `operations.business_date`, `cash_movements.business_date`, `operations.reverses_op_id`, `cash_movements.reverses_movement_id`. One dual-dialect trigger rewrite, one lockstep pass, one fleet skew window instead of two. The two `reverses_*_id` columns ship **unused but trigger-guarded**; Phase 34 only starts *writing* them.
  3. **The migration's internal order is `add_column` → timezone-correct backfill → THEN extend the append-only trigger's column enumeration.** Reversed, the backfill UPDATE trips the guard it just installed and `alembic upgrade head` aborts mid-upgrade on the live server. Write the ordering as a comment inside the migration file — it is the single most reorderable line in it.
  4. **The five-artifact lockstep is ONE commit**: the migration (both `_SQLITE_DDL` `IS NOT` and `_PG_DDL` `IS DISTINCT FROM` branches, plus both `downgrade()` halves) + `app/db.py::APPEND_ONLY_TRIGGERS` + both `IMMUTABLE_*_COLUMNS` frozensets + the two test constants in `tests/test_append_only_cursor.py`, alongside the model columns. Migration `0026` exists solely because this was missed once for `cash_movements.currency`. `test_trigger_column_list_matches_schema` is the tripwire — do not "fix" it by editing one constant.
  5. **Rollout order, written into the plan:** migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → *only then* cut the client release tag. Never edit migrations `0018`/`0026` retroactively — an applied migration is historical fact.
  6. **`business_date` gets its own period-bounds helper.** Do not reuse `local_day_bounds_utc` (14 call sites): a date-only column compared against UTC-timestamp bounds is a lexicographic comparison between two formats that happens to land right at UTC+3 and is off by a full day at any UTC− offset.

**Pitfalls owned** (`.planning/research/PITFALLS.md`): 1 (new ledger column escapes the trigger), 2 (backfill deadlocks against its own new trigger), 3 (`batch_alter_table` silently drops all four triggers — `add_column` only), 4 (a new column silently dropped by an older-code server), 14 (date-only column vs UTC-timestamp bounds — needs a `display_tz="America/New_York"` test), 15 (ordering ties on `business_date` — any sort entry must end in `created_at desc, seq desc`), 16 (the sync cursor accidentally follows the business date — `business_date` must appear nowhere in `sync.py`/`sync_client.py`/`routes/sync.py`), 20 (back-dating into an already-reported period — settled as unbounded + the «задним числом» marker, operator decision 2), 21 (migration count and rollout order).

**`needs verification` carried from research** (`.planning/research/SUMMARY.md` → Consolidated list): **V1** does an explicit `None` beat `server_default` in `session.execute(insert(model), rows)`? (6-line inverted merge test; also exposes the pre-existing `CashMovement.currency` NOT NULL bug) — *blocking*. **V2** what an older-*code* receiver does with an unknown wire field (monkeypatch `merge.KIND_TO_FIELDS` to the pre-change set; assert reject-not-drop) — *blocking*. **V3** does `tests/conftest.py`'s `engine` fixture build via `create_all`, making the trigger-liveness test non-migration-proving? (read the fixture) — *blocking*. **V4** does the backfill UPDATE trip the pre-rewrite trigger, and does it cover every row? (run against a copy of the s1 dump; assert rows-updated == rows-total). **V13** is s1's `alembic_version` at `0026` today? (`alembic current` on s1) — pre-rollout. **V14** what `display_tz` does s1's `.env.production` actually set? (it parameterises the backfill) — pre-rollout. **V15** is alembic 1.19.1 still the newest at planning time? (`uv pip index versions alembic` — **do not bump regardless**) — advisory.

**Research flag**: **not needed.** Skip `--research-phase`. The migration ritual is written verbatim in `0017`/`0018`/`0024`/`0026`, the helper shape is `local_day_bounds_utc` / `operation_currency_clause`, the type choice (`String(10)` ISO text) was verified by execution, and the call-site list is enumerated (9 must-switch, ~14 must-not).

**Plans**: 15 plans (6 waves)

Plans:
**Wave 1** *(SYNC-10..13 + the deployment facts — LOCKED ordering constraint 1: these land BEFORE the migration)*

- [x] 33-01-PLAN.md — POST /api/sync/push asymmetric schema gate: push_schema_ok + 409 + SCHEMA_AHEAD_ERROR (SYNC-10/11) (wave 1)
- [x] 33-02-PLAN.md — Client refusal surface: schema_mismatch SyncResult + RU formatter branch + auto-sync back-off (SYNC-10/11) (wave 1)
- [x] 33-03-PLAN.md — Migration-proving harness: alembic_engine + VA-5/6/7 + merge pinning tests (SYNC-12/13) (wave 1)
- [x] 33-04-PLAN.md — V13/V14 on s1 + the rollout runbook 33-ROLLOUT.md (autonomous: false; V14 gates the migration) (wave 1)

**Wave 2** *(blocked on Wave 1)*

- [x] 33-05-PLAN.md — The five-artifact lockstep as ONE commit: 4 ledger columns + tz-correct backfill + dual-dialect trigger rewrite + mirrored downgrade (migration 0027) (wave 2)

**Wave 3** *(blocked on Wave 2)*

- [x] 33-06-PLAN.md — Shared primitives: business_date_bounds, local_today_iso, business_date_expr, today_iso global, parse_op_date + both write-path kwargs + the one new CSS rule (wave 3)

**Wave 4** *(blocked on Wave 3)*

- [x] 33-07-PLAN.md — Reports/finance/dashboard: 5 predicates + 10 bounds sites switched; VA-9 byte-identity across the migration (DATE-03/07) (wave 4)
- [ ] 33-08-PLAN.md — История/customers/warehouses readers + D-24 borderline set + VA-17 ordering tripwire (DATE-03/04) (wave 4)
- [ ] 33-10-PLAN.md — Приход + списание write surfaces (desktop + mobile) + D-24 batch auto-name (DATE-01/02) (wave 4)
- [ ] 33-11-PLAN.md — Продажа + возврат write surfaces (desktop + mobile) + D-24 return label (DATE-01/02) (wave 4)
- [ ] 33-12-PLAN.md — Корректировка + перемещение write surfaces (desktop + mobile final steps) (DATE-01/02) (wave 4)

**Wave 5** *(blocked on Wave 4)*

- [ ] 33-09-PLAN.md — CSV: «Когда» becomes the business date, «Внесено» appended last, both ORDER BYs incl. the CD-9 gap (DATE-03/05) (wave 5)
- [ ] 33-13-PLAN.md — Cash forms (shared desktop↔mobile) + VA-15 all-14-surfaces proof (DATE-01/02) (wave 5)
- [ ] 33-14-PLAN.md — История both-dates rendering + «задним числом» filter, desktop AND mobile (DATE-05/06) (wave 5)

**Wave 6** *(blocked on Wave 5)*

- [ ] 33-15-PLAN.md — CI PostgreSQL parity + browser checks B-1..B-7 + the LOCKED rollout (autonomous: false) (wave 6)

**UI hint**: yes

#### Phase 34: One-Tap Reversal (сторно) & Currency Render Coverage

**Goal**: From История, on desktop and mobile, the operator can undo a wrong receipt, write-off, correction, transfer or manual cash movement in one confirmed action that repairs the period it actually broke — and every amount the operator reads anywhere in the app states which currency it is in.
**Depends on**: Phase 33 — **hard, not soft**. A reversal must inherit the origin's business date AND the readers must already bucket by it; shipping storno first would write every reversal with no business date, and there is no retrofit because the ledger is append-only.
**Requirements**: REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, REV-07, REV-08, REV-09, REV-10, REV-11, CUR-03, CUR-04, CUR-05, CUR-06, CUR-07, CUR-08
**Success Criteria** (what must be TRUE):

  1. From История, on both desktop and mobile, the operator reverses a wrong receipt, write-off, correction, transfer or manual cash movement in one confirmed action; the confirmation states what will be written — including the business date the compensating row will carry — before anything is written; the result is a NEW compensating row of the same type with the opposite sign, written through the existing sanctioned write path, with nothing edited or deleted. A mistyped cash deposit or withdrawal, which has no undo at all today, is covered. (REV-01, REV-02, REV-03, REV-10)
  2. The reversal repairs the period it broke instead of creating a phantom one: it carries the **original** operation's business date, every existing report nets it out automatically — including the per-line breakdowns, the write-off report's per-reason lines and not just its grand total — and a multi-row operation reverses as one unit or not at all, so a transfer's two rows never half-reverse. (REV-04, REV-05, REV-06)
  3. История shows both sides of the relationship — the original marked «сторнирована», the compensating row reading «сторно операции X» — and the control is unavailable on an already-reversed row, on a reversal itself, and on a sale, where the operator is pointed at «Возврат» instead. Reversing an operation whose stock has already moved on is refused before any write, with a Russian message saying why; stock is never driven negative (a hard guard, not the warn-but-allow oversell shape). (REV-07, REV-08, REV-09, REV-11)
  4. Wherever an amount stands alone the operator can see which currency it is in — measured against the full render surface, not eyeballed, with История the priority (three currencies interleave there today with no marker); a customer's spend totals and purchase history state their currency or are scoped to one; and a regression tripwire prevents the swept surfaces from drifting back to an unlabelled render. (CUR-03, CUR-04, CUR-07)
  5. No report can produce a total that mixes currencies — `writeoff_report`, `top_selling_products` and `stale_products` each carry an explicit, recorded decision; a warehouse's currency cannot be changed once it holds stock, cash or history; and the per-warehouse currency feature finally gets the human browser check it never received. (CUR-05, CUR-06, CUR-08)

**Currency render coverage is a PLAN inside this phase, not a phase of its own.** The feature shipped 2026-08-10 (quick task `260810-2g3`, migrations 0023–0026); what remains is a counted sweep with no schema work and no ordering claim over anything. It is carried here, and **must be sequenced adjacent to the reversal work**, because the reversal control, the currency marker and the business-date column all edit `app/services/operations.py::history_view`, `app/templates/partials/history_rows.html` and `app/templates/mobile_partials/history_cards.html` — placing it elsewhere means editing those files three times instead of once. It must also complete **before Phase 35 starts**, so the mobile product form ships with the final money render rather than being redone. Do **not** run the currency plan in parallel with a reversal plan that touches the История templates.

**Ordering constraints — LOCKED:**

  1. **This phase does not add a migration.** Both `reverses_*_id` columns already exist and are trigger-guarded from Phase 33; this phase only starts writing them. If a plan proposes a second ledger migration, that is a signal something was dropped in Phase 33 — resolve it there, not here.
  2. **The compensating row is the SAME type with a verbatim copy of the target's `payload`, `batch_id`, `currency` and frozen prices**, differing only in the sign of `qty_delta`/`amount_cents` and its own identity/audit fields. Never a dedicated `storno` type: every existing `WHERE type == ...` filter would miss it and *nothing* would net.
  3. **The double-reversal cap is ledger-derived, never a flag column** (`SELECT ... WHERE reverses_op_id = :id`, mirroring `returns.returnable_qty`). A `reversed` boolean is blocked by the append-only trigger, invisible across sync, and lets two devices double-reverse the same receipt.
  4. **No DB-level FK on `reverses_*_id`** — bare native column in the migration, ORM `ForeignKey` only for insert ordering and PostgreSQL portability (the `sale_id`/`batch_id`/`author_id` precedent), so a reversal whose target has not yet arrived renders as a dangling link instead of rolling back an entire push.
  5. **The non-SUM aggregate audit is a written artifact, not a feeling.** Walk `reports.py`, `dashboard.py`, `finance_reports.py` and `customers.py` for every aggregate that is not a plain SUM (`MAX`, `func.count`, `GROUP BY payload[...]`, `.limit()` over an ordered aggregate) and record an explicit decision for each.

**Pitfalls owned** (`.planning/research/PITFALLS.md`): reversal — 9 (double-reversal guarded by a flag instead of a ledger-derived cap), 10 (reversal link in `payload` JSON instead of an indexed column — impossible for cash, which has no `payload` column at all), 11 (a reversal FK rolling back a whole push), 12 (a reversal driving stock negative), 13 (reversal of a return / of a reversal — explicit allow-list and exclusion list as constants), 19 (the reversal's business date — the silent failure mode is `reversals.py` simply not passing the kwarg, which makes **every** reversal wrong by default with no error), 23 (a reversal losing its currency or a legacy NULL-batch row bucketing as RUB), 26 (storno breaking every aggregate that is not a plain SUM). Currency plan — 5 (money rendered without a currency almost everywhere: `money(` in 1 template against `| cents` in 42), 6 (`Product.cost_cents` has no currency and is the sale-cost fallback for every warehouse), 7 (a warehouse's currency editable after it holds stock, retroactively relabelling history), 25 (write-offs / top-selling / stale never currency-scoped).

**`needs verification` carried from research**: **V5** does any report `COUNT` operations rather than SUM signed quantities, so a storno counts as a second event instead of netting? (three instances already identified at `reports.py:108,153,224`). **V6** are historical transfer pairs really `seq`-adjacent in production data? (`SELECT device_id, seq, qty_delta FROM operations WHERE type='transfer' ORDER BY device_id, seq` on the s1 dump; assert every row pairs with `seq±1`). **V7** does `writeoff_report` sum money or only quantities? (read `reports.py:127-171`). **V8** the exact per-surface list of templates still rendering bare `format_cents` / `| cents` — re-run `rg -c '\| cents' app/templates` at plan time against ARCHITECTURE §5.1's classification rather than trusting the snapshot counts (103 renders / 42 templates measured at `b4ca98c`, of which ~50 renders / 29 templates are genuine gaps). **V9** does a rejected mixed-currency basket preserve the typed basket on re-render? (route-level test — the service-level test at `tests/test_sales.py:617` does not cover the render). **V10** does the *mobile* sale wizard render `errors.basket`? **V11** mobile currency-switcher coverage beyond `/m/finance` and the mobile home. **V12** which batch-picker services already load `Warehouse`, so a per-row currency is available? **V16** how a storno of a *sale* would interact with the sale's cash movement and customer spend statistics — **CLOSED at requirements time** by operator decision 1 (sales are excluded from storno; the operator uses «Возврат»), recorded here so it is not silently re-opened.

**Research flag**: **`--research-phase` at plan time.** Two items are discovery work, not implementation work: (a) the transfer sibling-resolution problem has no existing handle in the data — no group id, no shared payload key — and the `seq±1` probe needs a hard "exactly one match, all three assertions pass" rule plus a decision on stamping `transfer_group_id` on new transfers; (b) the non-SUM aggregate audit spans four service modules. This is the one part of the feature that can quietly produce a wrong result, so it gets its own explicit success criterion.

**Plans**: TBD
**UI hint**: yes

#### Phase 35: Mobile Card Editing

**Goal**: The operator can fix a product card and an existing customer's complete profile from the phone, at parity with the desktop forms and through the same services — without a mobile save ever silently destroying data the small screen did not show.
**Depends on**: Phase 34 (the currency plan must have landed so the mobile product form ships with the final money render) and Phase 33 (the product edit path writes `price_change`/`product_edited` ledger rows through `record_operation`, so it inherits the business-date contract). Shares no files with the ledger work otherwise.
**Requirements**: MOB-02, MOB-03, MOB-04, MOB-05, MOB-06, MOB-07, MOB-08
**Success Criteria** (what must be TRUE):

  1. From the phone, the operator edits a product card — minimum sale price, cost, sale price, category and low-stock threshold — and corrects an existing customer's complete profile: name, surname, consultant number, address, and every contact kind (phones, emails, telegram, social), at full parity with the desktop customer form. (MOB-02, MOB-03)
  2. Saving from the phone never blanks a field the small screen did not show and never deletes a contact the operator did not touch; multi-value survives — a customer with three phones still has three phones after a save, and the form can add and remove values within each kind. (MOB-05)
  3. A mobile edit that touches no contact field leaves the customer's contacts byte-identical, pinned by a GET → POST-unchanged round-trip test — the single check that catches this whole family of defects, and the same round trip proves no product column was NULLed either. (MOB-06)
  4. The mobile forms reuse the same services as the desktop ones, so a validation rule can never differ between the two, and a rejected mobile edit redisplays what the operator typed with the error next to the offending field. (MOB-04, MOB-07)
  5. The operator is not misled about where a contact lives: `CustomerContact` is not part of the sync exchange in either direction and the mobile UI is server-only, so a phone edited on the phone updates the server and will not appear in the desktop client. v5.0 states this pre-existing divergence honestly rather than pretending it does not exist. (MOB-08)

**Scope note — sized correctly.** This is *not* a flat-field edit form. The operator amended the customer scope twice on 2026-09-04 and settled on full parity including all four `CONTACT_KINDS`, which means a repeatable multi-value field group on a phone screen. That amendment also **closes** the delete-by-omission trap by construction rather than guarding against it: `update_customer`'s contract is that a `contacts` dict fully replaces the set and an omitted kind is cleared, so rendering all four kinds makes a full-replacement submission correct — exactly what Pitfall 17 prescribes. **Do not plan a partial-update path or a second service variant**; that would create the second validation path MOB-04 forbids. The same completeness rule applies to the product form: render every field `update_product` reads, because `parse_optional_cents("")` returns `None` and an omitted field is written as NULL with a `price_change` audit row recording the wipe. No wire-format change and no `FORMAT_VERSION` bump is in scope.

**Ordering constraints — LOCKED:**

  1. **Zero service changes.** New routes and templates only, following `app/routes/mobile_batches.py`'s module shape (the exact shipped `GET /m/batches/{id}/edit` + `POST /m/batches/{id}` precedent), not POST handlers bolted onto `mobile_products.py`/`mobile_customers.py`, whose docstrings declare a "one plain full-page GET, no HX-partial branch" contract.
  2. **Every new `hx-vals` is single-quoted.** `rg 'hx-vals="' app/templates` must return nothing — double quotes truncated five attributes and silently killed batch selection in every mobile wizard once already (quick task `260813-ezt`).

**Pitfalls owned** (`.planning/research/PITFALLS.md`): 8 (reference edits made on a *client* never reach the server and are overwritten on the next pull — mobile editing makes this pre-existing topology acutely visible; state it, do not fix it here), 17 (a mobile edit form silently NULLing every field it does not render — closed by completeness, see the scope note), 18 (the three HTMX partial-swap traps this codebase has already been bitten by: `| tojson` in a double-quoted attribute, un-`<template>`-wrapped OOB `<td>`/`<tr>`, filter/sort/page state dropped on the write response), 22 (editing a record while the background auto-sync tick overwrites it), 24 (`CustomerContact` is not a sync kind at all — the operator chose neither of the research's two options: mobile is server-only so no wire change is needed, and MOB-08 states the divergence).

**`needs verification` carried from research**: none outstanding for this phase. Pitfall 24's fact (zero occurrences of `CustomerContact` in `app/services/merge.py`) was verified in HEAD during requirements.

**Research flag**: **not needed.** Skip `--research-phase`. `mobile_batches.py` is an exact, shipped route-pair precedent and the pitfalls are enumerated. The one genuinely new UI element — the repeatable multi-value contact group — has a desktop counterpart in the Phase 21 customer form to copy.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24 → 25 → 26 → 27 → 28 → 29 → 30 → 31 → 32 → 33 → 34 → 35

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|-----------------|--------|-----------|
| 1. Foundation & Ledger Core | v1.0 | 3/3 | Complete | 2026-07-08 |
| 2. Catalog, Dictionary & Search | v1.0 | 4/4 | Complete | 2026-07-08 |
| 3. Goods Receipt & Backup | v1.0 | 3/3 | Complete | 2026-07-09 |
| 4. Sales & Customers | v1.0 | 6/6 | Complete | 2026-07-09 |
| 5. Stock Operations & History | v1.0 | 9/9 | Complete | 2026-07-10 |
| 6. Reports & Data Export | v1.0 | 6/6 | Complete | 2026-07-10 |
| 7. Category Browsing & Minimum Price Guardrail | v1.1 | 4/4 | Complete    | 2026-07-10 |
| 8. Warehouses | v1.1 | 2/2 | Complete   | 2026-07-11 |
| 9. Batch Tracking & Ledger Integration | v1.1 | 9/9 | Complete    | 2026-07-12 |
| 10. Warehouse Transfers & Expiry Reporting | v1.1 | 3/3 | Complete    | 2026-07-12 |
| 11. Dedicated Mobile Flow | v1.1 | 10/10 | Complete   | 2026-07-13 |
| 12. Code & Name Autofill | v1.2 | 4/4 | Complete    | 2026-07-13 |
| 13. Mobile Wizard Context & Navigation | v1.2 | 6/6 | Complete    | 2026-07-13 |
| 14. List Pagination, Filtering, Sorting & Quick Delete | v1.2 | 7/7 | Complete    | 2026-07-14 |
| 15. Cash Ledger Foundation | v1.3 | 4/4 | Complete   | 2026-07-14 |
| 16. Manual Cash Movements & History | v1.3 | 4/4 | Complete    | 2026-07-15 |
| 17. Financial Reports, Export & Dashboard Analytics | v1.3 | 5/5 | Complete   | 2026-07-15 |
| 18. Two-Price Model Consolidation (ДЦ/ПЦ) | v2.0 | 8/8 | Complete   | 2026-07-16 |
| 19. Products Page Rebuild | v2.0 | 1/1 | Complete    | 2026-07-16 |
| 20. Warehouses & Batch-Split Transfers | v2.0 | 7/7 | Complete   | 2026-07-16 |
| 21. Customer Profiles & Purchase Insights | v2.0 | 5/5 | Complete    | 2026-07-17 |
| 22. Sales Page Rebuild | v2.0 | 7/7 | Complete    | 2026-07-17 |
| 23. Dashboard & History Rebuild | v2.0 | 7/7 | Complete    | 2026-07-17 |
| 24. Navigation Restructure & Settings | v2.0 | 7/7 | Complete    | 2026-07-17 |
| 25. Authentication, Roles & User Attribution | v3.0 | 9/9 | Complete   | 2026-07-18 |
| 26. PostgreSQL Portability & Append-Only Parity | v3.0 | 3/3 | Complete   | 2026-07-18 |
| 27. Shared Idempotent Merge Core | v3.0 | 4/4 | Complete   | 2026-07-19 |
| 28. Central Server — Hosting & Sync API | v3.0 | 6/6 | Complete    | 2026-07-19 |
| 29. Online Client Sync | v3.0 | 5/5 | Complete    | 2026-07-20 |
| 30. Offline Self-Uploading File | v3.0 | 4/4 | Complete   | 2026-07-20 |
| 31. Packaging, Launcher & Signed-Release Pipeline | v4.0 | 8/8 | Complete    | 2026-09-03 |
| 32. In-App Secure Self-Update | v4.0 | 5/5 | Complete    | 2026-09-03 |
| 33. Back-Dated Operations | v5.0 | 7/15 | In Progress|  |
| 34. One-Tap Reversal (сторно) & Currency Render Coverage | v5.0 | 0/0 | Not started | - |
| 35. Mobile Card Editing | v5.0 | 0/0 | Not started | - |

## Backlog

### Phase 999.1: Per-Warehouse Currency (RUB/UAH/EUR) — ✅ SHIPPED 2026-08-10, NOT A PHASE

**Goal:** Each warehouse carries its own currency; money is never silently summed across currencies.
**Status:** Delivered as quick task `260810-2g3` (plus its part-1 predecessor) — 9 `feat(cur)` commits starting at `cdcec66`, migrations 0023–0026, requirement IDs CUR-01/CUR-02.
**Plans:** shipped outside the phase system

> ⚠ **The scope survey below is dated 2026-08-09 and was overtaken the NEXT DAY.** Do not plan from it. Verified in HEAD 2026-09-04: `Warehouse.currency`, `CashMovement.currency`, `Batch.cost_cents`, `CURRENCIES`/`currency_symbol()`/`format_money()` (`app/core.py:56-86`), the `money` Jinja filter (`app/routes/__init__.py:227`), currency-scoped `/reports/sales` via a shared `operation_currency_clause` (OUTER-joined so legacy `batch_id IS NULL` rows bucket as RUB rather than vanishing), currency-scoped finance reports plus a `/finance` switcher, a Главная dashboard switcher, currency labels on CSV exports, required destination-currency cost on cross-currency transfers, and rejection of mixed-currency sale baskets before any write (`faff73d`).
>
> **What actually remains** is a coverage tail, carried into v5.0 as a plan rather than a phase: 42 templates still use the bare `|cents` filter against 1 using `|money` — triage which are legitimate (a column already labelled with a currency) versus a real gap (an amount standing alone with no currency visible). Plus `needs verification`: does `writeoff_report` sum money across currencies, and does a rejected mixed-currency basket preserve the operator's typed work on re-render?
>
> ➡ **The remaining tail is now scheduled: CUR-03..CUR-08, carried as a plan inside Phase 34 (v5.0).** This entry stays SHIPPED and is not re-promoted.

<details>
<summary>Superseded scope survey (2026-08-09) — kept for the record</summary>

Decisions locked by the operator (2026-08-09):

- **Field:** `Warehouse.currency`, fixed list RUB/UAH/EUR. Migration backfills `RUB` for every existing warehouse; the warehouse form gets a select defaulting to RUB.
- **No conversion:** no FX rates, no rate table, no base-currency roll-up. Currencies live side by side.
- **Reports:** single-currency only, behind a mandatory warehouse/currency filter. Cross-currency totals must not exist.
- **Transfers:** allowed between warehouses of different currencies; the operator enters the cost in the destination warehouse's currency (today the batch cost is carried over as a bare number).

Scope discovered by reading the code (2026-08-09) — this is a full phase, not a field addition:

- `services/reports.py`, `services/dashboard.py`, `services/finance.py` contain **zero** occurrences of `warehouse`. A currency filter means introducing a warehouse dimension that does not exist there at all. The only link is `Batch.warehouse_id` (`app/models.py:256`); sales reach a warehouse only through batches.
- `format_cents` (`app/core.py:49`) renders `12,50` with no currency symbol anywhere. Every money surface (receipts, transfers, sale, history, batch cards) needs a currency-aware render, desktop **and** mobile templates.
- `services/sales.py` has zero occurrences of `warehouse`, so a basket can currently mix batches from different warehouses — after this change that would mix currencies inside one sale. Mixing must be blocked (or the sale split).
- Sync needs no schema edit: `merge.KIND_TO_FIELDS` (`app/services/merge.py:80`) derives fields from the model columns, so `currency` propagates automatically. **Needs verification:** behaviour when a new-schema client pushes to an old-schema server — the field is likely dropped silently; cover with a version-mismatch test.

Plans:

- [ ] TBD (promote with /gsd-review-backlog when ready)

</details>

### Phase 999.2: One-Tap Reversal of a Wrong Operation — ⬆ PROMOTED to Phase 34 (v5.0, 2026-09-04)

**Goal:** [Captured for future planning] An operator who recorded the wrong receipt, write-off, transfer or cash movement can reverse it from История with one confirmed tap, instead of hand-composing a compensating operation.
**Requirements:** REV-01..REV-11 (defined 2026-09-04)
**Plans:** planned under Phase 34 — see the v5.0 section above

> ⬆ **PROMOTED.** This backlog entry was promoted into milestone v5.0 as **Phase 34: One-Tap Reversal (сторно) & Currency Render Coverage** on 2026-09-04. The capture below is retained for provenance; plan against `.planning/REQUIREMENTS.md` and the Phase 34 detail section, not against this entry.

Captured 2026-08-13 from a live-usage audit prompted by the operator ("найди подобные неудобства"), alongside the batch-editing gap that shipped as quick task 260813-i28. NOT scheduled at capture time — the operator explicitly deferred it.

The problem, verified in code:

- Nothing in the app can be undone. `/history` (`app/routes/history.py:84`) is display-only — `app/templates/pages/history.html` renders no action controls at all.
- Ledger operations are append-only by design (`record_operation`, `app/services/ledger.py:37-49`, is the ONLY sanctioned write path; DB triggers ABORT any UPDATE). That constraint is correct and must stay — a reversal has to be a NEW compensating operation, never an edit or delete.
- Today the operator must hand-compose that compensation and know which tool to reach for: a wrong receipt → correction + write-off; a wrong write-off → a `+` correction; a wrong transfer → a manual reverse transfer. Nothing links the compensating row back to what it fixes.
- Cash is the worst case: `record_cash_movement` (`app/services/finance.py:48`) is the only write path and there is no delete/undo route at all (`app/routes/finance.py` exposes only `/finance/withdraw` and `/finance/deposit`). A mistyped deposit can only be balanced by an opposite movement, leaving two rows and no stated relationship.

Scope sketch (not a plan): a reversal service per operation type that writes the compensating row(s) through the existing sanctioned write paths; a payload link back to the reversed operation id so История can show «сторно операции X»; guards against double-reversal and against reversing a row whose stock has already moved on; the same control on desktop and mobile История. Returns (`app/services/returns.py:117`) are the existing precedent for a linked, capped compensating write.

> ⚠ Superseded by research: the link must be a real indexed column (`reverses_op_id` / `reverses_movement_id`), **not** a payload field — `CashMovement` has no `payload` column at all, and the double-reversal cap must be queryable without dialect JSON SQL. See `.planning/research/PITFALLS.md` #10 and `ARCHITECTURE.md` §4.1.

### Phase 999.3: Back-Dated Operations — ⬆ PROMOTED to Phase 33 (v5.0, 2026-09-04)

**Goal:** [Captured for future planning] The operator can record a sale, receipt or cash movement with the date it actually happened, so period reports stop drifting.
**Requirements:** DATE-01..DATE-08 (defined 2026-09-04), plus the SYNC-10..13 pre-work the research added
**Plans:** planned under Phase 33 — see the v5.0 section above

> ⬆ **PROMOTED.** This backlog entry was promoted into milestone v5.0 as **Phase 33: Back-Dated Operations** on 2026-09-04. The capture below is retained for provenance; plan against `.planning/REQUIREMENTS.md` and the Phase 33 detail section, not against this entry.

Captured 2026-08-13 in the same audit. NOT scheduled at capture time — deferred by the operator.

The problem, verified in code:

- `record_operation` (`app/services/ledger.py:37-49`) takes no date argument; every ledger row is stamped "now". Same for `record_cash_movement` (`app/services/finance.py:48`).
- Consequence: a sale made yesterday and entered today lands in today's bucket. Every period-scoped surface (finance report, dashboard, cash flow, sales profit) inherits the drift.

Known risks to settle before planning: the operation date is currently the same value used for ordering, for the sync cursor and for the append-only audit trail — an operator-supplied date must NOT overwrite the audit timestamp. The likely shape is a separate "business date" column defaulting to the technical timestamp, with reports switching to it; that touches the ledger, the sync payload and every report query, so this is a real phase, not a field.

> ⚠ Corrected by research: `Operation.created_at` is **not** a sync cursor — the ledger push cursor is `synced_at IS NULL` and the pull cursor covers reference kinds only. The audit-trail and display-order concerns stand; the sync-cursor one does not, and `business_date` must appear nowhere in `sync.py`/`sync_client.py`/`routes/sync.py`. See `.planning/research/ARCHITECTURE.md` §0 and PITFALLS #16.

### Phase 999.4: Mobile Editing of Product and Customer Cards — ⬆ PROMOTED to Phase 35 (v5.0, 2026-09-04)

**Goal:** [Captured for future planning] The operator can fix a product card or a customer's details from the phone, instead of having to reach a desktop.
**Requirements:** MOB-02..MOB-08 (defined 2026-09-04)
**Plans:** planned under Phase 35 — see the v5.0 section above

> ⬆ **PROMOTED.** This backlog entry was promoted into milestone v5.0 as **Phase 35: Mobile Card Editing** on 2026-09-04. The capture below is retained for provenance; plan against `.planning/REQUIREMENTS.md` and the Phase 35 detail section, not against this entry.

Captured 2026-08-13 in the same audit. NOT scheduled at capture time — deferred by the operator.

The problem, verified in code:

- `app/routes/mobile_products.py` exposes exactly one route (`GET /m/products`, a list). The mobile product card `app/templates/mobile_partials/search_product_detail.html` states its own read-only status in its header comment; there is no mobile route that writes a `Product`.
- So min sale price, cost, category and the low-stock threshold — all editable on desktop at `/products/{id}/edit` (`app/routes/products.py:262,281`) — are unreachable from the phone.
- `app/routes/mobile_customers.py` likewise exposes only `GET /m/customers`. A new customer CAN be created mid-sale (`app/routes/mobile_sales.py:159` calls the shared `create_customer`), but an existing customer's name, surname, phone or consultant number cannot be corrected from the phone.

Scope sketch (not a plan): mobile route pairs mirroring the desktop edit/update pair and reusing the same services (no second validation path), following the `/m/batches/{id}/edit` precedent shipped in quick task 260813-i28, plus entry points from the mobile product card and the customer list.

> ⚠ Extended at requirements: the operator amended the customer scope twice on 2026-09-04 and settled on **full parity with the desktop form, including all four `CONTACT_KINDS` with multi-value add/remove**. That makes the phase larger than this capture implies and closes the delete-by-omission trap by construction. See MOB-03/MOB-05/MOB-06 and the Phase 35 scope note.
