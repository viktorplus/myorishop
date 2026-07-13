---
phase: 11
slug: dedicated-mobile-flow
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-12
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* with `httpx`-backed `fastapi.testclient.TestClient` (existing `client` fixture in `tests/conftest.py`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_mobile_*.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10-20 seconds (full suite currently 358 tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mobile_*.py -x -q` (or the closest existing desktop-equivalent file if the mobile file doesn't exist yet for that task)
- **After every plan wave:** Run `uv run pytest -q` (full suite — also guards that desktop tests stay green, i.e. the "purely additive" phase boundary held)
- **Before `/gsd-verify-work`:** Full suite must be green + manual UAT gates from `11-UI-SPEC.md`
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-XX-01 | TBD | TBD | UI-01 | — | `/m/` home renders all 8 tiles with correct hrefs | integration | `uv run pytest tests/test_mobile_home.py -x -q` | ❌ W0 | ⬜ pending |
| 11-XX-02 | TBD | TBD | UI-01 | T-11 batch-ownership | Each wizard's final step calls the SAME service function as its desktop counterpart, same DB effect | integration | `uv run pytest tests/test_mobile_sales.py -x -q` | ❌ W0 | ⬜ pending |
| 11-XX-03 | TBD | TBD | UI-01 | — | Guardrails (price-floor, oversell, over-removal) fire identically on mobile, zero-write until `confirm=1` | integration | `uv run pytest tests/test_mobile_sales.py -k oversell -q` (+ writeoff/correction/transfer equivalents) | ❌ W0 | ⬜ pending |
| 11-XX-04 | TBD | TBD | UI-01 | — | Batch-selection step blocks forward progress when a product has zero open batches | integration | `uv run pytest tests/test_mobile_sales.py -k empty_batches -q` | ❌ W0 | ⬜ pending |
| 11-XX-05 | TBD | TBD | UI-01 | — | `/m/history` renders one filter + card rows with all 4 lines | integration | `uv run pytest tests/test_mobile_history.py -x -q` | ❌ W0 | ⬜ pending |
| 11-XX-06 | TBD | TBD | UI-01 | — | `/m/reports/expiry` renders the read-only card list | integration | `uv run pytest tests/test_mobile_reports.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are placeholders — the planner assigns real plan/wave/task numbers; this table's rows are the requirement→test obligations that must map onto whatever tasks are created.*

---

## Wave 0 Requirements

- [ ] `tests/test_mobile_home.py` — stubs for UI-01 (home tile grid)
- [ ] `tests/test_mobile_search.py` — stubs for UI-01 (search screen)
- [ ] `tests/test_mobile_receipts.py` — stubs for UI-01 (receipt wizard)
- [ ] `tests/test_mobile_sales.py` — stubs for UI-01 (sale wizard + basket + guardrails)
- [ ] `tests/test_mobile_writeoff.py` — stubs for UI-01 (write-off wizard + guardrail)
- [ ] `tests/test_mobile_corrections.py` — stubs for UI-01 (correction wizard + guardrail)
- [ ] `tests/test_mobile_transfers.py` — stubs for UI-01 (transfer wizard + guardrail)
- [ ] `tests/test_mobile_returns.py` — stubs for UI-01 (return flow, entry from history)
- [ ] `tests/test_mobile_history.py` — stubs for UI-01 (history card list + single filter)
- [ ] `tests/test_mobile_reports.py` — stubs for UI-01 (expiry report card list)
- No framework install needed — `tests/conftest.py`'s existing `client`/`session`/`product`/`warehouse`/`batch`/`customer`/`stocked_product` fixtures are directly reusable for every new mobile test file.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Viewport-width auto-redirect (D-02) fires only from a phone-width browser landing on `/` | UI-01 | `TestClient` has no JS engine — `matchMedia`/`location.replace` cannot be executed or asserted by pytest; automated tests can only assert the redirect script text is present in `base.html` (weak proxy) | Open the app in a real browser (or devtools responsive mode) at <600px width, navigate to `/`, confirm auto-redirect to `/m/`. Then confirm `/customers`, `/backup`, `/dictionary` etc. remain directly reachable (not redirected) per Pitfall 2's scoping. |
| Desktop pages remain pixel-for-pixel unchanged at desktop widths | UI-01 | Visual/layout regression — no visual diffing tool in this project | Full existing desktop test suite must stay green (automated proxy) + manual spot-check of category page, batch picker, transfer form, expiry report at desktop width per ROADMAP success criterion 4 |
| Mobile wizard "one action per screen" feel / thumb-operability, 44px touch targets | UI-01 | Subjective UX quality, not assertable via TestClient | Manual walkthrough of each wizard on a real phone or emulator per `11-UI-SPEC.md`'s UAT gate list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-12 (plan-checker confirmed every task has a real automated verify command, no MISSING placeholders)
