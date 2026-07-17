---
phase: 23
slug: dashboard-history-rebuild
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `23-RESEARCH.md` § Validation Architecture (commands measured, not estimated).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (`pyproject.toml` `pytest==9.1.*`, `testpaths = ["tests"]`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_history.py tests/test_mobile_home.py tests/test_finance_reports.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | Not yet measured this session — capture at planning/Wave 0 time |

> **Every command must be prefixed `uv run`** — deps live in the uv-managed `.venv`.

---

## Sampling Rate

- **After every task commit:** targeted `-k`/file subset for the requirement being implemented (see map below)
- **After every plan wave:** `uv run pytest tests/test_dashboard.py tests/test_history.py tests/test_mobile_history.py tests/test_mobile_home.py tests/test_active_catalog.py`
- **Before `/gsd-verify-work`:** `uv run pytest` (full suite) must be green
- **Max feedback latency:** target < 30s for the quick run

---

## Phase Requirements → Test Map

*(Requirement-level draft — planner binds exact Task ID/Plan/Wave columns during planning.)*

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| DASH-01 | Home shows date/weekday/time | unit (service) + route smoke | `uv run pytest tests/test_home.py -x` | ❌ Wave 0 (no `test_home.py` today) |
| DASH-02 | Active catalog number + days-remaining; empty state renders without error | unit (`ActiveCatalog` service) + Alembic upgrade/downgrade round-trip | `uv run pytest tests/test_active_catalog.py -x`; `uv run alembic upgrade head && uv run alembic downgrade -1` | ❌ Wave 0 |
| DASH-03 | Revenue/profit/expense correct for today/week/month, incl. D-08 sign convention | unit (mirrors `test_finance_reports.py`) | `uv run pytest tests/test_dashboard.py -k metrics -x` | ❌ Wave 0 |
| DASH-04 | Distinct product-code count + valuation match manual SUM | unit | `uv run pytest tests/test_dashboard.py -k valuation -x` | ❌ Wave 0 |
| DASH-05 | Feed columns adapt per type; walk-in sale shows no customer; non-sale rows never crash on missing customer/price | unit + route smoke (mirrors `recent_sales`'s outerjoin precedent) | `uv run pytest tests/test_dashboard.py -k feed -x` | ❌ Wave 0 |
| HIST-01 | Selecting a type swaps BOTH rows and columns; unselected default keeps current generic 10-column view | route/e2e (`test_web_` convention) | `uv run pytest tests/test_history.py -k test_web_type_columns -x` | ❌ Wave 0 (extend existing 12-test file) |
| HIST-02 | Product/date/customer/category filters compose (AND semantics); customer/category filters absent-or-inert where inapplicable | unit + route | `uv run pytest tests/test_history.py -k filter -x` | ❌ Wave 0 (extend existing file) |
| HIST-03 | Sort options per type produce correctly-ordered results | unit | `uv run pytest tests/test_history.py -k sort -x` | ❌ Wave 0 (extend existing file — currently only "oldest" tested) |
| HIST-04 | Pagination correct on desktop and mobile after load-more → numbered migration | unit + route (mirrors `test_pagination.py` + `test_mobile_history.py`) | `uv run pytest tests/test_pagination.py tests/test_mobile_history.py -x` | ✅ (extend existing files) |

*Status: ⬜ pending for all rows — plans not yet created.*

---

## Wave 0 Requirements

- [ ] `tests/test_home.py` — **new file**, covers DASH-01/DASH-05 desktop route smoke (no such file exists today — only `test_mobile_home.py` with 1 test)
- [ ] `tests/test_active_catalog.py` — **new file**, covers the new `ActiveCatalog` model + service + `/catalogs` form round-trip + Alembic migration
- [ ] `tests/test_dashboard.py` — **new file**, covers `dashboard_metrics()`/`stock_valuation` composition/feed generalization (money-math correctness, D-08 sign convention, join correctness)
- [ ] Extend `tests/test_history.py` (currently 12 tests) — new filter/sort/column-set cases
- [ ] Extend `tests/test_mobile_history.py` — numbered-pagination migration cases (currently load-more-shaped)
- [ ] Framework install: none — pytest/httpx already installed and in use project-wide

---

## Manual-Only Verifications

*To be confirmed during planning — RESEARCH.md flags no JS-runtime-only behaviors for this phase (server-rendered HTMX, no client-side column-visibility logic per D-03).*

*If none survive planning: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies — pending planner task binding
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify — pending planner task binding
- [ ] Wave 0 covers all MISSING references — pending planner task binding
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s — pending measurement
- [ ] `nyquist_compliant: true` set in frontmatter — pending planner sign-off

**Approval:** pending
