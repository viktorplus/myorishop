---
phase: 30
plan: 01
subsystem: offline-self-uploading-file
tags: [testing, nyquist, wave-0, scaffold, offline]
requires:
  - anon_client REAL-guard TestClient fixture (tests/conftest.py)
  - settings.secret_key (app/config.py)
  - merge.serialize_exchange / parse_exchange / FORMAT_VERSION (app/services/merge.py)
  - rate_limit.reset_buckets / SYNC_BUCKET_CAPACITY (app/services/rate_limit.py)
provides:
  - tests/test_offline.py Wave-0 RED test map (18 tests) for OFF-01..07
  - shared helpers _offline_ndjson / _mint_offline_token / _seed_admin / _offline_login (+_op/_ops_count/_seed_unsynced_op)
  - the offline-token contract (salt "offline-upload", scope "offline_upload") Wave-1 offline.py must honour
affects:
  - app/services/offline.py (Wave 1 — mint/verify token, schema_version_ok, OFFLINE_TOKEN_TTL)
  - app/routes/offline.py (Waves 2-3 — login/upload/export routes, MAX_OFFLINE_BYTES, current_schema_version)
  - app/services/sync_client.py (Wave 1 — promote _collect_push_records → public collect_push_records)
  - app/services/merge.py (Wave 1 — add payload_sha256 to serialize_exchange header)
tech-stack:
  added: []
  patterns:
    - "RED-by-design Wave-0 scaffold: not-yet-built modules imported INSIDE test bodies so collection stays green"
    - "REAL-guard anon_client (not the auth_guard-override client) so the /api/offline/ bypass is genuinely exercised"
key-files:
  created:
    - tests/test_offline.py
  modified: []
decisions:
  - "payload_sha256 computed over record lines only, LF-joined (D-08) — the exact digest the upload route must verify"
  - "offline token = URLSafeTimedSerializer(secret_key, salt='offline-upload').dumps({scope, sub}) (D-03) — pinned as the Wave-1 service contract"
  - "added test_upload_oversized_body_rejected to cover threat T-30-09 (mitigate) though not an explicit RESEARCH test-map row"
metrics:
  duration: ~8min
  tasks: 2
  files: 1
  completed: 2026-07-20
---

# Phase 30 Plan 01: Offline Test Scaffold Summary

Wave-0 Nyquist scaffold: `tests/test_offline.py` seeds 4 shared helpers, an autouse rate-limit fixture, and the full 18-test RED map for OFF-01..07 (plus token / auth-guard-bypass / `</script>`-escaping / CRLF / rate-limit rows), each pinned to the wave that turns it green. No production code changed.

## What Was Built

**Task 1 — helpers + fixtures (commit c167bbb):**
- `_offline_ndjson(records, *, schema_version="", ...)` — builds the NDJSON body exactly as `serialize_exchange` will, computing `payload_sha256` over the record lines only (LF-joined), the D-08 integrity contract the upload route verifies before any DB touch.
- `_mint_offline_token(user_id)` — `URLSafeTimedSerializer(settings.secret_key, salt="offline-upload").dumps({"scope": "offline_upload", "sub": user_id})`, the exact contract Wave-1 `app/services/offline.mint_offline_token` must honour.
- `_seed_admin`, `_offline_login`, plus `_op` / `_ops_count` / `_seed_unsynced_op` support helpers.
- `_fresh_buckets` autouse fixture calls `rate_limit.reset_buckets()` so the rate-limit test cannot leak.
- Module-level imports touch only already-existing symbols; `app.routes.offline` / `app.services.offline` / the promoted `collect_push_records` / `merge.payload_digest` are imported INSIDE the test bodies.

**Task 2 — RED test map (commit 3819b37), 18 tests:**
- Login handshake (OFF-04 / T-30-07): `test_login_success_mints_token`, `test_login_wrong_password_no_token` (asserts no token AND no data echo), `test_login_rate_limited`.
- Ingest (OFF-05 / OFF-07, via the REAL-guard `anon_client` so the bypass is exercised): `test_upload_twice_is_noop`, `test_upload_all_or_nothing` (mirrors `test_push_all_or_nothing` — IntegrityError propagates, zero rows persist), `test_upload_corrupted_checksum_rejected`, `test_upload_incompatible_schema_rejected` (409, both versions named), `test_upload_empty_server_schema_skips_gate`, `test_upload_bad_format_version_rejected`, `test_upload_expired_token_rejected`, `test_upload_oversized_body_rejected`, `test_crlf_payload_digest_matches`.
- Bypass narrowness (T-30-06): `test_offline_bypass_is_narrow` — session-guarded export (anon → 303 /login) + token-gated ingest (a browser session is not an upload bypass).
- Export/serializer unit (OFF-01/02/03/06, T-30-08): `test_export_header_counts_present`, `test_export_does_not_stamp_synced_at`, `test_export_bundle_fk_closure_complete`, `test_export_html_contains_embedded_payload_and_form`, `test_script_tag_escaping_round_trip`.

## Verification

- `uv run pytest tests/test_offline.py --collect-only -q` → **18 tests collected, zero import/collection errors**.
- `uv run pytest --ignore=tests/test_offline.py -q` → **1122 passed, 12 skipped** (the expected green baseline — no regression).
- The 18 offline tests are intentionally RED until their implementing waves (30-02..30-04); per the plan, this plan is NOT gated on them passing.

## Deviations from Plan

### Auto-added functionality

**1. [Rule 2 - Missing coverage] Added `test_upload_oversized_body_rejected`**
- **Found during:** Task 2
- **Reason:** Threat register T-30-09 (DoS, disposition `mitigate`) references an oversized-body test mirroring `test_push_rejects_oversized_body`, but the RESEARCH Requirements→Test Map (Task 2's authoritative source) does not list it as a named row. Added it to keep the mitigation provable, monkeypatching `app.routes.offline.MAX_OFFLINE_BYTES` to a tiny cap.
- **Files modified:** tests/test_offline.py
- **Commit:** 3819b37

## Notes for Downstream Waves

- **30-02** must add `payload_sha256` to `serialize_exchange`'s header and promote `_collect_push_records` → public `collect_push_records`; the export unit tests import the public name.
- **30-03** must expose `current_schema_version`, `MAX_OFFLINE_BYTES` and the RU result strings on `app.routes.offline` (the schema/oversized tests monkeypatch those module attributes), and `OFFLINE_TOKEN_TTL` on `app.services.offline` (the expired-token test monkeypatches it). Result HTML must contain the locked substrings «Файл повреждён», «Файл собран для версии данных», «Время на загрузку истекло».
- **30-04** owns `GET /offline/export` (session-guarded, embeds `<script type="application/x-ndjson">` + a form to `/api/offline/upload`, escapes `</script>` → `<\/script>`).

## Self-Check: PASSED
