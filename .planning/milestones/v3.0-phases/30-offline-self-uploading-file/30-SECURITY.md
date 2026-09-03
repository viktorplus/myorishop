---
phase: 30
slug: offline-self-uploading-file
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-03
mode: verify-mitigations
register_authored_at_plan_time: true
---

# Phase 30 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 30 opens an **untrusted-file ingest path**: a session-guarded desktop export
> produces ONE self-contained HTML file that, opened on a foreign internet PC with no
> app installed, authenticates with login+password and self-uploads an NDJSON bundle
> through the Phase-27 merge engine. Every mitigation below was VERIFIED present in
> implemented code — documentation and intent were not accepted as evidence. Every
> `mitigate` row cites the exact line that performs the control plus the test that
> proves it; `tests/test_offline.py` was re-run by the auditor on 2026-09-03:
> **21 passed**.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| desktop operator → `GET /offline/export` | Session-guarded (NOT under the ingest bypass); only a logged-in operator can build a bundle | Full unsynced ledger + D-13 FK closure, embedded in an HTML attachment |
| exported file → any browser (`file://`, null origin) | The embedded NDJSON is non-executable data inside a `script type="application/x-ndjson"` block; the HTML-parser breakout vector is neutralized at render | Business records (product/customer names — attacker-influenceable in the v3 multi-operator model) |
| untrusted internet PC → `POST /api/offline/login` | Password crosses here; verified server-side (Argon2id), generic failure, rate-limited, single narrow ACAO header | login + password ONLY (no data field declared) |
| untrusted internet PC → `POST /api/offline/upload` | Attacker-controlled NDJSON crosses here; token + size + digest + schema + format + FK all validated before/inside ONE owned transaction | In-body upload token + NDJSON payload |
| copied `myorishop.db` → device credential | The upload token derives from `settings.secret_key` (config, outside the synced DB), never a DB column | — |
| offline routes ↔ `/api/sync/` CORS posture | The narrow ACAO must stay scoped to `/api/offline/login`; no app-wide CORSMiddleware may exist | — |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (verified evidence) | Status |
|-----------|----------|-----------|-------------|--------------------------------|--------|
| T-30-01 | Tampering | `offline_upload` digest gate (gate 4) | mitigate | Digest verified BEFORE `parse_exchange`/`apply_merge`: `payload_digest(record_lines) != header.get("payload_sha256")` → «Файл повреждён» 400 — `app/routes/offline.py:222-230` (merge is at :248-259). ONE digest impl, LF-join, shared by emit and verify — `app/services/merge.py:528-542`, emitted at `merge.py:579`. **Both sides agree after WR-01:** export joins lines with `"\n"` (`offline.py:113`), ingest canonicalizes on real newline styles ONLY (`\r\n`/`\r`/`\n`), never `str.splitlines()` — `offline.py:215` (commit 5ae888e). **Fail-closed:** a missing `payload_sha256` yields `None != <hex>` → rejected, the gate cannot be skipped by omitting the field. Proofs: `tests/test_offline.py:269` (byte-flip), `:376` (CRLF), `:390` (U+2028) | closed |
| T-30-02 | Integrity | `offline_upload` schema gate (gate 5) | mitigate | `offline_service.schema_version_ok(file_schema, server_schema)` at the route layer, BEFORE parse/merge → 409 naming BOTH versions — `app/routes/offline.py:232-243`. Exact match with empty-server skip — `app/services/offline.py:61-71`; server value is DB-derived, never hardcoded — `app/services/sync.py:225-235`. Both version strings autoescaped, never `| safe` — `app/templates/offline/result.html:26-29`. Proofs: `tests/test_offline.py:289` (409, both versions), `:310` (empty-schema skip), `:325` (bad `format_version` → parse gate) | closed |
| T-30-03 | Info Disclosure | `offline_login` handshake + `self_upload.html` flow | mitigate | The endpoint DECLARES only `login`/`password` — no payload/data parameter exists, so business data cannot reach it on a failed login — `app/routes/offline.py:140-145`. One generic non-enumerating `BAD_CREDENTIALS_ERROR` for unknown login / wrong password / deactivated — `offline.py:60,165-175`. Client side: the credential inputs sit OUTSIDE the upload `<form>` (`self_upload.html:84-95`), the login `fetch` body is `URLSearchParams({login, password})` only (`:187-190`), and the payload form is revealed only on a 2xx token (`:197-203`). Proofs: `tests/test_offline.py:204` (401, no `token`/`records`/`counts` in body); live browser UAT `30-UAT.md` test 2 — wrong password produced only `POST /api/offline/login` 401 with **no `/upload` request** | closed |
| T-30-04 | Spoofing / EoP | offline upload token (gate 1) | mitigate | `verify_offline_token` is the FIRST gate; `SignatureExpired`/`BadSignature` → «Время на загрузку истекло» 401 — `app/routes/offline.py:197-201`. HMAC-timed itsdangerous verify over `settings.secret_key` with dedicated salt `offline-upload`, TTL 300 s, `offline_upload` scope claim enforced, never a bare `==` — `app/services/offline.py:28,31,35,44,55-58`. Proofs: `tests/test_offline.py:345` (expired → 401 + RU page), `:196` (mint), `:412` (garbage token rejected even with a live session cookie). **Residual accepted:** no user-active re-check inside the 300 s window — see AR-30-04 | closed |
| T-30-05 | Elevation | narrow CORS | mitigate | Exactly ONE header dict `_ACAO = {"Access-Control-Allow-Origin": "*"}` — `app/routes/offline.py:67` — applied ONLY on the three `/api/offline/login` responses (`:162` 429, `:174` 401, `:179` 200). **NO `Access-Control-Allow-Credentials` anywhere** (repo grep for `Access-Control` returns only `app/routes/offline.py`). The upload route renders through `_result` (`:72-83`) which adds no CORS header — the bulk upload is a top-level form navigation, not a CORS read. **No app-wide CORSMiddleware:** `app.add_middleware` appears exactly once in `app/main.py:179-184` and it is `SessionMiddleware`; grep for `CORSMiddleware` across `app/` = 0 matches, so the `/api/sync/` posture is provably untouched | closed |
| T-30-06 | Access Control | `auth_guard` OFFLINE_PATH_PREFIX bypass | mitigate | `OFFLINE_PATH_PREFIX = "/api/offline/"` — exact prefix WITH the trailing slash, never a bare `/api/` — `app/services/security.py:64-75`; single branch `request.url.path.startswith(OFFLINE_PATH_PREFIX): return` placed after the SYNC branch — `security.py:194`. **Prefix cannot be fooled:** `/api/offlineX` and `/api/offline` (no trailing slash) do not match `startswith` → stay guarded; the match is case-sensitive so `/API/OFFLINE/…` stays guarded (and matches no route); a dot-segment path like `/api/offline/../products` bypasses the guard but matches no route → 404 (app-level dependencies are per-route, so an unmatched path never reaches a handler). **Bypass surface is exactly 2 routes** (`offline.py:140,182`), each self-gated; the third route `GET /offline/export` (`offline.py:86`) is deliberately outside the prefix and stays session-guarded. Proof: `tests/test_offline.py:412` — (a) anonymous `/offline/export` → 303 `/login`, (b) a REAL session cookie grants nothing on the ingest tree. Tests run on the REAL-guard `anon_client` (`tests/conftest.py:190-217`), not an `auth_guard` override, so the genuine bypass is exercised | closed |
| T-30-07 | Spoofing (brute-force) | `offline_login` rate limit | mitigate | `check_rate_limit(f"offline-login:{login}")` is the FIRST statement after the strip, before any DB lookup → 429 + RU message — `app/routes/offline.py:159-163`; monotonic-clock token bucket, 30 burst / 0.5 rps, thread-safe — `app/services/rate_limit.py:19-47`. Proof: `tests/test_offline.py:216` (429 observed after exhausting `SYNC_BUCKET_CAPACITY`) | closed |
| T-30-08 | Tampering (HTML breakout) | embedded NDJSON in `self_upload.html` | mitigate | **Data path:** rendered into a NON-executable `<script id="payload" type="application/x-ndjson">` — `app/templates/offline/self_upload.html:114`; the escape runs at render BEFORE `| safe`: `re.sub(r"</script", lambda m: "<\\/" + m.group(0)[2:], body, flags=re.IGNORECASE)` — case-INSENSITIVE and case-PRESERVING — `app/routes/offline.py:128-130` (CR-01 fix, commit ba02d29); reversed in JS with `/<\\\/(script)/gi` → `</$1` before parse/submit — `self_upload.html:155`. **Live-script path:** the logic `<script>` body contains no literal `</script` of any case (UAT blocker fix 380387a; the NOTE at `self_upload.html:151-152` records the rule). Proofs: `tests/test_offline.py:528` (lowercase round-trip), `:555` (mixed `</SCRIPT>`/`</Script>` — asserts **no** case-variant end tag survives inside the embed AND byte-identical round-trip), `:591` (`test_logic_script_block_has_no_raw_end_tag` — live logic block clean). Live browser UAT after 380387a: page renders, JS executes, upload 200 (`30-UAT.md`) | closed |
| T-30-09 | DoS | `offline_upload` body cap (gate 2) | mitigate | `MAX_OFFLINE_BYTES = 32 * 1024 * 1024` — `app/routes/offline.py:55` — enforced in-app at `:203-205`, i.e. **before** canonicalization (`:215`), header JSON (`:223`), digest (`:229`), parse (`:248`) and any DB touch; independent of any proxy config. Proof: `tests/test_offline.py:360` (cap monkeypatched tiny → rejected, row count unchanged). Framework adds a stricter outer bound (see IN-04) | closed |
| T-30-10 | Spoofing (CSRF) | offline bypass branch | mitigate / accept | **No session cookie is honoured on `/api/offline/*`:** `auth_guard` returns at `app/services/security.py:194`, BEFORE the session read at `:198`; neither offline route reads `request.session` or `request.state.user` (grep in `app/routes/offline.py` = 0) — the only credentials are the in-body form fields. CSRF is therefore deliberately not applied (D-05, identical reasoning to the Bearer `/api/sync/` tree — `security.py:173-183`). A cross-origin form POST to `/upload` is possible but useless: it carries no forgeable token → 401, and its response is not readable cross-origin (no ACAO on `/upload`). Proof: `tests/test_offline.py:412(b)` — an authenticated browser session + invalid token still cannot upload | closed |
| T-30-SC | Tampering | package installs | **accept** | VERIFIED zero new packages: `git log -- pyproject.toml uv.lock` shows NO phase-30 commit at all (nearest neighbours are `54ff30c` 2026-07-20 `feat(29-01)` and `07a2186` 2026-07-22 `feat(32-02)`); all four SUMMARYs declare `tech-stack: added: []`; `30-RESEARCH.md:119-124` §Package Legitimacy Audit records the gate as not triggered. **Self-uploading file is genuinely self-contained:** grep for `https?://`, `src=`, `@import`, `<link`, `unpkg`, `cdn`, `googleapis`, `.woff` in `app/templates/offline/self_upload.html` matches ONLY the prohibition comment at line 7; all CSS is inline (`:11-64`), all JS is inline (`:116-222`); the sole network egress is the operator's own `server_url`. Live UAT confirms the page GET was the ONLY network request (`30-UAT.md` test 1). See AR-30-SC | closed |
| — (data-loss avoidance) | — | `offline_export` | **accept** | D-07 honoured: the route ignores the collector's id map — `records, _ids = collect_push_records(session)` — `app/routes/offline.py:112`; `synced_at` appears in `app/routes/offline.py` only in the docstring/comment at `:98,111`, never as an assignment (grep). `collect_push_records` is SELECT-only — `app/services/sync_client.py:263-293`; the only `synced_at` write in the codebase's client path is the post-2xx stamp in `run_sync_once` — `sync_client.py:384-390`. Proof: `tests/test_offline.py:458` (`synced_at is None` after building a bundle). See AR-30-D07 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-30-04 | T-30-04 (code-review WR-03) | **Upload token survives user deactivation for its remaining TTL.** `verify_offline_token` validates signature + TTL + scope but the route discards the `sub` claim and never re-checks `is_active` (`app/routes/offline.py:197-201`), whereas the login gate does (`:165-175`) and the session guard revokes immediately (`get_active_user`). Adjudicated **CLOSED-with-accepted-risk**, not OPEN, because: (1) the *declared* mitigation for T-30-04 (300 s TTL + `offline_upload` scope + HMAC verify) is present and proven — nothing planned is missing; (2) the exposure is bounded by an absolute 300 s lifetime, is not renewable, and requires the actor to have held valid credentials at mint time; (3) the granted capability is an append-only, idempotent, server-authoritative `apply_merge` — it can insert ledger rows but cannot read, update or delete anything (`*_no_update`/`*_no_delete` triggers still apply); (4) single-operator deployment (1 user in year one, 1-3 devices), so "deactivated user" is a v3 multi-operator scenario, not a current one; (5) **ASVS L1** contains no requirement for immediate propagation of account deactivation to an already-issued short-lived bearer credential (V3 session requirements target the session token; V8.2/V8.3 timeout controls are satisfied by the 300 s absolute lifetime). Fix cost is ~4 lines (`session.get(User, claim["sub"])` + `is_active` check) and is recorded in `30-REVIEW.md:146-163`. **Revisit trigger:** multi-operator rollout, any TTL increase above 300 s, or the offline path gaining write capability beyond append-only insert. | gsd-security-auditor | 2026-09-03 |
| AR-30-D07 | — (data-loss avoidance, 30-04-PLAN.md `<threat_model>`) | **The offline export never stamps `synced_at`.** Consequence accepted as planned: a permanently-offline client's SYNC-07 unsynced badge stays inflated and re-exports re-include already-uploaded rows (larger files, harmless — the server merge is idempotent). This is the deliberately data-loss-averse choice: a lost, never-uploaded USB file must not silently mark rows as delivered. `synced_at` is cleared only by a confirmed online 2xx (`app/services/sync_client.py:384-390`). Verified read-only in code and by `tests/test_offline.py:458`. Flagged for UAT in `30-04-SUMMARY.md`. | gsd-security-auditor | 2026-09-03 |
| AR-30-SC | T-30-SC | **Supply chain: zero new packages in Phase 30.** No phase-30 commit touches `pyproject.toml` or `uv.lock` (git-verified); every symbol used is stdlib (`hashlib`, `json`, `re`) or an already-locked dependency (`itsdangerous` 2.2.*, `argon2-cffi`, `jinja2`, `fastapi`, `python-multipart`). The self-uploading file uses only baseline browser primitives (`fetch`, `URLSearchParams`, `textContent`, native form POST) — no polyfill, no CDN, no external font/CSS/JS, which is simultaneously a hard product requirement (OFF-03, must work with no install) and the supply-chain control for the client half. | gsd-security-auditor | 2026-09-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Residual / Advisory Notes (non-blocking)

These do NOT reopen any threat — every declared mitigation is present in code.

| Ref | Note | Disposition |
|-----|------|-------------|
| WR-02 | A parseable-but-poisoned batch (missing FK parent) lets `IntegrityError` propagate → HTTP 500 instead of the RU result page (`app/routes/offline.py:252-259`). **Deliberate:** `tests/test_offline.py:249` asserts the raise as the all-or-nothing rollback proof, and zero rows persist. **Auditor judgment on the information-disclosure question asked of this run: no leak.** The app is constructed without `debug=` (`app/main.py:169-173`), so Starlette's `ServerErrorMiddleware` returns a bare `Internal Server Error` body — no traceback, no SQL, no row contents reach the untrusted PC; the detail goes to server logs only. UX-only defect. | advisory |
| IN-02 | Login timing side-channel (`30-REVIEW.md:176-184`): the `user is None or not verify_password(...) or ...` short-circuit (`offline.py:167-172`) skips the deliberately slow Argon2 verify for an unknown login, so response *time* distinguishes unknown-login from wrong-password even though the *body* is a single generic message. Blunted by the per-login rate limit (T-30-07). Not an ASVS L1 requirement (constant-time credential response is not mandated at L1). | advisory |
| IN-03 | The CORS posture has **no automated regression test** — no test in `tests/` asserts `Access-Control-Allow-Origin` presence on `/api/offline/login`, its absence on `/api/offline/upload` and `/api/sync/*`, or the absence of `Access-Control-Allow-Credentials`. T-30-05 is CLOSED on unambiguous code evidence (a literal header dict applied at three explicit call sites; no middleware), but a future refactor could silently widen it. Cheap hardening for a later phase. | advisory |
| IN-04 | Starlette 1.3.1 caps every form field/part at 1 MB (`starlette/formparsers.py:63-64,149,159,184-185`), so a `payload` larger than 1 MB is rejected by the framework with a generic 400 **before** `MAX_OFFLINE_BYTES` (32 MB) is ever reached. Security-wise this is fail-closed and strictly *stronger* than the declared T-30-09 control (peak memory is bounded at 1 MB/part, not 32 MB). Functionally it means a real export bundle above 1 MB would land on a generic 400 rather than the RU result page — a **functional/UAT concern outside this audit's scope**, raised here because it interacts with the declared cap. The live UAT bundle (49 records) was far below the limit. **CONFIRMED EMPIRICALLY by the orchestrator 2026-09-03** with a throwaway probe (4 000 operation records → 1 662 044 B / 1.59 MiB body, since deleted): urlencoded → `400 {"detail":"Field exceeded maximum size of 1024KB."}`, multipart/form-data (what the real browser form sends, `self_upload.html:101`) → `400 {"detail":"Part exceeded maximum size of 1024KB."}`. Both are raw English JSON, not the RU result page, and neither reaches `MAX_OFFLINE_BYTES`. Note `tests/test_offline.py:360` cannot catch this — it monkeypatches the cap down to 10 bytes and posts a tiny body, so the framework bound is never exercised. Security verdict unchanged (fail-closed, generic message, no leak → T-30-09 stays CLOSED), but the offline path breaks functionally at roughly 4 000 accumulated records. **Recommend a follow-up fix** (`max_part_size` raised to `MAX_OFFLINE_BYTES` on an explicit `request.form(...)` call, plus a real oversize regression test). | advisory |
| IN-05 | `auth_guard` calls `issue_csrf(request)` *before* the offline bypass (`security.py:189,194`), so `/api/offline/*` responses carry a `Set-Cookie` for a session containing only a CSRF token. No user identity, no data; cross-origin `fetch` without credentials ignores it. Cosmetic. | advisory |
| IN-06 | The preview panel writes `header.counts` values via `innerHTML` (`self_upload.html:162-169`). Only the six known `RU_LABELS` keys are rendered and each value must satisfy `n > 0`, which coerces non-numeric strings/objects to `NaN` and drops them; the counts map is server-generated by `serialize_exchange` (`merge.py:565-579`). No practical injection vector, but `textContent` would be the stricter idiom. | advisory |

**Auditor judgment at `block_on: high`** — no declared mitigation is absent, weaker than declared, or unreachable. The one deferred security warning routed to this run (WR-03) is adjudicated as an accepted residual with written justification (AR-30-04), not as a silent pass: the planned control is fully implemented, the gap is an *additional* control that was never in the register. No BLOCKER.

---

## Unregistered Flags

**None.** No `## Threat Flags` section exists in `30-01..04-SUMMARY.md`; the auditor read all four in full and mapped every recorded deviation and post-review fix to an existing threat ID:

| Implementation-time surface | Source | Maps to |
|-----------------------------|--------|---------|
| `test_upload_oversized_body_rejected` added (Rule 2, not a RESEARCH test-map row) | 30-01-SUMMARY deviations | T-30-09 (made provable) |
| Non-dict header guard `isinstance(header, dict)` added (`offline.py:226-227`) | 30-03-SUMMARY deviations | T-30-01 (prevents an `AttributeError` 500 that would have echoed internal state) |
| CR-01 case-insensitive `</script>` neutralization (ba02d29) + mixed-case regression | 30-REVIEW critical | T-30-08 |
| WR-01 newline-only canonicalization (5ae888e) + U+2028 regression | 30-REVIEW warning | T-30-01 |
| UAT blocker: literal `</script` in the LIVE logic script (380387a) + `test_logic_script_block_has_no_raw_end_tag` | 30-UAT gaps | T-30-08 |

No new attack surface appeared during implementation without a mapped threat ID.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 12 (11 numbered + 1 unnumbered accept) | 12 | 0 | gsd-security-auditor |

Verification basis: static evidence located by grep in the cited files (no mitigation accepted on documentation or comments alone), plus an independent run of `uv run pytest tests/test_offline.py -q` → **21 passed** (2026-09-03), plus git history for the supply-chain accept, plus the closed live-browser UAT (`30-UAT.md`, 2 passed) for the two browser-only controls (no-install self-containment; no-POST-until-confirm).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-30-04, AR-30-D07, AR-30-SC)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
