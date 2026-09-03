---
phase: 30
plan: 04
subsystem: offline-self-uploading-file
tags: [offline, export, self-upload, wave-3, template, session-guarded, ndjson-embed]
requires:
  - sync_client.collect_push_records — public unsynced ledger + D-13 FK closure (app/services/sync_client.py, from 30-02)
  - merge.serialize_exchange — NDJSON header (counts + payload_sha256) + record lines (app/services/merge.py, from 30-02)
  - sync.current_schema_version (app/services/sync.py)
  - settings.sync_server_url / settings.device_id (app/config.py)
  - POST /api/offline/upload + POST /api/offline/login ingest contract (app/routes/offline.py, from 30-03)
  - offline/result.html S2 result page the upload navigation lands on (from 30-03)
provides:
  - "GET /offline/export — session-guarded desktop route: collect_push_records → serialize_exchange → render self_upload.html as an HTML attachment (OFF-01/OFF-02/OFF-03)"
  - app/templates/offline/self_upload.html — standalone self-contained uploader (inline CSS, embedded NDJSON, preview + login fetch + confirm form-POST)
  - "export.html offline-export CTA + blank-URL error state (OFF-02, Pitfall 5)"
affects: []
tech-stack:
  added: []
  patterns:
    - "the export route is deliberately NOT under /api/offline/ — it stays behind the app-level session guard (like /sync/run), so only a logged-in operator can produce the file (T-30-06); the ingest bypass is exact-prefix only (D-05)"
    - "read-only export: collect_push_records ids are IGNORED — the offline path NEVER stamps synced_at (D-07); a lost/never-uploaded file keeps its rows visible"
    - "NDJSON embedded in a non-executable <script type=application/x-ndjson>; </script> → <\\/script> escaped at render, | safe only after that escape, reversed in the browser JS before parse/submit (T-30-08/Pitfall 2/6)"
    - "server_url embedded via an HTML attribute (data-server + form action, autoescaped) and read back through dataset — never inside a JS string literal"
    - "two-step handshake in inline vanilla JS: creds fetched first (x-www-form-urlencoded simple request); the payload form is revealed and submitted only after a confirmed login + an explicit confirm click (OFF-04/OFF-06/D-10)"
key-files:
  created:
    - app/templates/offline/self_upload.html
  modified:
    - app/routes/offline.py
    - app/routes/export.py
    - app/templates/pages/export.html
decisions:
  - "blank sync_server_url → the export route re-renders pages/export.html with sync_configured=False (RU error-block) instead of downloading a dead file (Pitfall 5) — one consistent guard shared by the CTA and the route"
  - "the embedded payload <script> uses id BEFORE type so the substring `type=\"application/x-ndjson\">` sits immediately before `>`, matching the round-trip test's extraction marker"
  - "optional read-only 'exported, not yet uploaded' hint OMITTED — no clean data source exists without reading/writing synced_at (D-07), so per the plan it was omitted rather than fabricated"
  - "empty payload (total 0): preview shows «В файле нет данных для отправки.» and the upload form stays hidden even after a successful login (nothing to send)"
metrics:
  duration: ~15min
  tasks: 3
  files: 4
  completed: 2026-07-20
---

# Phase 30 Plan 04: Offline Client Export + Self-Uploading File Summary

Wave-3 ships the offline client half of Phase 30: the session-guarded desktop route `GET /offline/export` collects the unsynced ledger + its D-13 FK closure via the shared `collect_push_records`, serializes it to NDJSON (header carrying `counts` + `payload_sha256`), and renders a SINGLE self-contained HTML file (`self_upload.html`) delivered as a download attachment. Opened in any browser on an internet PC with no app install, that file previews the counts client-side, authenticates through the two-step handshake, and — only after an explicit confirm — posts itself to `/api/offline/upload` (the 30-03 ingest route). Plus the S3 offline-export CTA on the existing export page with its blank-URL error state. All additive, zero new packages, no migration; the route only reads and never stamps `synced_at` (D-07).

## What Was Built

**Task 1 — GET /offline/export (commit 61a7fcc):**
- Added `offline_export(request, session)` to `app/routes/offline.py`, a plain `def` deliberately NOT under `/api/offline/` so it stays behind the app-level session guard (T-30-06 — anonymous → 303 /login, proven by `test_offline_bypass_is_narrow`). Flow: Pitfall 5 guard (blank `settings.sync_server_url` re-renders `pages/export.html` with `sync_configured=False`, no dead file) → `records, _ids = collect_push_records(session)` (D-07: ids IGNORED, never stamps `synced_at`) → `body = "\n".join(serialize_exchange(records, schema_version=current_schema_version(session), source_device_id=settings.device_id, generated_at=utcnow_iso()))` → `embedded = body.replace("</script", "<\\/script")` (Pitfall 2) → render `offline/self_upload.html` with `embedded` + `server_url`, returned with `Content-Disposition: attachment; filename="myorishop-offline-YYYYMMDD-HHMM.html"`.
- Imports added: `datetime/timezone`, `app.config.settings`, `serialize_exchange`, `collect_push_records`.

**Task 2 — self_upload.html (commit 9354ab8):**
- Created `app/templates/offline/self_upload.html`, a fully self-contained document (OFF-03): `lang="ru"`, charset, viewport, and a single inline `<style>` replicating the UI-SPEC §S1 token table VERBATIM (body/main/h1/h2/label/.field/input/button/:disabled/`:focus-visible` `2px solid #2563eb`/.muted/.error-block/.preview-panel). NO `<link>`, `@import`, web-font, CDN, or external image.
- The NDJSON lives in `<script id="payload" type="application/x-ndjson">{{ embedded | safe }}</script>` (`| safe` correct because non-executable + `</script>` already neutralized, Pitfall 6). A top-level `<form id="upload" method="post" enctype="multipart/form-data" action="{{ server_url }}/api/offline/upload">` holds hidden `token` + `payload` fields and the confirm submit button.
- Inline vanilla JS (no HTMX/library): (1) on load — recover the ORIGINAL NDJSON (`replace(/<\\\/script/g, "</script")`), parse the header, render the preview counts from `header.counts` in UI-SPEC RU-label order (zero counts omitted), stage the ORIGINAL payload into the hidden field, all BEFORE any network call; empty payload → «В файле нет данных для отправки.» with the form kept hidden; (2) «Проверить» → `fetch(server + "/api/offline/login", …x-www-form-urlencoded…)` — 401 → «Неверный логин или пароль. Данные не отправлены.», 429 → «Слишком много попыток…», network → «Не удалось связаться с сервером…»; on 2xx stash the token and reveal the confirm step; (3) form submit disables the button + shows the no-graphic «Отправка…» caption. `server_url` is read from `document.body.dataset.server` (autoescaped HTML attribute), never a JS string literal.

**Task 3 — export page CTA + empty-URL state (commit e5594dd):**
- `app/routes/export.py`: `export_page` now passes `sync_configured=bool(settings.sync_server_url)` (added `from app.config import settings`).
- `app/templates/pages/export.html`: added an «Офлайн-экспорт» section below the CSV buttons — when `sync_configured`, a primary `<a class="button" href="/offline/export">Экспортировать офлайн-файл</a>` + the RU `.muted` helper; otherwise the `.error-block` «Сначала укажите адрес сервера в настройках, затем экспортируйте файл.» (Pitfall 5). The optional read-only hint was omitted (D-07 — no clean source without touching `synced_at`).

## Verification

- `uv run pytest tests/test_offline.py -q` → **18 passed** — the whole offline module is now GREEN (the 3 previously-RED export rows `test_export_html_contains_embedded_payload_and_form`, `test_script_tag_escaping_round_trip`, `test_offline_bypass_is_narrow` join the ingest rows from 30-03).
- `uv run pytest -q` (full suite) → **1142 passed, 12 skipped, 0 failed** in 428s — the 1139 baseline plus the 3 export rows this wave turned green; **zero regressions**.
- Manual grep (D-07 / self-containment): `synced_at` appears in `app/routes/offline.py` only in the export route docstring/comment (never assigned); `<link`/`@import`/CDN/font in `self_upload.html` only in the self-containment prohibition comment (no actual asset link); the form action is `{{ server_url }}/api/offline/upload`.

## Deviations from Plan

None — plan executed exactly as written. The only judgment calls were pre-authorized by the plan/UI-SPEC: omitting the optional D-07 read-only hint (no clean `synced_at`-free source), and re-rendering the export page (rather than a bespoke card) on a blank server URL to reuse Task 3's error-block state.

## Notes for Downstream

- Phase 30 client half is complete: the desktop operator exports all not-yet-uploaded work to one self-contained HTML file (OFF-01/OFF-02), which opens in any browser with no install and uploads itself (OFF-03), previewing counts and gating the POST behind an explicit confirm (OFF-06). The file lands the operator on the 30-03 S2 result page.
- **UAT (from 30-VALIDATION §Manual-Only):** open the exported HTML in a real browser on an internet PC — confirm preview counts render, nothing POSTs until the confirm click, and login+upload completes with no app installed. This is the one MEDIUM-confidence surface (CRLF form normalization A1 / CORS simple-request A2) that only a real browser fully exercises; the automated CRLF + round-trip tests are the proxy guards.
- **Known consequence (D-07, flagged for UAT):** a permanently-offline client's unsynced badge (SYNC-07) stays inflated and re-exports re-include already-uploaded rows (harmless, larger files) — `synced_at` is cleared only by a confirmed online 2xx.
- No server-side merge change here, so PG-parity CI is unaffected by this wave.

## Self-Check: PASSED
