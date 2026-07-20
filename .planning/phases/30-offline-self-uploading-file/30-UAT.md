---
status: testing
phase: 30-offline-self-uploading-file
source: [30-VERIFICATION.md]
started: 2026-07-20T16:27:30Z
updated: 2026-07-20T16:27:30Z
---

## Current Test

number: 1
name: Self-uploading file opens with no app install on an internet PC (OFF-03)
expected: |
  Copy an exported `myorishop-offline-*.html` from a USB drive to a second
  internet-connected computer that has no MyOriShop installed and open it in any
  browser. The page renders fully with no blocked external CSS/JS/font requests
  (it is self-contained), and login + upload completes end-to-end against the
  central server without any application installed.
awaiting: user response

## Tests

### 1. Self-uploading file opens with no app install on an internet PC (OFF-03)
expected: |
  Copy an exported `myorishop-offline-*.html` from a USB drive to a second
  internet-connected computer with no MyOriShop install; open it in any browser.
  The page renders fully (no external CSS/JS/font loads); login + upload completes
  end-to-end against the central server with no application installed.
why_human: Requires a separate internet-connected machine with no app install; TestClient cannot exercise `file://` browser behaviour.
result: [pending]

### 2. In-browser preview counts + explicit confirm gate (OFF-06 / OFF-04)
expected: |
  In the opened file, observe the «Будет отправлено» preview before touching the
  network; the counts render from the embedded NDJSON header with no network call.
  Enter a wrong password → the inline RU error shows and NO payload is sent. Enter a
  correct password → the confirm step appears. Nothing POSTs to the server until the
  «Отправить на сервер» confirm button is clicked.
why_human: The preview render and no-post-until-confirm behaviour execute in browser JS; automated tests verify the embedded markup and JS source but not the live in-browser interaction.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
