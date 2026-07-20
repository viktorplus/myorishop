---
phase: 30
slug: offline-self-uploading-file
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-20
finalized: 2026-07-20
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (+ `fastapi.testclient`, `httpx` 0.28.*) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_offline.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~ full suite (1122 passing baseline) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_offline.py tests/test_merge.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green; PG-parity CI must stay green (`apply_merge` runs on PostgreSQL too)
- **Max feedback latency:** ~30 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 0 | OFF-01..07 | — | Shared fixtures/helpers: NDJSON body with a correct `payload_sha256`, direct token minter + expired variant, login-token helper | scaffold | `uv run pytest tests/test_offline.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 30-01-02 | 01 | 0 | OFF-01..07 | T-30-01..10 | RED test bodies for all reqs + token / bypass / `</script>`-escaping / CRLF / rate-limit | scaffold | `uv run pytest tests/test_offline.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 30-02-01 | 02 | 1 | OFF-07 | T-30-01 | `payload_sha256` header emitted over LF-joined record lines only (D-08) | unit | `uv run pytest tests/test_offline.py::test_export_header_counts_present tests/test_merge.py -x -q` | ❌ W0 | ⬜ pending |
| 30-02-02 | 02 | 1 | OFF-01, OFF-02 | — | Promote `_collect_push_records` → public `collect_push_records` (one shared collector, SYNC-04) | unit | `uv run pytest tests/test_sync_client.py tests/test_sync_ui.py -x -q` | ❌ W0 | ⬜ pending |
| 30-02-03 | 02 | 1 | OFF-04, OFF-07 | T-30-04, T-30-06, T-30-09, T-30-10 | `auth_guard` exact-prefix `/api/offline/` bypass + token minter/verifier (TTL+scope) + `schema_version_ok` | integration | `uv run pytest tests/test_offline.py::test_offline_bypass_is_narrow tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 30-03-01 | 03 | 2 | OFF-07 | — | `result.html` (S2, no-session shell) + RU constants + `offline.py` module shell | glue | `uv run python -c "import app.routes.offline; from app.routes import templates; templates.get_template('offline/result.html')"` | ❌ W0 | ⬜ pending |
| 30-03-02 | 03 | 2 | OFF-04 | T-30-03, T-30-05, T-30-07 | `POST /api/offline/login`: creds→token, NO data on failure, narrow CORS, rate-limit | integration | `uv run pytest tests/test_offline.py::test_login_success_mints_token tests/test_offline.py::test_login_wrong_password_no_token tests/test_offline.py::test_login_rate_limited -x -q` | ❌ W0 | ⬜ pending |
| 30-03-03 | 03 | 2 | OFF-05, OFF-07 | T-30-01, T-30-02, T-30-04, T-30-09 | `POST /api/offline/upload`: token → SHA-256 + schema gate → all-or-nothing `apply_merge` (idempotent) | integration | `uv run pytest tests/test_offline.py tests/test_merge.py -x -q` | ❌ W0 | ⬜ pending |
| 30-04-01 | 04 | 3 | OFF-01, OFF-02 | T-30-06 | `GET /offline/export` session-guarded; FK-closure bundle; export reads only (no `synced_at` stamp) | integration | `uv run pytest tests/test_offline.py::test_export_html_contains_embedded_payload_and_form tests/test_offline.py::test_export_bundle_fk_closure_complete tests/test_offline.py::test_export_does_not_stamp_synced_at -x -q` | ❌ W0 | ⬜ pending |
| 30-04-02 | 04 | 3 | OFF-03, OFF-06 | T-30-01, T-30-03, T-30-08 | `self_upload.html` standalone: inline CSS, embedded NDJSON, client preview + login + confirm + form-POST | integration | `uv run pytest tests/test_offline.py::test_export_html_contains_embedded_payload_and_form tests/test_offline.py::test_script_tag_escaping_round_trip -x -q` | ❌ W0 | ⬜ pending |
| 30-04-03 | 04 | 3 | OFF-01, OFF-06 | — | S3 export CTA + empty-`sync_server_url` state + optional read-only hint (never stamps `synced_at`) | integration | `uv run pytest tests/test_offline.py -x -q` | ❌ W0 | ⬜ pending |

*Populated from the plan task list + RESEARCH.md §Validation Architecture Requirements→Test Map. Task IDs are `{plan}-{task}` (e.g. 30-03-03 = plan 30-03, Task 3). `File Exists ❌ W0` = the test lands in Wave 0 (30-01) and is RED-by-design until its implementing wave turns it GREEN.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_offline.py` — stubs covering OFF-01..07 + token/bypass/escaping/CRLF/rate-limit rows
- [ ] Fixture/helper: build a valid offline NDJSON body with a correct `payload_sha256` header, and POST `/api/offline/login` to obtain a token (build on the REAL-guard `anon_client`, mirror `device_client`)
- [ ] Helper: mint an offline token directly (serializer + `settings.secret_key`) for upload tests that skip login, plus an expired-token variant
- [ ] No new framework install — pytest/httpx/TestClient already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| JS client-side preview counts + explicit confirm gate in the browser | OFF-06 | Runs in a real browser on an internet PC; no server round-trip until confirm | Open exported HTML in a browser, verify counts render from embedded NDJSON, confirm nothing POSTs until the confirm button is clicked |
| Self-uploading file opens with no app install on any internet computer | OFF-03 | Requires a second, internet-connected machine with no MyOriShop install | Copy exported HTML from USB to an internet PC, open in a browser, complete login + upload |

*Header `counts` presence (OFF-06 data side) is automated; the JS confirm gate is manual.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (30-01 seeds every test the impl waves reference)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-20 (map finalized from plan tasks; `wave_0_complete` flips to true when Wave 0 lands during execution)
