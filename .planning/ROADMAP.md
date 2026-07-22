# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- ✅ **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (shipped 2026-07-13)
- ✅ **v1.2 Catalog Pricing UX & List Ergonomics** — Phases 12-14 (shipped 2026-07-14)
- ✅ **v1.3 Финансы / Касса** — Phases 15-17 (shipped 2026-07-15)
- ✅ **v2.0 UX Overhaul & Navigation Restructure** — Phases 18-24 (shipped 2026-07-17)
- 🚧 **v3.0 Multi-Operator Sync, Central Server & Roles** — Phases 25-30 (in progress)
- 🚧 **v4.0 Distribution & Delivery** — Phases 31-32 (in progress)

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

### 🚧 v4.0 Distribution & Delivery (In Progress)

**Milestone Goal:** Turn the app from a run.bat/uv dev checkout into a self-contained, self-updating local client distribution for Windows operators. A non-technical Oriflame reseller installs it on a bare Windows machine (no Python, no uv, no git; works offline) and it safely upgrades itself from the project's GitHub Releases without ever losing local data. The central server (s1, ori.viktorplus.com) stays a plain Docker deployment and is the update *target*, never a self-updating client.

**Build order (dependency-ordered — forced):** packaging + a stable launcher + code/data physical separation + a signed-release pipeline first (there is nothing safe to update *to*, and no safe over-the-top swap, until these exist) → in-app secure self-update second (the security-critical, threat-modelled phase where fetched code is executed). Phase B cannot even be tested until two real signed releases exist.

- [ ] **Phase 31: Packaging, Launcher & Signed-Release Pipeline** - Bundled-runtime Windows distributable + unsigned Inno Setup installer, operator data physically separated from swappable code, a stable stop/swap/migrate/restart launcher, and a GitHub Actions pipeline publishing an offline-Ed25519-minisign-signed release (archive + SHA-256 + signature)
- [ ] **Phase 32: In-App Secure Self-Update** - Startup + manual update-check vs GitHub Releases, signature+checksum verify before unpack, notify-and-confirm UI with release notes, backup→migrate→rollback apply, integer-scheme version tie-in with anti-downgrade, and a hard no-op on the PostgreSQL server

#### Phase 31: Packaging, Launcher & Signed-Release Pipeline

**Goal**: Turn the git+uv dev checkout into a self-contained, installable Windows distribution — a bundled Python runtime + app source (onedir), an unsigned Inno Setup installer, operator data physically separated from the swappable code, a stable launcher that can stop/swap/migrate/restart the app, and a repeatable GitHub Actions pipeline that publishes a signed release. This is the prerequisite foundation: there is nothing safe to update *to*, and no safe over-the-top swap, until code/data separation + a launcher + a signed release format exist.
**Depends on**: Phase 30 (previous milestone; first phase of v4.0)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05
**Success Criteria** (what must be TRUE):

  1. On a bare Windows machine with no Python, uv, or git, the operator runs the installer and launches the app to a working localhost browser UI — the distribution's own bundled runtime and app source (onedir layout, never a self-locking single-file exe) run with nothing else installed. (PKG-01)
  2. Installing creates a Start-Menu shortcut and an uninstaller and puts the app per-user under `%LOCALAPPDATA%`; because the installer is shipped unsigned for now, the operator clears the one-time SmartScreen warning via the documented «Подробнее → Выполнить в любом случае» step. (PKG-02)
  3. The operator's SQLite database, the `.env`, the per-install `secret_key`/`device_id`, and `backups/` live in an install-root location that is a *sibling* of the swappable application directory — so replacing the entire application directory can never reach or destroy operator data. (PKG-03)
  4. A stable launcher process (living outside the swappable code directory) starts the app and can stop it, swap in a staged application directory, run `alembic upgrade head`, and restart — proven by hand-placing a staged directory + a pending marker and watching the launcher swap → migrate → restart, with a failed apply rolling back to the previous code directory and the pre-update database as a matched pair. (PKG-04)
  5. Pushing a version tag runs a GitHub Actions pipeline that builds the distributable and publishes, as release assets, the archive, its SHA-256 checksum, and an Ed25519 minisign signature over the signed asset/manifest; the signature is produced with an OFFLINE secret key and verifies against the public key vendored into the client. (PKG-05)

**Plans**: 5 plans (4 waves)

Plans:
**Wave 1**

- [x] 31-01-PLAN.md — Nyquist Wave-0 RED scaffold: test_packaging/test_launcher/test_release_verify pin PKG-03/04/05 contracts (wave 0)
- [x] 31-02-PLAN.md — PKG-03 data-separation seam: root DB/.env/secret_key/device_id/backups under absolute MYORISHOP_DATA_DIR (wave 1)
- [ ] 31-03-PLAN.md — PKG-04 stable launcher: pure swap state machine + Windows adapters + matched-pair rollback (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 31-04-PLAN.md — PKG-01/02/05 build: build_release.py embeddable onedir + manifest/SHA-256 + tag↔version + MyOriShop.iss (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 31-05-PLAN.md — PKG-02/05 pipeline: release.yml draft build + offline-sign runbook + vendored minisign.pub + CI verify (wave 3)

> **Research flag:** Recommend a small spike to settle bundled-runtime strategy (Python embeddable package vs PyInstaller `--onedir`) before committing `build_release.py` — the tradeoff (AV surface, Alembic `versions/` bundling, `._pth` config) is real and version-sensitive. Also verify current SmartScreen / post-2023 CA/B hardware-key code-signing specifics if a cert is ever pursued (deferred for now — installer ships unsigned per PKG-02).

#### Phase 32: In-App Secure Self-Update

**Goal**: Build the security-critical in-app self-update on top of Phase 31 — the client checks GitHub Releases, verifies a downloaded update's signature AND checksum before unpacking, notifies the administrator and applies only on explicit confirmation, takes a pre-update backup then migrates with rollback on any failure, ties the visible header version to the installed release with integer-scheme anti-downgrade, and is a hard no-op on the PostgreSQL central server. This is the threat-modelled phase where fetched code is executed — verification is a hard gate.
**Depends on**: Phase 31 (bundled runtime, stop/swap/restart launcher, signed release format — none of this is testable without two real signed releases from Phase 31)
**Requirements**: UPD-01, UPD-02, UPD-03, UPD-04, UPD-05, UPD-06, UPD-07
**Success Criteria** (what must be TRUE):

  1. On startup with an active internet connection the client checks the project's latest GitHub Release and detects when a newer version exists; with no connection it is a silent no-op that never blocks offline launch, the administrator can trigger the same check on demand from Настройки («Проверить обновления»), and on the central PostgreSQL server the entire update path is a hard no-op gated on the SQLite dialect. (UPD-01, UPD-06, UPD-07)
  2. Before any downloaded update is unpacked, the client verifies both its SHA-256 checksum AND its Ed25519 signature over the signed asset/manifest (not the mutable git tag) against the vendored public key; a verification failure aborts the update and nothing is applied. (UPD-02)
  3. The operator is shown the available new version and its release notes and the update is applied ONLY on explicit confirmation («Обновить и перезапустить»), with a «Позже» defer option — never a silent auto-apply. (UPD-03)
  4. Applying an update takes a pre-update backup (via the existing VACUUM INTO backup), runs `alembic upgrade head`, and on any failure — verification, migration, or a failed post-update health check — rolls back to the previous code and the pre-update database as a matched pair, so the operator's data is never left half-migrated or lost. (UPD-04)
  5. The visible header version reflects the actually-installed release, and version comparison is done on the integer counter of the "1.<N>" scheme (never string compare) so only a strictly-newer release is ever offered (anti-downgrade). (UPD-05)

**Plans**: TBD
**UI hint**: yes

> **Research flag:** Security-critical — this phase carries a threat model (`security_enforcement=true`, ASVS L1). The signed-manifest-vs-SHA256SUMS shape, the exact minisign verify call, and the launcher/app IPC contract (`pending.json` + controlled-shutdown signal) warrant a focused design pass. Flag `/gsd-plan-phase 32 --research-phase` for the trust model and controlled-shutdown protocol. Reuses shipped mechanisms unchanged (`backup.create_backup()` VACUUM INTO pre-update anchor, the `engine.dialect.name == "sqlite"` server no-op gate, the `_auto_sync_loop` background-loop shape, the `APP_VERSION` header / `app/__init__.py` `__version__`).

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24 → 25 → 26 → 27 → 28 → 29 → 30 → 31 → 32

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
| 31. Packaging, Launcher & Signed-Release Pipeline | v4.0 | 2/5 | In Progress|  |
| 32. In-App Secure Self-Update | v4.0 | 0/TBD | Not started | - |
