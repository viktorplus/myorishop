---
phase: 30
plan: 02
subsystem: offline-self-uploading-file
tags: [offline, contracts, wave-1, integrity, token, auth-guard]
requires:
  - merge.serialize_exchange / FORMAT_VERSION (app/services/merge.py)
  - sync_client._collect_push_records D-13 FK-closure collector (app/services/sync_client.py)
  - security.auth_guard + SYNC_PATH_PREFIX bypass (app/services/security.py)
  - settings.secret_key (app/config.py)
  - itsdangerous (already installed — zero new packages)
provides:
  - merge.payload_digest(record_lines) — the ONE integrity checksum (D-08)
  - payload_sha256 header field emitted by serialize_exchange (OFF-07 emit side)
  - sync_client.collect_push_records (public; promoted from _collect_push_records, SYNC-04)
  - security.OFFLINE_PATH_PREFIX + exact-prefix auth_guard bypass (D-05)
  - app/services/offline.py — mint_offline_token / verify_offline_token / schema_version_ok (D-03/D-09)
affects:
  - app/routes/offline.py (30-03 — upload/login routes verify the token + digest + schema gate)
  - app/routes/offline.py (30-04 — export route consumes collect_push_records + serialize_exchange)
tech-stack:
  added: []
  patterns:
    - "ONE digest impl (payload_digest) shared by serializer emit + upload verify — SYNC-04 applied to the checksum (D-08)"
    - "itsdangerous URLSafeTimedSerializer with a dedicated salt namespaces the upload token away from the session cookie (D-03)"
    - "exact-prefix auth_guard bypass /api/offline/ (never bare /api/), mirroring the SYNC_PATH_PREFIX guarantee (D-05)"
key-files:
  created:
    - app/services/offline.py
  modified:
    - app/services/merge.py
    - app/services/sync_client.py
    - app/services/security.py
    - tests/test_merge.py
decisions:
  - "payload_digest over LF-joined record lines only, header excluded — the exact digest the 30-03 upload route verifies (D-08)"
  - "OFFLINE_TOKEN_TTL = 300s + scope 'offline_upload' claim; verify raises on expiry/tamper/wrong-scope (D-03)"
  - "schema_version_ok skips the gate when server_schema == '' (create_all fixtures have no alembic_version), else exact match (D-09)"
  - "OFFLINE_PATH_PREFIX bypass sits immediately after the SYNC branch; CSRF deliberately not applied (in-body token, T-30-10)"
metrics:
  duration: ~12min
  tasks: 3
  files: 5
  completed: 2026-07-20
---

# Phase 30 Plan 02: Offline Foundation Contracts Summary

Interface-first Wave-1: landed the four shared contracts every later Phase-30 wave consumes — (1) the `payload_sha256` NDJSON header field via a single pure `payload_digest` helper (OFF-07 emit / D-08), (2) the public `collect_push_records` so offline export and online push share ONE unsynced collector (SYNC-04), (3) the exact-prefix `/api/offline/` `auth_guard` bypass (D-05), and (4) the new pure `app/services/offline.py` minting/verifying the short-lived upload-scoped token (D-03) and gating the schema version (D-09). All additive, zero new packages, no migration.

## What Was Built

**Task 1 — payload_digest + payload_sha256 header (commit a7e7c24):**
- Added `import hashlib` and a pure `payload_digest(record_lines: list[str]) -> str` to `app/services/merge.py` — `hashlib.sha256("\n".join(record_lines).encode("utf-8")).hexdigest()`, the ONE checksum impl shared by the serializer (emit) and the 30-03 upload route (verify), so the two can never diverge (D-08).
- `serialize_exchange` now materializes the record JSON lines into a list first, computes `payload_sha256 = payload_digest(record_lines)`, adds it to the header dict (digest over record lines ONLY, header excluded, exact emission order), then yields the header followed by the pre-built lines. No change to existing key order or record-line format — online push ignores the extra field.
- Added `test_payload_digest_matches_serialized_record_lines` and `test_payload_digest_empty_is_sha256_of_empty_string` to `tests/test_merge.py` (the empty-list → SHA-256-of-empty-string case had no prior coverage).

**Task 2 — public collect_push_records (commit f06d1a3):**
- Renamed `_collect_push_records` → public `collect_push_records` in `app/services/sync_client.py` (same signature, same D-13 FK-closure body — no behaviour/selection change) and updated the single `run_sync_once` call site. `grep -rn "_collect_push_records" app/` returns nothing. Offline export (30-04) and online push now share ONE collector (SYNC-04).

**Task 3 — /api/offline/ bypass + offline service (commit 2ad39e3):**
- `app/services/security.py`: added `OFFLINE_PATH_PREFIX = "/api/offline/"` (exact prefix, never bare `/api/`; the `/offline/export` page is deliberately NOT under it and stays session-guarded) with a bypass branch `if request.url.path.startswith(OFFLINE_PATH_PREFIX): return` immediately after the SYNC branch. CSRF deliberately not applied — in-body token, no cookie (T-30-10). Updated the `auth_guard` docstring with step 3b.
- `app/services/offline.py` (new, pure): `OFFLINE_TOKEN_TTL = 300`, `OFFLINE_TOKEN_SCOPE = "offline_upload"`, module-level `_signer = URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")`, and `mint_offline_token` / `verify_offline_token` (raises `SignatureExpired`/`BadSignature` on expiry/tamper/wrong-scope) / `schema_version_ok` (empty-server skip, else exact match).

## Verification

- `uv run pytest tests/test_merge.py -x -q` → **35 passed** (round-trip tests intact + 2 new digest tests).
- `uv run pytest tests/test_sync_client.py tests/test_sync_ui.py -x -q` → **30 passed** (no behaviour change from the rename).
- `uv run pytest tests/test_sync_api.py tests/test_auth.py -q` → **24 + 28 passed** (SYNC bypass unchanged; the new offline branch causes no auth regression).
- Inline check of `app/services/offline.py`: token round-trip returns `{scope, sub}`; a wrong-scope claim → `BadSignature`; an expired token → `SignatureExpired`; `schema_version_ok("x","")` True, `("x","y")` False, `("x","x")` True.
- Full suite: **1127 passed, 12 skipped, 15 failed** — all 15 failures are the RED-by-design `tests/test_offline.py` route/ingest tests pending 30-03/30-04 (exactly as the plan's `<verification>` states). Baseline was 1122 passed; the +5 are the 2 new merge tests plus 3 export-collector unit tests (`test_export_header_counts_present`, `test_export_does_not_stamp_synced_at`, `test_export_bundle_fk_closure_complete`) that this wave turned green. Zero regressions outside test_offline.py.

## Deviations from Plan

None — plan executed exactly as written. Task 1 was `tdd="true"`; the Wave-0 scaffold already supplied the RED tests (`test_export_header_counts_present`, `test_crlf_payload_digest_matches`), and the two `tests/test_merge.py` unit tests added here directly prove `payload_digest` (including the empty-list edge case) per the plan's `<files>` list.

## Notes for Downstream Waves

- **30-03** (ingest routes) must import `merge.payload_digest` (verify with `"\n".join(payload.splitlines()[1:])` canonicalization, Pitfall 1), `offline.verify_offline_token` / `offline.schema_version_ok`, and expose `current_schema_version`, `MAX_OFFLINE_BYTES` + the RU result strings on `app.routes.offline`; the expired-token test monkeypatches `app.services.offline.OFFLINE_TOKEN_TTL`.
- **30-04** (export route, `GET /offline/export`, session-guarded — NOT under `/api/offline/`) consumes the public `collect_push_records` + `serialize_exchange`; ignore the returned ids (D-07 never stamps `synced_at`).
- `test_offline_bypass_is_narrow` stays RED until 30-04 adds the `/offline/export` route (the guard 404s an unmatched path rather than 303-redirecting, so part (a) needs the route to exist).

## Self-Check: PASSED
