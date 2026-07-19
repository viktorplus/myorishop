# Requirements: MyOriShop — Milestone v3.0 (Multi-Operator Sync, Central Server & Roles)

**Defined:** 2026-07-18
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

**Milestone goal:** Turn the single-operator local app into a multi-operator system built around a central PostgreSQL server. The server hosts two online interfaces (browser + mobile). A local desktop client keeps working offline and syncs online when internet is available; when it isn't, work accumulates and is carried on a USB flash drive as a self-contained file that uploads itself to the server from any internet computer — no install required. Everything is gated behind mandatory login with an administrator/operator split.

## v3.0 Requirements

Requirements committed to this milestone. Each maps to exactly one roadmap phase (see Traceability).

### Authentication (AUTH)

- [x] **AUTH-01**: User must log in with a login and password before reaching any page — on the local desktop client and on both of the server's interfaces (browser and mobile).
- [x] **AUTH-02**: Passwords are stored only as Argon2id hashes — never in plaintext or a reversible form.
- [x] **AUTH-03**: A logged-in session persists across browser refresh via a signed cookie, and the user can log out to end it.
- [x] **AUTH-04**: On first run with no users yet, the app guides creation of an initial administrator account (no default credentials are shipped).
- [x] **AUTH-05**: HTMX POST forms are protected against CSRF.

### User Accounts & Attribution (USER)

- [x] **USER-01**: Each user has a profile with a display name, login, and role.
- [x] **USER-02**: An administrator can create a new user and assign their role.
- [x] **USER-03**: An administrator can deactivate a user (soft-disable) without deleting them, so the user can no longer log in but their past operations stay attributed.
- [x] **USER-04**: An administrator can reset another user's password.
- [x] **USER-05**: Every operation and cash movement records the logged-in user as its author, stamped at the single `record_operation()` write path.
- [x] **USER-06**: The History page shows the operating user for each entry and can be filtered by user.

### Roles & Access Control (ROLE)

- [x] **ROLE-01**: Exactly two roles exist — administrator and operator — assigned per user.
- [x] **ROLE-02**: Every protected route enforces a server-side role guard — the local client's routes, the server's browser and mobile interfaces, and the `export`/`backup` endpoints — menu hiding alone is never the boundary.
- [x] **ROLE-03**: An operator can perform receipts, sales, write-offs/returns/corrections, cash movements, and sync; administrator-only sections (user management, warehouses, dictionaries, settings) are hidden and blocked for operators.
- [x] **ROLE-04**: An administrator has full access — user management, warehouses, dictionaries, settings, reports — plus every operator action.

### Central Server & PostgreSQL (SRV)

- [x] **SRV-01**: The same data models and single Alembic migration history run unchanged on both SQLite (client) and PostgreSQL (server).
- [x] **SRV-02**: The central server runs on PostgreSQL and enforces the same append-only ledger guarantee (UPDATE/DELETE of ledger rows blocked at the database) as the SQLite client.
- [ ] **SRV-03**: The local desktop client keeps working fully offline on local SQLite; the central server is required only for sync/upload, never for day-to-day local work.
- [ ] **SRV-04**: The central server hosts two online web interfaces — a browser (desktop) UI and a mobile UI. The mobile version is server-only: there is no local/offline mobile install; mobile users always work against the server online.

### Synchronization — Online & Core (SYNC)

- [x] **SYNC-01**: When internet is available, the local desktop client syncs with the central server via a manual «Синхронизировать» action — pushing its operations and cash movements up and pulling server-authoritative reference data down.
- [x] **SYNC-02**: The server merges the append-only ledgers by UUID with idempotent replay — re-syncing or re-uploading the same data twice changes nothing (no duplicated operations, no double-counted stock).
- [x] **SYNC-03**: After any merge, derived stock quantities and cash balances are recomputed so counts and figures stay correct.
- [x] **SYNC-04**: Online sync and the offline self-upload file use one shared exchange format and one server-side merge engine (never two divergent implementations).
- [x] **SYNC-05**: The central server is the source of truth for mutable reference data (products, customers, warehouses, batches, dictionary) — conflicting edits from different devices resolve to the server's version, including a defined rule for duplicate `Product.code` created on two devices.
- [ ] **SYNC-06**: The sync UI shows sync status, last-sync time, and a plain-language result; a sync failure never blocks local work.
- [ ] **SYNC-07**: The app shows a badge with the count of local operations not yet synced to the server.
- [ ] **SYNC-08**: The operator can enable an optional interval-based automatic sync that runs in the background and silently stops attempting while offline; when disabled, only the manual button syncs.
- [ ] **SYNC-09**: The client authenticates to the server's sync endpoints with a per-device token.

### Offline Data Transfer (OFF)

The offline path is upload-only: a local client with no internet accumulates work, then ships it to the server via a self-contained file carried on a USB flash drive to any internet-connected computer — no app installation required there.

- [ ] **OFF-01**: When the local desktop client has no internet, it keeps recording operations normally and accumulates everything not yet uploaded to the server.
- [ ] **OFF-02**: The operator can export all not-yet-uploaded data to a single self-contained file on a USB flash drive with no internet connection.
- [ ] **OFF-03**: The self-contained file requires NO application installation on the internet-connected computer — the operator opens it (leading approach: an HTML file opened in any browser; final mechanism decided in phase research) and it uploads its own data to the central server.
- [ ] **OFF-04**: The self-uploading file authenticates to the server with a login and password before uploading; a wrong credential is rejected with a clear message and no data is sent.
- [ ] **OFF-05**: The server ingests the uploaded file through the same idempotent UUID merge as online sync — uploading the same file twice changes nothing, and an interrupted upload never leaves a half-applied batch (all-or-nothing on the server).
- [ ] **OFF-06**: Before uploading, the file shows the operator a preview of what will be sent (count of operations/records) and requires an explicit confirm.
- [ ] **OFF-07**: The server validates every uploaded file (integrity checksum + schema-version compatibility) and rejects a tampered or incompatible file with a clear message.

### Reports (RPT)

- [x] **RPT-01**: Reports (sales, profit, and other period reports) can be filtered by operator.

## Future Requirements (deferred)

Acknowledged but out of this milestone's scope. Moving any to v3.0 requires a roadmap update.

### Roles & Auth

- **AUTH-V2-01**: A third "report viewer" role with read-only access to reports.
- **AUTH-V2-02**: Idle session timeout / auto-lock after inactivity.

### Currency

- **CUR-V2-01**: Multi-currency support (prices, reports, cash by currency).

### Customer Intelligence

- **CST-V2-01**: Customer purchase-frequency analysis and "running low" reminders.
- **CST-V2-02**: On goods receipt, suggest customers likely interested in the product based on purchase history.

### Export & Mobile

- **EXP-V2-01**: CSV export includes warehouse/batch columns.
- **MOB-V2-01**: Mobile CRUD parity (warehouses, products/catalog, customers, dictionary, full reports).

## Out of Scope

Explicitly excluded for this milestone. Documented to prevent scope creep. Most are anti-features surfaced by the v3.0 research.

| Feature | Reason |
|---------|--------|
| Multi-currency | Deferred to a separate milestone (operator decision, 2026-07-18); single currency as today |
| A local/offline mobile install | Mobile is server-only (SRV-04); the offline client is desktop-only |
| Installing any app on the internet-connected computer for upload | The offline transfer is a self-contained file that uploads itself — no install (OFF-03) |
| Pulling server data down via the offline USB path | Offline transfer is upload-only; pulling reference data happens on online sync (SYNC-01) |
| Interactive per-row conflict-resolution UI | Server-authoritative resolution chosen; append-only ledgers have no conflicts to resolve |
| Real-time / continuous multi-master sync | Manual + optional-interval sync is sufficient for a handful of operators; avoids background-job infrastructure |
| Syncing derived stock/batch quantities or cash balance directly | Caches are always recomputed from the ledger after merge — shipping them risks corruption |
| Password policies / rotation / lockout / 2FA / email-based reset | Over-engineered for a few trusted operators on trusted machines; admin resets passwords directly |
| Self-service registration | Accounts are administrator-created only |
| Custom / dynamic roles or a permission matrix | Exactly two fixed roles (administrator, operator) |
| Hard-deleting users | Soft-deactivate preserves operation attribution and audit history |
| Selective / partial sync | Full sync only — simpler and correct at this data scale |
| CRDTs / Kafka / Celery / Redis | Unjustified complexity; sync is set-union-by-UUID + recompute |

## Traceability

Which phases cover which requirements. Each v3.0 requirement maps to exactly one phase (roadmap created 2026-07-18).

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 25 | Complete |
| AUTH-02 | Phase 25 | Complete |
| AUTH-03 | Phase 25 | Complete |
| AUTH-04 | Phase 25 | Complete |
| AUTH-05 | Phase 25 | Complete |
| USER-01 | Phase 25 | Complete |
| USER-02 | Phase 25 | Complete |
| USER-03 | Phase 25 | Complete |
| USER-04 | Phase 25 | Complete |
| USER-05 | Phase 25 | Complete |
| USER-06 | Phase 25 | Complete |
| ROLE-01 | Phase 25 | Complete |
| ROLE-02 | Phase 25 | Complete |
| ROLE-03 | Phase 25 | Complete |
| ROLE-04 | Phase 25 | Complete |
| RPT-01 | Phase 25 | Complete |
| SRV-01 | Phase 26 | Complete |
| SRV-02 | Phase 26 | Complete |
| SYNC-02 | Phase 27 | Complete |
| SYNC-03 | Phase 27 | Complete |
| SYNC-04 | Phase 27 | Complete (one engine proven on SQLite + PostgreSQL in the pg-parity CI job, 27-04) |
| SYNC-05 | Phase 27 | Done |
| SRV-04 | Phase 28 | Pending |
| SYNC-09 | Phase 28 | Pending |
| SYNC-01 | Phase 29 | Complete |
| SYNC-06 | Phase 29 | Pending |
| SYNC-07 | Phase 29 | Pending |
| SYNC-08 | Phase 29 | Pending |
| SRV-03 | Phase 29 | Pending |
| OFF-01 | Phase 30 | Pending |
| OFF-02 | Phase 30 | Pending |
| OFF-03 | Phase 30 | Pending |
| OFF-04 | Phase 30 | Pending |
| OFF-05 | Phase 30 | Pending |
| OFF-06 | Phase 30 | Pending |
| OFF-07 | Phase 30 | Pending |

**Phase → Requirements summary:**

- **Phase 25 — Authentication, Roles & User Attribution:** AUTH-01..05, USER-01..06, ROLE-01..04, RPT-01 (16)
- **Phase 26 — PostgreSQL Portability & Append-Only Parity:** SRV-01, SRV-02 (2)
- **Phase 27 — Shared Idempotent Merge Core:** SYNC-02, SYNC-03, SYNC-04, SYNC-05 (4)
- **Phase 28 — Central Server (Hosting & Sync API):** SRV-04, SYNC-09 (2)
- **Phase 29 — Online Client Sync:** SYNC-01, SYNC-06, SYNC-07, SYNC-08, SRV-03 (5)
- **Phase 30 — Offline Self-Uploading File:** OFF-01..07 (7)

**Coverage:**

- v3.0 requirements: 36 total (AUTH×5, USER×6, ROLE×4, SRV×4, SYNC×9, OFF×7, RPT×1)
- Mapped to phases: 36 ✓
- Unmapped: 0 ✓ (every requirement maps to exactly one phase, no duplicates)

---
*Requirements defined: 2026-07-18*
*Last updated: 2026-07-18 — roadmap created; 36/36 requirements mapped to Phases 25-30*
