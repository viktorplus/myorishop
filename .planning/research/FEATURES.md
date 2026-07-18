# Feature Research

**Domain:** Local-first inventory app gaining multi-operator sync (online + USB), mandatory auth, and admin/operator roles
**Researched:** 2026-07-18
**Confidence:** MEDIUM-HIGH (web-informed UX best practices + established auth/RBAC/local-first patterns; no exotic libraries required)

> Scope note: this file covers ONLY the v3.0-new behavior — Sync (online + USB), Auth/Users, Roles, and per-operator attribution. The existing local warehouse/sales/finance app (v1.0–v2.0) is treated as a fixed foundation, not re-researched. Multi-currency is explicitly out of scope.

---

## Foundation the milestone builds on (already shipped)

These existing facts change what is "table stakes" vs "hard" for v3.0. Cite them when scoping.

- **Append-only operation ledger** with `record_operation()` as the single write path (Phase 1, D-rule). This is THE sync foundation and THE attribution hook. Sync = ship ledger rows; attribution = stamp the row.
- **Per-row `device_id`** already exists on ledger rows (states machine identity — "which client").
- **`created_by` / `created_at`** already present on the ledger (Phase 1), but `created_by` today is effectively a constant/device placeholder — v3.0 must repoint it at a real user.
- **UUID-per-entity pattern** recommended in STACK (integer PK + `uuid` text column) — dedup key for sync. Must be confirmed present on synced tables (add where missing) before online/USB merge can be idempotent.
- **Stock counts are a derived cache**, recomputed from the ledger — never a source of truth. Critical: sync moves ledger rows, then recomputes stock; it never syncs quantities directly.
- **Настройки hub** (Phase 24) — the natural home for both a Sync page and User Management.
- **Backups via `VACUUM INTO`** (Phase 3) — file-handling/offline mechanics to reuse for the USB exchange file (distinct feature, shared plumbing).
- **History with type-adaptive columns** (Phase 23) — an operator column slots in cheaply.
- **Dedicated mobile flow** (Phase 11) — login + a sync trigger must reach mobile parity.
- **PostgreSQL portability** (STACK) — the server is the same models with a connection string; the client stays on SQLite.

---

## Feature Landscape

### Table Stakes (Users Expect These)

#### Sync

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Manual **«Синхронизировать»** button | A non-technical operator wants to press one button and know data is exchanged; explicit beats invisible | MEDIUM | Primary trigger. Runs push-then-pull against the server. Same code path the USB flow reuses. |
| Clear sync **status** (idle → «Синхронизация…» → «Готово» / «Ошибка») | Users must know what's happening; silence reads as "broken" | LOW | HTMX partial swap on the Sync page + a small header indicator. Plain-Russian microcopy, not codes. |
| **Last-sync time** shown («Последняя синхронизация: сегодня 14:32») | Baseline trust signal for any sync UI | LOW | Store per-transport (online / USB) timestamps. |
| **Plain-language result summary** («Отправлено 12, получено 5 операций») | Confirms something actually happened; reassures against data loss | LOW | Count rows pushed/pulled; no jargon. |
| **Offline USB export → file** («Экспорт для обмена») | The literal milestone requirement; the offline transport | MEDIUM | Writes one exchange file (all un-exchanged ledger rows + reference deltas) to a chosen path / flash drive. |
| **Offline USB import** («Импорт обмена») | Other half of the USB flow | MEDIUM | Reads an exchange file, merges by UUID, recomputes stock. Same merge engine as online pull. |
| **One exchange format for both directions and both transports** | Prevents two divergent, separately-buggy code paths | MEDIUM | A single versioned envelope (schema_version + rows). Online push/pull and USB export/import all speak it. |
| **Idempotent re-apply** (import the same file twice → nothing changes) | Non-technical users double-click, re-insert the same flash drive | MEDIUM | Dedup by operation UUID. This is the single most important correctness property of the whole milestone. |
| **Offline-safe failure** (sync error never blocks local work) | The app was local-first for two years; that promise must hold | LOW | Sync errors are surfaced and dismissible; the local DB keeps working with no network. |

#### Authentication

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Login screen** (login + password), mandatory before any page | This milestone introduces the first security boundary; multi-operator implies "who are you" | MEDIUM | Server-rendered form; unauthenticated requests redirect to `/login`. |
| **Logout** | Universally expected | LOW | Clears the session cookie. |
| **Password hashing** (bcrypt or argon2) | Non-negotiable; plaintext/weak hashing is a defect, not a choice | LOW | Use `passlib`/`argon2` or `bcrypt`. Never store or log plaintext. |
| **Signed session cookie** | Standard session mechanism for server-rendered FastAPI | LOW | Starlette `SessionMiddleware` / itsdangerous-signed cookie. No JWT needed. |
| **Self-service password change** | Expected once a login exists | LOW | Requires current password + new. |
| **First-run admin bootstrap** | On upgrading a no-auth app, someone must become the first admin without a hardcoded default password | MEDIUM | First launch on the new schema forces creation of the initial administrator. No default credentials shipped. |

#### Roles & Users

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Two fixed roles: administrator, operator** | The stated requirement | LOW | Enum on the user row. No dynamic role system. |
| **Role-based menu hiding** | Operators shouldn't see admin surfaces (Настройки, Склады, Справочник, Users) | LOW | Template gates on role. UX layer only — see next row for the real boundary. |
| **Server-side route guards on every protected route** | Menu hiding is cosmetic; the actual security boundary is per-request authorization | MEDIUM | A dependency/guard on each router. Operator hitting an admin URL directly gets 403, not the page. Both this AND menu hiding are required. |
| **Admin user management** (create user, assign role, deactivate, reset password) | An admin with no way to manage users is incomplete | MEDIUM | CRUD under Настройки. Deactivate ≠ delete (see below). Password reset sets a new password directly — no email. |
| **Deactivate (not delete) users** | Ledger rows reference the user; deleting orphans historical attribution | LOW | Soft flag; deactivated users can't log in but stay referenced in history. |

#### Attribution

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Real `created_by` = the logged-in user** on every operation | Once >1 operator exists, "who did this" is the whole point | LOW | Stamp inside `record_operation()` from the session. The single choke point makes this a one-place change. |
| **Operator shown in History** | "Who sold this / who wrote this off" is the first question in a multi-user shop | LOW | Add an operator column to the existing type-adaptive History (Phase 23). |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Conflict-free-by-design sync** | Because the ledger is append-only and UUID-keyed, operations interleave by timestamp instead of overwriting — so there is essentially nothing to "resolve" for operational data | MEDIUM | This is the milestone's structural advantage: it turns the hardest part of most sync projects into a dedup + recompute. Sell it, protect it (see anti-features). Only *mutable reference data* needs a policy. |
| **Last-write-wins on reference data** (product names, reference prices, dictionaries), server authoritative | The one place edits genuinely collide; a simple timestamp rule avoids a conflict UI entirely | MEDIUM | Compare `updated_at`; newest wins; server breaks ties. Predictable, no user prompt. |
| **Unsynced-count badge** («3 операции не отправлены») | Ambient reassurance that pending work is tracked, without forcing a sync | LOW | Count ledger rows not yet acknowledged by the server / not yet exported. |
| **"What will change" preview before applying a USB import** | A non-technical operator sees «Будет добавлено 5 операций, обновлено 2 товара» before committing — undo-anxiety killer | MEDIUM | Dry-run the merge, show counts, then confirm. High trust-per-effort. |
| **Filter History/Reports by operator** | Answers "how much did each person sell", "who made this correction" | LOW | Reuses existing History filters (Phase 23) + reports period filter; add operator facet. |
| **Optional automatic/background sync on app start + interval** (opt-in) | Convenience for the online case once manual sync is trusted | MEDIUM | Keep manual as primary and always available; auto is a toggle in Настройки. Must degrade silently offline. |
| **USB exchange integrity check** (schema_version + checksum in the envelope) | Rejects a truncated/foreign file with «Файл обмена повреждён или несовместим» instead of corrupting data | LOW | A header field + hash; not cryptography. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Interactive per-row conflict resolution UI** ("keep mine / keep theirs") | Sounds like the "proper" way to do sync | The append-only ledger design deletes the need — operations don't conflict, they coexist. Building the UI re-introduces the complexity the architecture avoided, and confuses a non-technical operator | Auto-dedup by UUID for operations; last-write-wins for reference data. No prompts. |
| **Real-time / continuous multi-master sync** (WebSockets, CRDT libraries, live cursors) | "Modern" sync feels instant | Enormous complexity and moving parts for operators who sync a few times a day across countries; battery/bandwidth cost; nothing needs sub-second freshness | Manual button + optional interval sync. Batch, not stream. |
| **Syncing stock quantities / balances directly** | Seems like the obvious thing to keep in step | Stock is a derived cache; syncing it invites divergence and double-counting. The ledger is the truth | Sync ledger rows only; recompute stock locally after every merge. |
| **Password policies, rotation, lockout, 2FA/MFA, email verification** | "Security best practice" reflex | Enterprise auth sprawl for a 2-role, few-operator, trusted-machine app; friction with zero threat-model justification here; no email infra exists | Strong hashing + admin-set/admin-reset passwords + a signed session. Keep it minimal. |
| **Self-service registration + forgot-password-via-email** | Standard SaaS onboarding | Users are created by the admin; there's no mail server, and self-signup breaks the closed-team model | Admin creates accounts and resets passwords directly in Настройки. |
| **A dynamic permission matrix / custom roles / third "report-viewer" role now** | "Flexibility for the future" | Exactly two roles are specified; a permission editor is pure overhead and a bug surface. Report-viewer is on the deferred Future list, not this milestone | Hard-code two roles. Add report-viewer later if actually needed. |
| **Deleting users** | Housekeeping instinct | Breaks historical attribution (ledger references the user) | Deactivate (soft); keep the record for history. |
| **PKI-signed / encrypted USB exchange files** | "The file is sensitive" | Key management is a rabbit hole for a non-technical operator; the flash drive is physically carried by the same trusted person | A version header + integrity checksum. Physical custody is the security model. |
| **Selective / partial sync** (choose warehouses/date ranges to sync) | "Give me control" | Splits the dataset, breaks idempotency guarantees, confuses users | Sync everything; the ledger is small and dedup makes re-sync free. |
| **Aggressive idle session timeout** | "Auto-lock is secure" | On a single trusted local machine it mostly annoys; forces re-login mid-work | Long-lived / "remember me" session by default; provide explicit Logout. Make timeout an optional admin setting, off by default. |

---

## Feature Dependencies

```
[User accounts (Auth)]
    ├──requires──> [First-run admin bootstrap]
    ├──enables───> [Roles: administrator / operator]
    │                   └──requires──> [Server-side route guards]  (the real boundary)
    │                   └──enhanced-by─> [Role-based menu hiding]  (UX only)
    └──enables───> [Real created_by attribution]
                        └──requires──> [record_operation() choke point]   (EXISTS, Phase 1)
                        └──enables───> [Operator column + filter in History/Reports]

[Sync (online + USB)]
    ├──requires──> [UUID on every synced entity]   (pattern EXISTS; verify/add columns)
    ├──requires──> [Append-only ledger + record_operation()]   (EXISTS, Phase 1)
    ├──requires──> [Single versioned exchange format]
    │                   ├──used-by──> [Online push/pull (PostgreSQL server)]
    │                   └──used-by──> [USB export/import]
    ├──requires──> [Stock recompute-from-ledger after merge]   (recompute EXISTS)
    └──enhanced-by─> [Central PostgreSQL server]   (online transport only; USB works without it)

[created_by attribution] ──enriches──> [Sync]   (each synced row carries WHO + which device_id)
[Interactive conflict UI] ──conflicts-with──> [Append-only conflict-free design]   (do not build)
```

### Dependency Notes

- **Roles require user accounts, and route guards are the real boundary:** menu hiding without server-side guards is a false sense of security. Both ship together, guards being the non-optional half.
- **Attribution requires the `record_operation()` choke point (already exists):** stamping `created_by` from the session in one place is why attribution is LOW complexity — no scatter-gun edits across every operation type.
- **Both sync transports must share one exchange format:** if online and USB diverge into two merge algorithms, one will silently be less correct. The format/merge engine is the core deliverable; online and USB are just two ways to move the same envelope.
- **Sync requires UUIDs actually present, not just recommended:** the STACK note prescribes UUIDs; before any merge ships, confirm every synced table has one, or idempotent dedup is impossible. This is a pre-flight, not an assumption.
- **USB sync does not depend on the server:** client↔client (or client↔server) file exchange works with no PostgreSQL online. This lets USB ship independently of / before online.
- **The conflict UI conflicts with the architecture:** listed as a dependency edge specifically to flag that building it undoes the append-only advantage.

---

## MVP Definition

### Launch With (v3.0 core)

Minimum to deliver "multi-operator system with roles and both sync transports."

- [ ] **Auth: login/logout + hashed passwords + signed session** — the security boundary the whole milestone rests on.
- [ ] **First-run admin bootstrap** — upgrade path from the no-auth app; without it nobody can log in.
- [ ] **User profiles (name, login, role) + admin user management** (create / assign role / deactivate / reset password) — required to have more than one operator.
- [ ] **Two roles with server-side route guards + menu hiding** — the administrator/operator split.
- [ ] **Real `created_by` attribution + operator column in History** — the point of knowing "who".
- [ ] **Single versioned exchange format + idempotent UUID merge + stock recompute** — the sync engine.
- [ ] **USB export/import** — the offline transport (ships first; no server needed).
- [ ] **Online push/pull against the central PostgreSQL server + manual «Синхронизировать» button** — the online transport, with status + last-sync time + plain-language result.
- [ ] **Offline-safe failure + mobile parity for login and sync trigger** — preserve the local-first promise across desktop and mobile.

### Add After Validation (v3.x)

- [ ] **"What will change" preview before USB import** — add once base merge is trusted; strong anxiety-reducer.
- [ ] **Unsynced-count badge** — after the manual flow proves stable.
- [ ] **Optional automatic/interval background sync** — convenience once manual online sync is proven and trusted.
- [ ] **Filter Reports (not just History) by operator** — after attribution ships and per-operator questions arise.

### Future Consideration (v4+ / already deferred)

- [ ] **Third "report-viewer" role** — deferred (Future list AUTH-V2-01); only if a read-only stakeholder actually appears.
- [ ] **Multi-currency** — explicitly out of scope this milestone.
- [ ] **Optional idle session timeout / auto-lock** — only if a shared-machine scenario emerges.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Login/logout + hashed session auth | HIGH | MEDIUM | P1 |
| First-run admin bootstrap | HIGH | MEDIUM | P1 |
| User management (CRUD, role, deactivate, reset) | HIGH | MEDIUM | P1 |
| Two roles + route guards + menu hiding | HIGH | MEDIUM | P1 |
| Real `created_by` + operator in History | HIGH | LOW | P1 |
| Exchange format + idempotent UUID merge + stock recompute | HIGH | HIGH | P1 |
| USB export/import | HIGH | MEDIUM | P1 |
| Online push/pull + manual sync button + status/last-sync | HIGH | HIGH | P1 |
| Last-write-wins on reference data | MEDIUM | MEDIUM | P1 (needed for correctness of ref edits) |
| Offline-safe failure + mobile parity | HIGH | LOW-MEDIUM | P1 |
| "What will change" import preview | MEDIUM | MEDIUM | P2 |
| Unsynced-count badge | MEDIUM | LOW | P2 |
| Filter Reports by operator | MEDIUM | LOW | P2 |
| Automatic/interval background sync | MEDIUM | MEDIUM | P2 |
| USB integrity/version check | MEDIUM | LOW | P2 |
| Interactive conflict-resolution UI | LOW (negative) | HIGH | P3 — do NOT build |
| Password policies / 2FA / email reset | LOW (negative) | HIGH | P3 — do NOT build |

**Priority key:** P1 must-have for the milestone · P2 add after core validates · P3 avoid / far future.

---

## Concrete User-Facing Behavior (for requirements authoring)

**(a) Sync UX.** Primary trigger is a manual **«Синхронизировать»** button on a Sync page under Настройки (and reachable on mobile). Pressing it: pushes local un-acknowledged ledger rows to the server, pulls new remote rows, dedups by UUID, applies last-write-wins to reference edits, recomputes stock, and shows «Готово · отправлено N, получено M» plus updates «Последняя синхронизация: …». Errors show one plain-Russian line and never block local work. Because operations are append-only and UUID-keyed, the operator is **never** asked to resolve a conflict; the only silent policy is newest-wins on product/dictionary edits.

**(b) Offline USB exchange.** Under the same page: **«Экспорт для обмена»** writes one file (e.g. to `E:\` flash drive); the operator carries it to the other machine and picks **«Импорт обмена»**, selects the file, optionally sees a "what will change" count, confirms, and the exact same merge runs. The same envelope format is what the online transport ships — one algorithm, two carriers. Re-importing the same file is a safe no-op.

**(c) Authentication.** App opens to a **«Вход»** screen (логин + пароль). On the very first launch after upgrade, it instead demands creation of the first administrator. A signed session cookie keeps the operator logged in (long-lived / "remember me" by default; explicit **«Выход»**). Users change their own password from their profile; there is no email reset — the admin resets it.

**(d) Role-gated behavior.** An **operator** sees only operational surfaces (Приход, Продажи, Списание, Касса, История, and their own profile); Настройки, Склады, Справочник, and User Management are hidden AND blocked server-side (direct URL → 403). An **administrator** additionally sees user management (create user, assign administrator/operator, deactivate, reset password), warehouses, dictionaries, settings, and reports.

**(e) Per-operator attribution.** Every operation records the logged-in user as `created_by` (stamped in the existing `record_operation()`); `device_id` continues to record which machine. History (and later Reports) shows an operator column and can filter by it, so "who sold / wrote off / corrected this" is answerable across machines and countries after sync.

---

## Competitor / Comparable Feature Analysis

| Feature | Typical small-biz SaaS (cloud POS/inventory) | Offline sync tools (file-sync apps) | Our Approach |
|---------|----------------------------------------------|-------------------------------------|--------------|
| Sync model | Always-online, server is source of truth | Continuous file diff + conflict copies | Batch, manual-first; append-only ledger is source of truth, conflict-free by design |
| Conflict handling | Server-authoritative, rare user prompts | "Conflict_" duplicate files for the user to reconcile | No operational conflicts; last-write-wins only on reference data |
| Offline transport | None (cloud required) | Core competency (folders) | First-class USB exchange file sharing the online format |
| Auth | Full accounts, SSO, MFA | OS/account-level | Minimal: hashed password + signed session, admin-managed |
| Roles | Many granular roles/permissions | N/A | Exactly two hard-coded roles |
| Attribution | Per-user audit logs | File-level | Per-operation `created_by` off the existing ledger choke point |

---

## Sources

- WebSearch — local-first / offline-first sync UX (manual trigger, status badges, last-sync, non-technical conflict handling): [Offline-First Architecture (Medium, J. Topic)](https://medium.com/@jusuftopic/offline-first-architecture-designing-for-reality-not-just-the-cloud-e5fd18e50a79), [Offline-First Mobile App Architecture: Syncing, Caching, Conflict Resolution (DEV)](https://dev.to/odunayo_dada/offline-first-mobile-app-architecture-syncing-caching-and-conflict-resolution-518n), [Cool frontend arts of local-first: storage, sync, conflicts (Evil Martians)](https://evilmartians.com/chronicles/cool-front-end-arts-of-local-first-storage-sync-and-conflicts), [A Design Guide for Building Offline First Apps (Hasura)](https://hasura.io/blog/design-guide-to-offline-first-apps), [Offline File Sync: Developer Guide (daily.dev)](https://daily.dev/blog/offline-file-sync-developer-guide-2024/) — MEDIUM confidence.
- Project context: `.planning/PROJECT.md` (v3.0 goal, foundation features, append-only ledger + device_id + UUID pattern) and repo `CLAUDE.md` STACK notes (UUID-for-sync, PostgreSQL portability, session-cookie auth guidance) — HIGH confidence for the existing foundation.
- Established-pattern synthesis (append-only/UUID conflict-free sync, minimal session-cookie auth, two-role RBAC with server-side guards, soft-deactivate for attribution) — MEDIUM-HIGH confidence; standard practice, no exotic dependencies.

---
*Feature research for: multi-operator sync + auth + roles on a local-first FastAPI/SQLite app*
*Researched: 2026-07-18*
