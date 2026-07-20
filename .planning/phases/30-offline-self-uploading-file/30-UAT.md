---
status: diagnosed
phase: 30-offline-self-uploading-file
source: [30-VERIFICATION.md]
started: 2026-07-20T16:27:30Z
updated: 2026-07-20T16:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Self-uploading file opens with no app install on an internet PC (OFF-03)
expected: |
  Copy an exported `myorishop-offline-*.html` from a USB drive to a second
  internet-connected computer with no MyOriShop install; open it in any browser.
  The page renders fully (no external CSS/JS/font loads); login + upload completes
  end-to-end against the central server with no application installed.
why_human: Requires a separate internet-connected machine with no app install; TestClient cannot exercise `file://` browser behaviour.
result: issue
reported: "Opened the exported file in a browser (served from a separate origin, standalone). It IS self-contained — no external CSS/JS/font requests. But the page is broken: the «Будет отправлено» preview is empty and raw JavaScript leaks onto the page as text. The file's login/upload logic never runs, so upload cannot complete end-to-end."
severity: blocker

### 2. In-browser preview counts + explicit confirm gate (OFF-06 / OFF-04)
expected: |
  In the opened file, observe the «Будет отправлено» preview before touching the
  network; the counts render from the embedded NDJSON header with no network call.
  Enter a wrong password → the inline RU error shows and NO payload is sent. Enter a
  correct password → the confirm step appears. Nothing POSTs to the server until the
  «Отправить на сервер» confirm button is clicked.
why_human: The preview render and no-post-until-confirm behaviour execute in browser JS; automated tests verify the embedded markup and JS source but not the live in-browser interaction.
result: issue
reported: "Preview counts do NOT render (panel is empty) and the login/confirm flow is dead, because the inline <script> that owns all of this behaviour is terminated early by the browser. Cannot verify wrong-password gate, confirm gate, or no-post-until-confirm — none of the JS executes."
severity: blocker

## Summary

total: 2
passed: 0
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "The self-uploading file's inline JS (preview render, login, upload) runs when the file is opened in a browser"
  status: failed
  reason: "User reported: preview empty, JS leaks as page text, login/upload dead — the file is non-functional on any computer."
  severity: blocker
  test: 1
  root_cause: "The second (logic) <script> block in app/templates/offline/self_upload.html contains literal `</script`, `</SCRIPT`, `</Script` sequences inside its JavaScript // comments (lines 146, 149, 150 — added by the CR-01 fix commit ba02d29). An HTML <script> raw-text element is terminated at the FIRST `</script` (case-insensitive) regardless of JS comment context, so the browser cuts the script off at line 146 and renders everything after it as page text. The CR-01 fix correctly neutralized `</script` in the embedded DATA, but the comments *describing* that fix, written inside the live script, themselves break the page."
  artifacts:
    - path: "app/templates/offline/self_upload.html"
      issue: "Literal `</script` / `</SCRIPT` / `</Script` in JS comments at lines 146, 149, 150 prematurely terminate the logic <script> element."
  missing:
    - "Rewrite the three comment lines so no literal `</script` (any case) appears inside the live <script> block — e.g. write it as `<\\/script`, or `the closing script tag`, or split the token (`</scr`+`ipt`). The comment on line 111 is inside a Jinja {# #} block (stripped at render) and is harmless."
    - "Add a browser-level regression that asserts the logic script executes (e.g. the preview panel is populated / payload hidden field is staged) for an exported file, so a `</script` in this block is caught automatically. A static template test asserting no live-script line matches /<\\/script/i would also catch it cheaply."
  debug_session: ""
  fix_applied: "app/templates/offline/self_upload.html — rewrote the three JS comment lines (146/149/150) so no literal `</script` (any case) appears inside the live logic <script>; added a NOTE warning against writing the token there. NOT yet committed."
  fix_verified: "Live in-browser UAT (Claude in Chrome) on a regenerated export served from a separate origin (http://127.0.0.1:8020, standalone) against a demo central server (http://localhost:8010, empty ledger, admin/demo1234). All four checkpoints green: (1) preview renders «Операции 23 / Товары 7 / Покупатели 2 / Партии 4 / Продажи 6 / Движения кассы 26» with the ONLY network request being the page GET (self-contained, no external CSS/JS/font); (2) wrong password → «Неверный логин или пароль. Данные не отправлены.» + only POST /api/offline/login 401, no /upload; (3) correct password → «Отправить на сервер» confirm revealed, still no /upload; (4) confirm click → POST /api/offline/upload 200, result page «Данные загружены. Загружено записей: 49. Операций: 23, движений кассы: 26.», server DB rows 0→23 operations, 0→26 cash_movements."
  remaining: "Commit the template fix + add the regression test (still owed); then this blocker is closeable."
