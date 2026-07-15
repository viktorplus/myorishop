---
phase: 17
slug: financial-reports-export-dashboard-analytics
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-15
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `17-RESEARCH.md` §Validation Architecture + the four PLAN.md test seams.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + FastAPI `TestClient` (httpx 0.28.1) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`); fixtures in `tests/conftest.py` (`engine`, `session`, `product`, `client`) |
| **Quick run command** | `uv run pytest tests/test_finance_reports.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | quick ~3–5 s (new file only) · full suite ~45–60 s (39 test modules) |

**Naming convention (VERIFIED in `tests/test_export.py`):** route/web tests are prefixed `test_web_*`; service-level tests MUST NOT use that prefix. Reuse the `_ensure_batch` / `_record_sale_at` helpers from `tests/test_reports.py` and the CSV-roundtrip assertions from `tests/test_export.py`.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_finance_reports.py -x` (< 5 s)
- **After every plan wave:** Run `uv run pytest` (full suite must be green)
- **Before `/gsd-verify-work`:** Full suite green + the manual browser/CSV checks below
- **Max feedback latency:** ~5 seconds (quick command)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | FIN-11, FIN-12 | T-17-01 / T-17-04 / T-17-05 | Period bounds consumed only as ORM `.where(created_at …)`; category set from `CASH_BUCKETS` allow-list via `.in_()`; SELECT-only, no write path | service (tdd) | `uv run pytest tests/test_finance_reports.py -k "net or valuation" -x` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | FIN-08 | T-17-01 / T-17-04 | Half-open `[start_iso,end_iso)`; income/expense rows only from bucket allow-list; reconciles with net tile (D-05) | service (tdd) | `uv run pytest tests/test_finance_reports.py -k "cash_flow or report" -x` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | FIN-09 | T-17-02 / T-17-03 / T-17-01 | `_csv_safe` on every free-text cell (`note or ""`), single BOM (`_encode_once`), `;` delimiter; T-06-09 docstring records validated-date-range exception | service (tdd) | `uv run pytest tests/test_finance_reports.py -k csv -x` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | FIN-10, FIN-11 | T-17-01 | net = gross **+** signed expense sum (addition); gross == `sales_profit_report` profit_cents; net tile shows D-01b cash-outflow caveat | service + web | `uv run pytest tests/test_finance_reports.py -k "gross or net" -x` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | FIN-12 | T-17-05b | valuation tile: NULL prices excluded (not zero), unknown counts surfaced, point-in-time («на текущий момент») | web | `uv run pytest tests/test_finance_reports.py -k "valuation or tiles" -x` | ❌ W0 | ⬜ pending |
| 17-03-01 | 03 | 3 | FIN-08, FIN-09 | T-17-01 / T-17-06 / T-17-09 | `/finance/report(.csv)` from/to via `_resolve_period`; streamed CSV; plain `<a href>` download (never `hx-get`) | web | `uv run pytest tests/test_finance_reports.py -k "report_hx or web_csv" -x` | ❌ W0 | ⬜ pending |
| 17-03-02 | 03 | 3 | FIN-08 | T-17-05b | report partial: labels from `CASH_CATEGORIES`, Jinja autoescape, never `\| safe` on note/label; empty-state branch | web | `uv run pytest tests/test_finance_reports.py -k "report and not hx" -x` | ❌ W0 | ⬜ pending |
| 17-04-01 | 04 | 4 | FIN-10, FIN-11, FIN-12 | T-17-01 | mobile `/m/finance` tiles reuse the shared partials; parity with desktop values | web | `uv run pytest tests/test_finance_reports.py -k "mobile and tiles" -x` | ❌ W0 | ⬜ pending |
| 17-04-02 | 04 | 4 | FIN-08, FIN-09 | T-17-01 / T-17-06 / T-17-09 | mobile `/m/finance/report` (new construction) + CSV via `finance_base` prefix; same validation seam | web | `uv run pytest tests/test_finance_reports.py -k "mobile and report" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*File Exists: ❌ W0 = created by Wave-1 plan 01 (Task 1 authors `tests/test_finance_reports.py`) before the Wave 2/3/4 dependents consume it.*

---

## Wave 0 Requirements

- [ ] `tests/test_finance_reports.py` — authored by plan **17-01** (service tests for `cash_expense_total`, `stock_valuation`, `cash_flow_report`, `stream_cash_movements_csv`; web tests for the report page + CSV route + tiles). Reuse `_ensure_batch` / `_record_sale_at` (`tests/test_reports.py`) and the CSV-roundtrip assertions (`tests/test_export.py`).
- [ ] Fixtures for NULL-price products and a mixed cash-movement set (withdrawal + return + deposit + sale) in the same period; pre-seed a covering balance where the write-gate would otherwise interfere (Phase 16 precedent).
- No framework install needed — pytest 9.1.x + `TestClient` already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CSV opens correctly in RU-Excel (BOM detected, `;` columns, RU labels, signed amounts) | FIN-09 | Excel rendering can't be asserted in pytest | Download from `/finance/report`, open the `.csv` in Excel, confirm one column split on `;`, Cyrillic labels intact, no `=`/formula execution |
| Desktop dashboard tiles + report render correctly | FIN-08/10/11/12 | Visual layout / caveat-label discoverability | Browse `/finance` (tiles + light period selector, net-caveat line visible) and `/finance/report` (income vs expense, period presets) |
| Mobile parity | FIN-08/10/11/12 | Responsive layout on `/m/*` | Browse `/m/finance` and `/m/finance/report`; confirm the same numbers and the net-caveat line are visible on the narrow layout |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`tests/test_finance_reports.py` via plan 17-01)
- [x] No watch-mode flags (all commands use `-x`, no `--watch`/`-f`)
- [x] Feedback latency < 5s (quick command)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-15
