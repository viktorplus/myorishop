---
phase: 2
slug: catalog-dictionary-search
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (+ httpx TestClient) — already installed (Phase 1) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -q -x` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -x`
- **After every plan wave:** Run `uv run pytest -q` + `uv run ruff check .`
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Test naming convention (set in Plan 02-01 Task 1): route/e2e tests carry the `test_web_` prefix, enabling `-k "not test_web_"` service-scope filters.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 1 | CAT-01 | — | N/A (RED contract) | unit+integration (RED) | `uv run pytest -q tests/test_catalog.py; test $? -ne 0` + `uv run pytest -q --ignore=tests/test_catalog.py` | creates tests/test_catalog.py | ⬜ pending |
| 2-01-02 | 02-01 | 1 | CAT-01 | T-2-04, T-2-06 | deleted-product guard in record_operation; migration never touches operations triggers | unit + migration | `uv run pytest -q tests/test_catalog.py -k "not test_web_"` + `uv run pytest -q tests/test_ledger.py tests/test_pragmas.py` | ✅ (from 2-01-01) | ⬜ pending |
| 2-01-03 | 02-01 | 1 | CAT-01 | T-2-01, T-2-03 | typed Form → 422; autoescape, no \|safe; routes write-free | integration (TestClient) | `uv run pytest -q` + `uv run ruff check .` + grep gates | ✅ (from 2-01-01) | ⬜ pending |
| 2-02-01 | 02-02 | 2 | CAT-01, CAT-04 | — | N/A (RED contract) | unit+integration (RED) | `uv run pytest -q tests/test_catalog.py; test $? -ne 0` | extends tests/test_catalog.py | ⬜ pending |
| 2-02-02 | 02-02 | 2 | CAT-04 | T-2-04, T-2-06 | price history via immutable ops; snapshot-before-mutate; no quantity writes in catalog.py | unit | `uv run pytest -q tests/test_catalog.py -k "not test_web_"` | ✅ (from 2-02-01) | ⬜ pending |
| 2-02-03 | 02-02 | 2 | CAT-01, CAT-04 | T-2-03, T-2-05 | hx-confirm on destructive delete; autoescaped history render | integration (TestClient) | `uv run pytest -q` + `grep -c "HX-Redirect" app/static/htmx.min.js` | ✅ (from 2-02-01) | ⬜ pending |
| 2-03-01 | 02-03 | 3 | CAT-03 | — | N/A (RED contract) | unit+integration (RED) | `uv run pytest -q tests/test_search.py; test $? -ne 0` | creates tests/test_search.py | ⬜ pending |
| 2-03-02 | 02-03 | 3 | CAT-03 | T-2-02, T-2-03 | LIKE autoescape (% _ literal), LIMIT 20, segment-split <mark> without \|safe | unit + integration | `uv run pytest -q` + `! grep -rn "ilike\|func.lower(Product.name" app/` | ✅ (from 2-03-01) | ⬜ pending |
| 2-04-01 | 02-04 | 3 | CAT-02 | — | N/A (RED contract) | integration (RED) | `uv run pytest -q tests/test_dictionary.py; test $? -ne 0` | creates tests/test_dictionary.py | ⬜ pending |
| 2-04-02 | 02-04 | 3 | CAT-02 | T-2-01, T-2-03 | lookup read-only; 204 guard never overwrites operator input; autoescaped fragment | integration (TestClient) | `uv run pytest -q` + `! grep -rn "record_operation" app/services/dictionary.py` | ✅ (from 2-04-01) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Each plan carries its own RED task (Task 1) — no cross-plan RED debt; the suite is green at every plan boundary.

- [ ] `tests/test_catalog.py` — CAT-01 (CRUD, optional fields, soft-delete reject), CAT-04 (price history ops) — created in 02-01 Task 1, extended in 02-02 Task 1
- [ ] `tests/test_search.py` — CAT-03 (Cyrillic case-insensitive partial search, ranking, cap 20, %-escape, 21-product cap case) — created in 02-03 Task 1
- [ ] `tests/test_dictionary.py` — CAT-02 (dictionary CRUD, code→name lookup: 200-fragment vs 204 branches) — created in 02-04 Task 1
- [x] Existing fixtures from tests/conftest.py reused (no new framework install)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Debounced autocomplete feel (300ms) in real browser | CAT-03 | Perceived latency/UX not testable in-process | Type in search box on /products; results update without page reload (end-of-phase human check, Plan 02-03) |
| Autofill feel + no-overwrite in real browser | CAT-02 | htmx swap/204 behavior in live DOM | On /products/new type known code → name fills with hint; type name first, then code → nothing overwritten (end-of-phase human check, Plan 02-04) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (per-plan RED tasks)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
