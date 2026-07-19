---
phase: 28-central-server-hosting-sync-api
plan: 02
subsystem: auth
tags: [device-token, sync, sha256, soft-revoke, migration, sqlalchemy]
requires: [SRV-02, "0018"]
provides: [SYNC-09, DeviceToken, device-token-service]
affects: [app/models.py, alembic, app/services, tests]
tech-stack:
  added: []
  patterns:
    - "prefix-lookup + sha256 digest token auth (one indexed SELECT + constant-time compare)"
    - "deliberate hasher divergence: sha256 for high-entropy tokens vs Argon2 for passwords"
    - "soft-revoke (is_active=0 + revoked_at), never session.delete — User precedent"
    - "bare user_id column in migration, ORM-only ForeignKey (0017 author_id precedent)"
key-files:
  created:
    - alembic/versions/0019_device_tokens.py
    - app/services/devices.py
    - tests/test_devices.py
  modified:
    - app/models.py
decisions:
  - "SHA-256, not Argon2, for device tokens: a token_urlsafe(32) plaintext carries 256 bits of CSPRNG entropy so a slow KDF buys nothing against brute force while adding ~50-100ms to every sync request (RESEARCH A1)"
  - "No expiry column — revocation only; an expiring token on a 1-3 device app is a silent-failure mode for negligible gain"
  - "token_prefix is a non-secret index key so verification is one row read, not a table scan that hashes every row"
  - "user_id is a bare column in the migration; the ForeignKey lives only in the ORM (Operation.author_id / 0017 precedent) for insert ordering + PG portability"
metrics:
  duration: ~20min
  tasks: 3
  files: 4
  completed: 2026-07-19
---

# Phase 28 Plan 02: Device Token Identity (SYNC-09) Summary

A per-device token credential the sync endpoints will authenticate with: a `device_tokens` table, migration `0019`, and a fat service that mints, verifies, lists and revokes tokens using stdlib primitives only — the plaintext exists solely in `mint_token`'s return value.

## What Was Built

The `DeviceToken` model and its `device_tokens` table (migration `0019`, chained off `0018`) store a **non-secret 12-char `token_prefix`** (an indexed unique lookup key) and a **SHA-256 hex `token_hash`** — never the plaintext. `app/services/devices.py` mints a `myos_` + `secrets.token_urlsafe(32)` token (256 bits CSPRNG), returns the plaintext exactly once, and verifies a presented token in one indexed `SELECT` on the prefix followed by one `hmac.compare_digest` (via `auth.compare_token`) on the digests — no table scan, no per-row hashing, never a bare `==`. Revocation is a soft-disable (`is_active=0` + `revoked_at`); a row is never deleted, so the `device_id`/`user_id` audit trail survives.

Deliberately NOT in this plan (per the objective): the HTTP `require_device` dependency, the `auth_guard` bypass, and the admin UI. This plan is pure model + service, unit-testable with the plain `session` fixture before any app wiring (the Phase 25 Plan 03 precedent).

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | `DeviceToken` model (10 columns, no expiry) + migration `0019` (portable, up/down/up clean, ORM-only FK on `user_id`) | `51b7ade` |
| 2 | `app/services/devices.py` — `mint_token`, `lookup_active_token`, `touch_last_used`, `list_device_tokens`, `revoke_token`, `_digest` | `e10c46b` |
| 3 | `tests/test_devices.py` — 12 SYNC-09 service unit tests | `2bf50db` |

## Key Decisions

- **SHA-256 over Argon2 for device tokens.** A `token_urlsafe(32)` value has 256 bits of entropy — brute force is infeasible regardless of hash speed, so Argon2's deliberate slowness buys nothing and would add ~50-100 ms to *every* sync request. The divergence from the project's Argon2 convention is spelled out in the module docstring so it reads as intentional at review (RESEARCH A1).
- **No expiry column.** Revocation is the only kill switch. On a 1-3 device single-reseller app an expiring token is a silent-failure mode (sync quietly stops) for negligible security gain.
- **Prefix as a non-secret index key.** Storing the first 12 plaintext chars unique+indexed turns verification into one row read instead of a scan that hashes every row — while the actual authentication still rests entirely on the constant-time digest compare (proven by `test_lookup_rejects_a_wrong_token`, which forges a value sharing the prefix and asserts None).
- **Bare `user_id` in the migration.** The `ForeignKey` lives only in the ORM (0004/0008/0017 precedent) for Unit-of-Work insert ordering and PostgreSQL portability; SQLite's ALTER-in constraint limitation is thus avoided.

## Deviations from Plan

None — plan executed exactly as written. No architectural changes, no checkpoints, no auth gates, no new packages (`secrets`/`hashlib` are stdlib; `compare_token` already existed).

## Verification

| Check | Result |
|-------|--------|
| `alembic heads` | `0019 (head)` — single head |
| `alembic upgrade head` → `downgrade 0018` → `upgrade head` | all exit 0 |
| `uv run pytest tests/test_devices.py -q` | **12 passed** |
| `uv run pytest -q` (full SQLite suite) | **1043 passed, 11 skipped** (was 1031 before this plan) |
| `ruff check app/services/devices.py app/models.py alembic/versions/0019_device_tokens.py tests/test_devices.py` | clean |
| `grep -c "hmac" app/services/devices.py` | 0 (constant-time compare reached only via `auth.compare_token`) |
| `grep -Ec 'print\(|logging|logger' app/services/devices.py` | 0 |
| `grep -c "session.delete" app/services/devices.py` | 0 |
| `grep -c "sqlalchemy.dialects" app/services/devices.py` | 0 |
| `grep -Ec '^(from|import) app' alembic/versions/0019_device_tokens.py` | 0 (WR-06) |

## Success Criteria

- [x] `device_tokens` table exists via migration `0019` using portable constructs only; applies and reverses cleanly on SQLite
- [x] Service mints a 256-bit token, returns the plaintext exactly once, stores only its SHA-256 digest
- [x] Verification is one indexed lookup + one constant-time compare; wrong, unknown and revoked tokens all resolve to None
- [x] Revocation is a soft-disable that preserves the row for audit (never `session.delete`)

## Threat Model Coverage

| Threat ID | Disposition | How covered |
|-----------|-------------|-------------|
| T-28-01 (device-token theft) | mitigate | `revoke_token` soft-disable + `touch_last_used` staleness signal; `test_lookup_rejects_a_revoked_token` |
| T-28-07 (plaintext at rest/logs) | mitigate | sha256-only storage, zero print/logging (grep-asserted); `test_mint_returns_plaintext_once_and_stores_only_a_hash` |
| T-28-10 (timing side-channel) | mitigate | prefix SELECT + `compare_token`; `test_lookup_rejects_a_wrong_token` proves prefix alone does not authenticate |
| T-28-17 (weak token generation) | mitigate | `secrets.token_urlsafe(32)`; `test_two_mints_produce_distinct_tokens` |
| T-28-18 (hard-delete audit loss) | mitigate | no `session.delete` (grep-asserted); `test_revoke_soft_disables_and_never_deletes` asserts row count unchanged |
| T-28-SC (supply chain) | accept | zero new packages |

## Known Stubs

None.

## Threat Flags

None. This plan adds no network endpoint (the HTTP dependency is deferred to Plan 03 by design); it adds a token store whose full STRIDE surface is already enumerated in the plan's `<threat_model>` and covered above.

## Notes for Future Plans

- **Plan 03 (`require_device` + sync API)** wires the bearer dependency: parse `Authorization: Bearer <token>`, call `lookup_active_token`, then `touch_last_used` on success. The read path (`lookup_active_token`) never commits — the endpoint owns the `touch` write so it can batch or skip it.
- **Never** put the token in a query string (proxy logs / browser history) — `Authorization: Bearer` only (RESEARCH Pattern 3).
- Any future column on `device_tokens` needs a NEW migration (never edit `0019`) plus the ORM model; the `create_all`-based `session` fixture picks up model changes automatically, so no `APPEND_ONLY_TRIGGERS`-style lockstep applies here (this table has no triggers).

## Self-Check: PASSED

- FOUND: `alembic/versions/0019_device_tokens.py`
- FOUND: `app/services/devices.py`
- FOUND: `tests/test_devices.py`
- FOUND: `app/models.py` (DeviceToken class)
- FOUND: commit `51b7ade`
- FOUND: commit `e10c46b`
- FOUND: commit `2bf50db`
