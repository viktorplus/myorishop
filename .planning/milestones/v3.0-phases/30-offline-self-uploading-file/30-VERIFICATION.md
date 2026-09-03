---
phase: 30-offline-self-uploading-file
verified: 2026-07-20T16:25:18Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification_closed: 2026-08-09
human_verification:
  - test: "Open the exported HTML file in a real browser on an internet-connected PC with no MyOriShop install"
    expected: "The file opens and renders (no external CSS/JS/font loads); login + upload completes end-to-end without any application installed"
    why_human: "Requires a second internet-connected machine with no MyOriShop install; cannot be exercised by TestClient (OFF-03)"
    result: pass
    closed_by: "30-UAT.md test 1 (2026-08-09, after fix 380387a)"
  - test: "In the opened file, verify the client-side preview and the confirm gate"
    expected: "Preview counts render from the embedded NDJSON header BEFORE any network call; nothing POSTs to the server until the «Отправить на сервер» confirm button is clicked; a wrong login shows the inline error and transmits no payload"
    why_human: "The preview render + no-post-until-confirm behaviour runs in browser JS; automated tests verify the embedded markup + JS source but not the live in-browser interaction (OFF-06/OFF-04)"
    result: pass
    closed_by: "30-UAT.md test 2 (2026-08-09, after fix 380387a)"
---

# Phase 30: Offline Self-Uploading File Verification Report

**Phase Goal:** Ship the upload-only offline path last, reusing the proven Phase 27 engine — the client exports all not-yet-uploaded work to a single self-contained file on a USB drive that, opened on any internet computer with no app installed, authenticates with login/password, shows a preview, and uploads its own data through the same idempotent merge, with server-side integrity and schema-version validation.
**Verified:** 2026-07-20T16:25:18Z
**Status:** passed (human items closed 2026-08-09 — see 30-UAT.md)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | Offline client accumulates unsynced work and exports it to a single self-contained USB file (OFF-01, OFF-02) | ✓ VERIFIED (code) | `GET /offline/export` (offline.py:86-137) calls shared read-only `collect_push_records` (sync_client.py:256) → `serialize_exchange`; renders one self-contained `self_upload.html` (inline CSS, embedded NDJSON, no `<link>`/CDN). Tests: `test_export_bundle_fk_closure_complete` (FK closure product/batch/sale/customer/warehouse), `test_export_does_not_stamp_synced_at` (D-07 read-only), `test_export_header_counts_present`. 20/20 offline tests green. |
| 2 | File opens in any browser with no install and authenticates login+password; wrong credential rejected clearly, no data sent (OFF-03, OFF-04) | ✓ VERIFIED (code) — browser-open needs human | `POST /api/offline/login` (offline.py:140-179) takes ONLY login+password (no payload field → no data on failure, D-04); generic `BAD_CREDENTIALS_ERROR`, rate-limited, narrow `_ACAO` scoped to login only. Tests: `test_login_wrong_password_no_token`, `test_login_success_mints_token`, `test_login_rate_limited`. Self-containment (no-install open) confirmed in markup; live browser open = human item. |
| 3 | File shows a preview of counts before uploading and requires an explicit confirm (OFF-06) | ✓ VERIFIED (code) — browser render needs human | Header carries a `counts` map (`test_export_header_counts_present`); `self_upload.html:114-219` embeds the NDJSON in a non-executable `<script type="application/x-ndjson">`, renders the preview from `header.counts` before any network call, and gates the top-level POST form behind the «Отправить на сервер» confirm button. Live in-browser preview/confirm = human item. |
| 4 | Server ingests via the same idempotent UUID merge — double-upload is a no-op, interrupted upload is all-or-nothing (OFF-05) | ✓ VERIFIED | `POST /api/offline/upload` (offline.py:182-273) is a thin caller of `apply_merge` inside one owned `with session.begin()`. Tests: `test_upload_twice_is_noop` (replay inserts nothing), `test_upload_all_or_nothing` (poisoned FK → whole batch rolled back, zero rows). |
| 5 | Server validates every file (integrity checksum + schema-version) and rejects tampered/incompatible files clearly (OFF-07) | ✓ VERIFIED | Gate order in offline.py:197-250: token → size cap → canonicalize → SHA-256 digest (D-08) → schema gate (D-09) → parse_exchange, all BEFORE any DB write. Tests: `test_upload_corrupted_checksum_rejected` («Файл повреждён»), `test_upload_incompatible_schema_rejected` (409 names both versions), `test_upload_bad_format_version_rejected`, `test_upload_empty_server_schema_skips_gate`. |

**Score:** 5/5 truths verified (all code-observable portions). Two truths (OFF-03 browser open, OFF-06 in-browser preview/confirm) carry a residual browser-only behaviour that only a human can confirm.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/offline.py` | Pure token mint/verify + schema gate | ✓ VERIFIED | `mint_offline_token`/`verify_offline_token` (itsdangerous, salt `offline-upload`, TTL 300s, scope check), `schema_version_ok` (empty-server skip + exact match). Pure, no DB/HTTP. |
| `app/services/merge.py` | `payload_digest` + `payload_sha256` header | ✓ VERIFIED | Pure `payload_digest` (merge.py:528) over record lines only; emitted in `serialize_exchange` header (merge.py:579). |
| `app/services/security.py` | `/api/offline/` exact-prefix guard bypass | ✓ VERIFIED | `OFFLINE_PATH_PREFIX = "/api/offline/"` (line 65); bypass branch after the SYNC branch (line 184); `/offline/export` stays session-guarded. |
| `app/services/sync_client.py` | Public shared `collect_push_records` | ✓ VERIFIED | Promoted to public (line 256); `run_sync_once` calls it (line 351); no `_collect_push_records` reference survives (grep clean). |
| `app/routes/offline.py` | login + upload + export routes, RU constants, `_result` helper | ✓ VERIFIED | All three routes + `_result` + RU constants + `MAX_OFFLINE_BYTES`; wired in main.py:226 with no `dependencies=`. |
| `app/templates/offline/self_upload.html` | Standalone uploader (inline CSS, embedded NDJSON, preview+login+confirm JS) | ✓ VERIFIED | Fully inline, no external refs; `2px solid #2563eb` focus outline present; case-preserving `</script>` reverse. |
| `app/templates/offline/result.html` | 5-state no-session RU result page | ✓ VERIFIED | success/corrupted/incompatible/expired states with locked RU copy; version strings autoescaped. `wrong_password` branch is dead (IN-01, cosmetic). |
| `app/templates/pages/export.html` | S3 CTA + empty-URL error state | ✓ VERIFIED | «Экспортировать офлайн-файл» CTA + `sync_configured` guard fed from `export_page` (export.py:27). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `offline_upload` | `apply_merge` | `session.rollback(); with session.begin(): apply_merge(...)` | ✓ WIRED | offline.py:257-259, owned transaction, verbatim sync_push idiom |
| `offline_upload` | `payload_digest` + `schema_version_ok` + `verify_offline_token` | route-layer gates before parse/merge | ✓ WIRED | offline.py:199,229,236 |
| `offline_login` | `verify_password` + `check_rate_limit` + `mint_offline_token` | credential handshake | ✓ WIRED | offline.py:160,167,178 |
| `offline_export` | `collect_push_records` + `serialize_exchange` | records → embedded NDJSON | ✓ WIRED | offline.py:112-120 |
| `self_upload.html` | `{server}/api/offline/upload` | top-level confirm-gated form | ✓ WIRED | self_upload.html:101-108 |
| `auth_guard` | `OFFLINE_PATH_PREFIX` | `startswith` branch after SYNC | ✓ WIRED | security.py:184 |
| CORS `_ACAO` | login responses only | scoped header | ✓ WIRED | grep: `Access-Control-Allow-Origin` appears ONLY in offline.py — /api/sync/ posture untouched (D-05) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline requirement→test coverage | `uv run pytest tests/test_offline.py -q` | 20 passed | ✓ PASS |
| CR-01 mixed-case `</script>` regression | `test_script_tag_escaping_round_trip_mixed_case` | passed | ✓ PASS |
| WR-01 Unicode line-separator regression | `test_upload_unicode_line_separator_round_trips` | passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| OFF-01 | 30-01, 30-02, 30-04 | ✓ SATISFIED | read-only export collector, no synced_at stamp |
| OFF-02 | 30-01, 30-02, 30-04 | ✓ SATISFIED | single self-contained file, FK closure complete |
| OFF-03 | 30-01, 30-04 | ✓ SATISFIED (code) | self-contained HTML, embedded form; browser no-install open = human |
| OFF-04 | 30-01, 30-02, 30-03 | ✓ SATISFIED | login-only endpoint, generic reject, no data on failure |
| OFF-05 | 30-01, 30-03 | ✓ SATISFIED | idempotent + all-or-nothing via apply_merge |
| OFF-06 | 30-01, 30-04 | ✓ SATISFIED (code) | counts header + confirm-gated form; in-browser preview = human |
| OFF-07 | 30-01, 30-02, 30-03 | ✓ SATISFIED | SHA-256 + schema gate before any DB touch |

All seven OFF-* IDs appear in plan frontmatter, in REQUIREMENTS.md (lines 59-65, all `[x]`, all mapped Phase 30 Complete), and in the VALIDATION Nyquist test map. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| offline.py / offline service | — | Debt markers (TODO/FIXME/XXX) | ℹ️ None | grep clean in both files |
| result.html | 20-22 | Dead `wrong_password` branch | ℹ️ Info (IN-01) | Unreachable; login is a JSON endpoint. Cosmetic, no impact on goal. |
| offline.py | 246-259 | Parseable-but-poisoned batch raises IntegrityError → HTTP 500 (not RU page) | ⚠️ Warning (WR-02) | DELIBERATELY DEFERRED — the plan's `test_upload_all_or_nothing` asserts the raise propagates as the rollback proof; all-or-nothing IS achieved (zero rows persist). UX-only contract mismatch on an untrusted PC. Not a blocker. |
| offline.py | 197-201 | Upload token accepted for full TTL after user deactivation | ⚠️ Warning (WR-03) | DELIBERATELY DEFERRED to `/gsd-secure-phase 30`. Blast radius small (single-operator, 300s window, server-wins merge). Not a goal blocker. |

CR-01 (case-sensitive `</script>` neutralization — script-injection BLOCKER) was FIXED: offline.py:128-130 uses `re.sub(..., flags=re.IGNORECASE)` with a case-preserving replacement; JS reverse at self_upload.html:153 is `/<\\\/(script)/gi` → `</$1`. Regression test `test_script_tag_escaping_round_trip_mixed_case` green. Commit ba02d29. WR-01 (splitlines over-split on U+2028/U+2029) FIXED at offline.py:215 (`.replace("\r\n","\n").replace("\r","\n").split("\n")`); regression `test_upload_unicode_line_separator_round_trips` green. Commit 5ae888e.

### Human Verification — CLOSED 2026-08-09

Both items below were executed live in a real browser and are recorded as `result: pass`
in `30-UAT.md`. The first run found a BLOCKER (literal `</script` inside the live logic
script's own JS comments prematurely terminated the `<script>` element, so the preview
was empty and the JS leaked as page text); it was fixed in commit `380387a` and pinned by
`tests/test_offline.py:591 test_logic_script_block_has_no_raw_end_tag`. The re-run on a
regenerated export served from a separate origin was green on every checkpoint: the page
GET was the ONLY network request, the preview rendered «Операции 23 / Товары 7 /
Покупатели 2 / Партии 4 / Продажи 6 / Движения кассы 26», a wrong password produced
«Неверный логин или пароль. Данные не отправлены.» with only `POST /api/offline/login`
401 and no `/upload`, the confirm button gated the POST, and the confirmed upload returned
`POST /api/offline/upload` 200 with server rows 0→23 operations and 0→26 cash movements.

**1. Self-uploading file opens with no app install on an internet PC (OFF-03)** — ✓ PASS
- **Test:** Copy an exported `myorishop-offline-*.html` from a USB drive to a second internet-connected computer that has no MyOriShop installed; open it in any browser.
- **Expected:** The page renders fully (no blocked external CSS/JS/font requests); login + upload completes end-to-end against the central server.
- **Why human:** Requires a separate internet-connected machine with no app install; TestClient cannot exercise `file://` browser behaviour.

**2. In-browser preview counts + explicit confirm gate (OFF-06 / OFF-04)** — ✓ PASS
- **Test:** In the opened file, observe the «Будет отправлено» preview before touching the network; enter a wrong password, then a correct one; watch the confirm step.
- **Expected:** Counts render from the embedded header with no network call; a wrong login shows the inline RU error and sends no payload; nothing POSTs until «Отправить на сервер» is clicked.
- **Why human:** The preview render and no-post-until-confirm behaviour execute in browser JS; automated tests verify the embedded markup and JS source but not the live interaction.

### Gaps Summary

No blocking gaps. All five success criteria and all seven OFF-* requirements are satisfied in the codebase, backed by 20 passing requirement-mapped tests. The security spine is sound: exact-prefix guard bypass, scoped CORS (sync posture provably untouched), short-lived scoped token, SHA-256 + schema gates before any DB write, and read-only export that never stamps `synced_at`. The one code-review BLOCKER (CR-01) and the first warning (WR-01) were fixed and carry regression tests; WR-02 and WR-03 are documented deliberate deferrals (WR-02 is an intentional rollback-proof design with a matching test; WR-03 belongs to the pending `/gsd-secure-phase 30`).

Two success criteria (OFF-03, OFF-06) contained a browser-only behaviour — opening the file with no install and the live JS preview/confirm gate — that only a human could confirm. Both were exercised live on 2026-08-09 and passed (one BLOCKER found and fixed in `380387a`, regression pinned), so the phase status is now **passed**.

The one remaining phase-level tail is `/gsd-secure-phase 30` (security_enforcement is on, the plans carry threat models T-30-01..10, and no `30-SECURITY.md` exists yet). Code-review warning WR-03 (an upload token stays valid for its 300 s TTL after the user is deactivated — threat T-30-04) was deliberately deferred to that run.

---

_Verified: 2026-07-20T16:25:18Z_
_Verifier: Claude (gsd-verifier)_
_Human items closed: 2026-08-09 (see 30-UAT.md; fix commit 380387a)_
_Status updated to passed: 2026-09-03 by /gsd-verify-work 30_
