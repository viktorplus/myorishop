---
phase: 23
slug: dashboard-history-rebuild
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-17
bound: 2026-07-17
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
| **Quick run command** | `uv run pytest tests/test_history.py tests/test_mobile_history.py tests/test_mobile_home.py tests/test_home.py tests/test_active_catalog.py tests/test_dashboard.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | Not yet measured this session — capture at Wave 1 execution time |

> **Every command must be prefixed `uv run`** — deps live in the uv-managed `.venv`.

---

## Sampling Rate

- **After every task commit:** targeted `-k`/file subset for the requirement being implemented (see map below)
- **After every plan wave:** `uv run pytest tests/test_dashboard.py tests/test_history.py tests/test_mobile_history.py tests/test_mobile_home.py tests/test_home.py tests/test_active_catalog.py -q` **plus** `uv run ruff check . && uv run ruff format --check .`
- **Before `/gsd-verify-work`:** `uv run pytest -q` (full suite) must be green
- **Max feedback latency:** target < 30s for the quick run

---

## Wave Structure

| Wave | Plans | Test files written |
|------|-------|---------------------|
| 1 | 23-01, 23-02 | `tests/test_active_catalog.py` (23-01, new) · `tests/test_history.py` (23-02, service-level extensions) |
| 2 | 23-03, 23-04, 23-05 | `tests/test_dashboard.py` (23-03, new) · `tests/test_history.py` (23-04, route/template-level extensions) · `tests/test_mobile_history.py` (23-05, route/template-level extensions) |
| 3 | 23-06, 23-07 | `tests/test_home.py` (23-06, new) · `tests/test_mobile_home.py` (23-07, extensions) |

**File-ownership invariant:** no two plans in the same wave write the same file. `tests/test_history.py` is serialized 23-02 (Wave 1) → 23-04 (Wave 2); `app/services/operations.py` is written once, by 23-02 only, and read (never written) by 23-04/23-05.

---

## Per-Task Verification Map

> Columns bound by the planner 2026-07-17. **Task ID** is the task that makes the row GREEN (the
> implementing task).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|------------------|-----------|--------------------|-------------|--------|
| 23-01-T1 | 23-01 | 1 | DASH-02 | — | `ActiveCatalog` migration round-trips (upgrade/downgrade/upgrade) | migration | `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` | ❌ W0 → 23-01-T1 | ⬜ pending |
| 23-01-T2 | 23-01 | 1 | DASH-02 | T-23-01, T-23-02 | get/set round-trip; overlong number / malformed close_date rejected with zero writes; singleton invariant holds | unit | `uv run pytest tests/test_active_catalog.py -x` | ❌ W0 → 23-01-T2 | ⬜ pending |
| 23-01-T3 | 23-01 | 1 | DASH-02 | T-23-03 | `/catalogs` form saves and re-displays number/close_date; malformed date shows inline RU error, does not save | web | `uv run pytest tests/test_active_catalog.py -k catalogs -x` | ❌ W0 → 23-01-T3 | ⬜ pending |
| 23-02-T1 | 23-02 | 1 | HIST-02 | T-23-04, T-23-07 | Category filter (Cyrillic-safe substring), customer filter (sale/return-only, bounded candidate resolution) | unit | `uv run pytest tests/test_history.py -k "category or customer" -x` | ❌ W0 → 23-02-T1 | ⬜ pending |
| 23-02-T1 | 23-02 | 1 | HIST-02 | T-23-07 | Date-range filter excludes rows outside the half-open window | unit | `uv run pytest tests/test_history.py -k date_range -x` | ❌ W0 → 23-02-T1 | ⬜ pending |
| 23-02-T2 | 23-02 | 1 | HIST-01 | — | `history_view`'s `columns` key resolves per-type (6 stock-affecting types) and falls back to `None` for no-filter/audit types | unit | `uv run pytest tests/test_history.py -k columns -x` | ❌ W0 → 23-02-T2 | ⬜ pending |
| 23-02-T2 | 23-02 | 1 | HIST-01 | — | Transfer's two sibling rows each carry their own batch/warehouse — no synthesized single row (Pitfall 6) | unit | `uv run pytest tests/test_history.py -k transfer_warehouse -x` | ❌ W0 → 23-02-T2 | ⬜ pending |
| 23-02-T1/T2 | 23-02 | 1 | HIST-03 | — | Existing sort (`oldest`/default) behavior unchanged by the new kwargs (regression) | unit | `uv run pytest tests/test_history.py::test_history_view_sort_oldest_first -x` | ✅ existing | ⬜ pending |
| 23-03-T1 | 23-03 | 2 | DASH-01 | — | `dashboard_now` returns correct weekday/date/time for the configured tz | unit | `uv run pytest tests/test_dashboard.py -k now -x` | ❌ W0 → 23-03-T1 | ⬜ pending |
| 23-03-T1 | 23-03 | 2 | DASH-02 | — | `catalog_status` empty/partial/open/closed branches | unit | `uv run pytest tests/test_dashboard.py -k catalog -x` | ❌ W0 → 23-03-T1 | ⬜ pending |
| 23-03-T1 | 23-03 | 2 | DASH-03 | T-23-08 | `period_metrics`'s net profit is `gross + expense` (addition, D-08 regression guard); week/month boundaries match `_resolve_period` | unit | `uv run pytest tests/test_dashboard.py -k metrics -x` | ❌ W0 → 23-03-T1 | ⬜ pending |
| 23-03-T2 | 23-03 | 2 | DASH-04 | — | `stock_summary`'s distinct-code count + valuation match a manual SUM | unit | `uv run pytest tests/test_dashboard.py -k stock_summary -x` | ❌ W0 → 23-03-T2 | ⬜ pending |
| 23-03-T2 | 23-03 | 2 | DASH-05 | T-23-09 | `recent_operations` never drops a walk-in sale or a non-sale type (both outerjoins stay outer) | unit | `uv run pytest tests/test_dashboard.py -k feed -x` | ❌ W0 → 23-03-T2 | ⬜ pending |
| 23-03-T2 | 23-03 | 2 | DASH-02 | T-23-10 | `dashboard_context` with no `ActiveCatalog` row still populates every other section | unit | `uv run pytest tests/test_dashboard.py -k context_empty_catalog -x` | ❌ W0 → 23-03-T2 | ⬜ pending |
| 23-04-T1 | 23-04 | 2 | HIST-02 | T-23-11 | Unfiltered `/history` stays unfiltered by date (D-04 regression); malformed `from`/`to` falls back to today with inline error | web | `uv run pytest tests/test_history.py -k "unfiltered_default or malformed_date" -x` | ❌ W0 → 23-04-T1 | ⬜ pending |
| 23-04-T2 | 23-04 | 2 | HIST-01 | — | Type select swaps rows AND columns in one response; generic view unchanged for no-filter/audit types (Pitfall 5) | web | `uv run pytest tests/test_history.py -k test_web_type_columns -x` | ❌ W0 → 23-04-T2 | ⬜ pending |
| 23-04-T2 | 23-04 | 2 | HIST-02 | T-23-13 | Customer filter hidden entirely (not disabled) for non-sale/return types (D-05) | web | `uv run pytest tests/test_history.py -k customer_filter_hidden -x` | ❌ W0 → 23-04-T2 | ⬜ pending |
| 23-04-T2 | 23-04 | 2 | HIST-04 | — | Pagination bar still reflects the filtered total (regression) | web | `uv run pytest tests/test_history.py::test_web_history_pagination_bar_reflects_filtered_total -x` | ✅ existing | ⬜ pending |
| 23-04-T2 | 23-04 | 2 | Regression | — | `period_filter.html`'s additive `hx-include` does not break Reports/Finance | web | `uv run pytest tests/test_reports.py -k sales -x` | ✅ existing | ⬜ pending |
| 23-05-T1 | 23-05 | 2 | HIST-04 | — | Mobile history migrates load-more → numbered pagination; filtered total correct | web | `uv run pytest tests/test_mobile_history.py -k paging -x` | ❌ W0 → 23-05-T1 | ⬜ pending |
| 23-05-T1 | 23-05 | 2 | HIST-02 | — | Reinstated `product` deep-link param narrows mobile results | web | `uv run pytest tests/test_mobile_history.py -k product_filter -x` | ❌ W0 → 23-05-T1 | ⬜ pending |
| 23-05-T2 | 23-05 | 2 | HIST-01 | — | Mobile cards narrow fields per-type (same `columns` source as desktop) | web | `uv run pytest tests/test_mobile_history.py -k columns -x` | ❌ W0 → 23-05-T2 | ⬜ pending |
| 23-05-T2 | 23-05 | 2 | HIST-04 | — | `#history-cards` and `#history-pagination` are DOM siblings, never nested (CR-01 precedent) | web | `uv run pytest tests/test_mobile_history.py -k siblings -x` | ❌ W0 → 23-05-T2 | ⬜ pending |
| 23-06-T1/T2 | 23-06 | 3 | DASH-01 | — | `GET /` renders date/weekday/time | web | `uv run pytest tests/test_home.py -k datetime -x` | ❌ W0 → 23-06-T2 | ⬜ pending |
| 23-06-T2 | 23-06 | 3 | DASH-02 | T-23-16 | Empty-catalog state renders the link; closed catalog renders «закрыт», never a bare negative number | web | `uv run pytest tests/test_home.py -k catalog -x` | ❌ W0 → 23-06-T2 | ⬜ pending |
| 23-06-T2 | 23-06 | 3 | DASH-03, DASH-04 | — | 4-tile metric grid renders with correct figures | web | `uv run pytest tests/test_home.py -k tiles -x` | ❌ W0 → 23-06-T2 | ⬜ pending |
| 23-06-T2 | 23-06 | 3 | DASH-05 | T-23-17 | Feed row links into `/history?type=...&product=...`; per-type columns populate/mute correctly | web | `uv run pytest tests/test_home.py -k feed -x` | ❌ W0 → 23-06-T2 | ⬜ pending |
| 23-07-T1/T2 | 23-07 | 3 | DASH-01..05 | — | `/m/` renders the same dashboard content as desktop | web | `uv run pytest tests/test_mobile_home.py -k dashboard -x` | ❌ W0 → 23-07-T2 | ⬜ pending |
| 23-07-T2 | 23-07 | 3 | Regression | T-23-19 | Existing nav-tile-order test unmodified; new structural guard: nav grid precedes dashboard content (Pitfall 1) | web | `uv run pytest tests/test_mobile_home.py -x` | ✅ existing test extended by 23-07-T2 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_active_catalog.py` — **new file** (23-01-T2/T3): model+service round-trip, migration round-trip, `/catalogs` form save/error cases
- [ ] `tests/test_dashboard.py` — **new file** (23-03-T1/T2): `dashboard_now`/`catalog_status`/`period_metrics`/`dashboard_metrics`/`stock_summary`/`recent_operations`/`dashboard_context` — money-math correctness, D-08 sign convention, double-outerjoin correctness
- [ ] `tests/test_home.py` — **new file** (23-06-T2): desktop `/` route+template smoke covering DASH-01..05
- [ ] Extend `tests/test_history.py` (currently 12 tests) — 23-02-T1/T2 (service-level: filters, columns, warehouse join) then 23-04-T1/T2 (route/template-level: type-first UI, filter visibility)
- [ ] Extend `tests/test_mobile_history.py` — 23-05-T1/T2 (numbered-pagination migration, product deep-link, per-type card narrowing); the existing `test_no_product_filter_param_on_route_signature` test is UPDATED, not silently deleted (see 23-05-T1 acceptance criteria)
- [ ] Extend `tests/test_mobile_home.py` — 23-07-T2 (dashboard content + Pitfall-1 structural regression guard); existing `test_mobile_home_renders_all_tiles_in_order` stays green unmodified
- [ ] Framework install: none — pytest/httpx already installed and in use project-wide

---

## Manual-Only Verifications

RESEARCH.md flags no JS-runtime-only behaviors for this phase — server-rendered HTMX throughout, no
client-side column-visibility logic (explicitly ruled out by D-03), no live-total-style arithmetic in
this phase's scope (unlike Phase 22's SALE-02). All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every task across 23-01..23-07 carries an `<automated>` command in its PLAN.md; every ❌ W0 reference above maps to the task that authors it
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — no task lacks one
- [x] Wave 0 covers all MISSING references — every ❌ W0 row maps to a named 23-0N-TN task above
- [x] No watch-mode flags — every command is a single-shot `uv run pytest`; no `--looponfail`, no `-f`
- [ ] Feedback latency < 30s — pending measurement at Wave 1 execution
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] Wave 0 executed (`wave_0_complete`) — **not yet true**; 23-01/23-02 have not run. Flips on Wave 1 completion, not at planning time.

**Approval:** Planner-bound 2026-07-17 — task/plan/wave columns resolved, Nyquist gate green.
Awaiting execution; `status` flips to `verified` once the phase gate (full suite green, no regressions
in `tests/test_reports.py`/`tests/test_finance.py`/`tests/test_mobile_finance.py`) is confirmed.
