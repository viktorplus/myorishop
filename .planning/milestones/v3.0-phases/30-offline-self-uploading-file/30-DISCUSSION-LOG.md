# Phase 30: Offline Self-Uploading File - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-20
**Phase:** 30-offline-self-uploading-file
**Areas discussed:** File format, Ingest endpoint + auth, Marking as uploaded, Integrity/schema-version
**Mode:** advisor (research-backed comparison tables; calibration tier `standard`; 4 parallel gsd-advisor-researcher agents)

---

## Area 1 — File format & self-contained mechanism (OFF-02/03)

| Option | Description | Selected |
|--------|-------------|----------|
| B: HTML + form-POST | Single self-contained HTML; NDJSON embedded in `<script type=application/x-ndjson>`; uploads via top-level `<form>` POST → zero CORS; server renders result page | ✓ |
| A: HTML + fetch | `fetch()` to absolute URL, reads JSON report in-page; needs a dedicated `Access-Control-Allow-Origin: null` endpoint | |
| C: .ndjson + server-hosted page | Bare NDJSON data file + a server uploader page (same-origin); simplest but not "self-uploading" — spurns OFF-03 intent | |

**User's choice:** B: HTML + form-POST
**Notes:** Chosen to avoid loosening the online-sync API's CORS posture. Payload embedded per Option D sub-choice (script block, not base64). → D-01/D-02.

---

## Area 2 — Ingest endpoint + authentication (OFF-04/05)

| Option | Description | Selected |
|--------|-------------|----------|
| 1: Two-step (login→token→upload) | New `POST /api/offline/login` (login+password → short-lived signed token), then `POST /api/offline/upload`; data sent only after auth confirmed | ✓ |
| 2: Single-shot (creds+payload) | Login+password+NDJSON in one body; simpler but transmits data regardless — violates OFF-04 "no data on failure" | |
| ~~3: Session cookie~~ | Reuse Phase 25 session; rejected — `file://` `Origin: null` + `SameSite` break cross-origin cookies | (rejected pre-vote) |
| ~~4: Reuse `/api/sync/push` (Bearer)~~ | Wrong auth model (device token, not login+password); rejected by OFF-04 | (rejected pre-vote) |

**User's choice:** 1: Two-step (login→token→upload)
**Notes:** Only option that literally honors OFF-04's "sends NO data on failure". OFF-05 atomicity/idempotency reuses `apply_merge` + the `sync_push` owned-transaction pattern. → D-03/D-04/D-05.

---

## Area 3 — Marking data as uploaded, no return channel (OFF-01)

| Option | Description | Selected |
|--------|-------------|----------|
| C: Don't mark (baseline) | Offline path never stamps `synced_at`; only a future online sync clears it; zero data-loss risk; badge stays inflated | ✓ |
| B: Receipt file | Server emits a receipt of acknowledged UUIDs; operator carries it back and imports → honest badge; needs 2nd USB trip + import UI | |
| A: Optimistic on export | Stamp `synced_at` at export time; badge zeroes immediately but risks silent data loss if upload fails/never happens | |

**User's choice:** C: Don't mark (baseline)
**Notes:** Correctness > cosmetic badge. Verified: online driver stamps `synced_at` only after 2xx (`sync_client.py:377`), so C self-heals if the client ever gets internet; permanently-offline clients keep an inflated badge (flagged for UAT; escalate to B if it confuses the operator). → D-07.

---

## Area 4 — File integrity + schema-version validation (OFF-07)

| Option | Description | Selected |
|--------|-------------|----------|
| 2: SHA-256 in header | Plain SHA-256 of NDJSON payload (stdlib hashlib) + exact `schema_version` match; catches silent in-string corruption; no new deps | ✓ |
| 1: No checksum | Only schema_version + strict parse/apply_merge; zero code but silent value corruption merges undetected | |
| ~~3: HMAC~~ | Keyed hash; rejected — client-generated file has no server secret to sign with; false security | (rejected pre-vote) |

**User's choice:** 2: SHA-256 in header
**Notes:** Closes the one gap the pipeline misses (byte-flip inside a valid JSON string). Version rule bundled: `format_version` exact (already in `parse_exchange`); `schema_version` exact at the OFF-07 layer with both-version message; empty server version = skip. → D-08/D-09.

---

## Claude's Discretion

- Login-token TTL/scope and minter internals (reuse `itsdangerous`).
- Script-block embedding details; result-page HTML/wording for each outcome.
- Checksum header field name (`payload_sha256`); schema-version gate location.
- Optional read-only "offline-exported, not confirmed" UI hint (never stamps `synced_at`).
- Preview counts wording/layout; export-file naming/location on USB.

## Deferred Ideas

- Receipt-file round-trip (Option B, Area 3) — revisit only if UAT shows the inflated badge confuses the operator.
- Optimistic mark-on-export (Option A) — rejected (data-loss), recorded so it is not re-proposed.
- HMAC-signed files — rejected (no client-held secret).
- `fetch()` + dedicated `ACAO: null` endpoint (Option A, Area 1) — only if in-page structured report proves necessary.
- Compression of the export file — out of scope; never for integrity.
- Any PULL/two-way sync over USB — explicitly out of scope (upload-only).
