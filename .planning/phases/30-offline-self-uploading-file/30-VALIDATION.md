---
phase: 30
slug: offline-self-uploading-file
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-20
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
| {N}-01-01 | 01 | 1 | OFF-{XX} | T-30-{XX} / — | {expected secure behavior or "N/A"} | unit | `{command}` | ❌ W0 | ⬜ pending |

*Populated by the planner + nyquist pass from the RESEARCH.md Requirements → Test Map (OFF-01..07 + token/bypass/escaping/CRLF/rate-limit rows).*

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
