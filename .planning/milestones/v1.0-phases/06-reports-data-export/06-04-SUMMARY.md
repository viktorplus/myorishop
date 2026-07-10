---
phase: 06-reports-data-export
plan: 04
subsystem: export
tags: [fastapi, sqlalchemy, csv, streaming, htmx]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: append-only Operation ledger, format_cents/iso_to_local conventions
  - phase: 04-sales-customers
    provides: Sale header + frozen unit_cost_cents/unit_price_cents per sale line
  - phase: 06-reports-data-export (06-02)
    provides: "/reports landing page + nav «Отчёты» entry this plan's «Экспорт» entry sits alongside"
provides:
  - "app.services.export.stream_products_csv/stream_sales_csv/stream_customers_csv(session) -> StreamingResponse — full-table CSV dumps"
  - "app.services.export._csv_rows/_encode_once — BOM-once, semicolon-delimited CSV chunk generators (D-07, RESEARCH Pitfall 4)"
  - "app.services.export._csv_safe — CSV/formula-injection hardening (T-06-10)"
  - "GET /export page + GET /export/products.csv, /export/sales.csv, /export/customers.csv"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BOM-once streaming: _encode_once encodes only the first yielded text chunk with utf-8-sig, every later chunk with plain utf-8 — encoding every chunk with utf-8-sig would repeat the BOM and corrupt the file"
    - "';' CSV delimiter chosen deliberately because this app's format_cents renders money with a comma decimal separator ('12,50'), which a comma row delimiter would split into two columns"
    - "_csv_safe formula-injection guard: any free-text cell starting with =, +, -, or @ gets a leading apostrophe before writing — applied to every product/customer name, code, and category field across all three exports"

key-files:
  created:
    - app/services/export.py
    - app/routes/export.py
    - app/templates/pages/export.html
    - tests/test_export.py
  modified:
    - app/templates/base.html
    - app/main.py

key-decisions:
  - "_csv_safe applied consistently to ALL free-text cells across all three CSV exports (product code/name/category, customer name/surname, sale product code/name/customer name) — not just the customer name the plan's action text explicitly wrote out — per the plan's own <behavior> requirement and threat register T-06-10's 'any free-text cell value' wording"
  - "stream_sales_csv orders ascending (oldest-first) — a one-line comment documents this as an intentional divergence from the newest-first UI listings used elsewhere (/history, /reports/sales), since a full data-dump export reads best chronologically"
  - "consultant_number in stream_customers_csv is NOT wrapped in _csv_safe (plan's literal spec) — it's a numeric-ish field, unlike name/surname"

requirements-completed: [BCK-02]

# Metrics
duration: 15min
completed: 2026-07-10
---

# Phase 6 Plan 04: Data Export (CSV) Summary

**Three streaming CSV exports (products/sales/customers) with BOM-once utf-8-sig encoding, semicolon delimiter, and formula-injection hardening, served from a dedicated /export page with plain (non-htmx) download links**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-10 (session start)
- **Completed:** 2026-07-10T14:39:05Z
- **Tasks:** 2
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments
- `app/services/export.py` — `stream_products_csv`, `stream_sales_csv`, `stream_customers_csv`, each a `StreamingResponse` built on shared `_csv_rows`/`_encode_once` helpers that guarantee exactly one UTF-8 BOM at stream start and a `;` row delimiter, so a comma-decimal money value like `12,50` is never itself split by Excel's RU-locale CSV auto-import
- `_csv_safe` formula-injection guard applied to every free-text cell (product code/name/category, customer name/surname) across all three exports — a name starting with `=`, `+`, `-`, or `@` is prefixed with a leading apostrophe
- `GET /export` page with three plain `a.button`-styled download links (deliberately NOT `hx-get` — htmx would try to swap the CSV response into the DOM and break the native browser file download)
- `GET /export/products.csv`, `/export/sales.csv`, `/export/customers.csv` — each a hardcoded full-table dump; zero client-supplied filename/path/Form/Query parameters accepted (T-06-09), pinned by `test_web_export_ignores_client_params`
- Nav gains an «Экспорт» entry right after «Отчёты»; `app/main.py` registers the new router

## Task Commits

Each task was committed atomically (Task 1 followed RED/GREEN TDD, Task 2 was `type="auto"`):

1. **Task 1: export.py generators — RED** - `ebe66c3` (test)
2. **Task 1: export.py generators — GREEN** - `36afa6e` (feat)
3. **Task 2: /export page + three download routes, nav entry** - `549358e` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final commit).

## Files Created/Modified
- `app/services/export.py` - New: three CSV stream generators + `_csv_rows`/`_encode_once`/`_csv_safe` helpers
- `app/routes/export.py` - New: `GET /export`, `GET /export/products.csv`, `/export/sales.csv`, `/export/customers.csv`
- `app/templates/pages/export.html` - New: `/export` page, three plain `a.button` download links
- `app/templates/base.html` - Added «Экспорт» nav entry between «Отчёты» and «Справочник»
- `app/main.py` - Registered `export` router (alphabetical import + append to include_router block)
- `tests/test_export.py` - New file: 4 service-level tests (Task 1) + 4 web-level tests (Task 2)

## Decisions Made
- Extended `_csv_safe` coverage to every free-text field in all three exports (not only the customer-name field the plan's action text spelled out), matching Task 1's `<behavior>` requirement ("A product/customer name...") and the threat register's broader "any free-text cell value" wording for T-06-10
- Kept `stream_sales_csv` query/row-building logic inline in the service (no extra helper) since RESEARCH's verified code shape was already this compact
- Documented the ascending (oldest-first) sort order in `stream_sales_csv` with a one-line comment, since every other listing in this app (`/history`, `/reports/sales`) sorts newest-first

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unnecessary `Generator[X, None, None]` default type args**
- **Found during:** Task 1's `uv run ruff check app/services/export.py` verification step
- **Issue:** Ruff's UP043 rule (Python 3.13 target) flags `Generator[str, None, None]`/`Generator[bytes, None, None]` as unnecessary default type arguments — the plan's action text specified these signatures verbatim, but they fail this project's ruff config as written
- **Fix:** Applied `ruff check --fix`, which simplified both annotations to `Generator[str]` / `Generator[bytes]` — no behavior change, purely a type-annotation simplification
- **Files modified:** app/services/export.py
- **Verification:** `uv run ruff check app/services/export.py` passes; `uv run pytest tests/test_export.py -x -q` still green
- **Committed in:** `36afa6e` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed import-block sort order in tests/test_export.py**
- **Found during:** Task 2's `uv run ruff check` verification pass
- **Issue:** Ruff's I001 rule flagged a formatting nit in the stdlib import block (extra blank line before a comment) after Task 2's test additions
- **Fix:** Applied `ruff check --fix`
- **Files modified:** tests/test_export.py
- **Verification:** `uv run ruff check tests/test_export.py` passes; full test file still green (8/8)
- **Committed in:** `549358e` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both cosmetic ruff-lint fixes, no behavior change)
**Impact on plan:** Zero functional impact. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BCK-02 fully satisfied: three CSV downloads from a dedicated `/export` page, correctly encoded (`utf-8-sig`, BOM once) and delimited (`;`), zero client-controlled parameters, formula-injection hardening on every free-text cell
- **Manual UAT still pending** (per the plan's own `<verification>` note and UI-SPEC's Interaction Contract): double-clicking a downloaded CSV on the target Windows machine to confirm columns split correctly with readable Cyrillic in Excel. This is the one item this plan explicitly flags as needing a real Excel-open, not just an automated test (RESEARCH A3) — the automated `test_products_csv_roundtrip` test proves the byte-level contract (BOM, delimiter, header, row count) but cannot substitute for an actual Excel double-click. Per `workflow.human_verify_mode: end-of-phase` in this project's config, this defers to the phase-level UAT batch rather than a mid-plan checkpoint.
- No blockers for downstream Phase 6 plans (06-05, 06-06) — this plan's files (`app/services/export.py`, `app/routes/export.py`) are standalone and not depended on by other Phase 6 plans

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (export.py CSV generators) | ✓ `ebe66c3` | ✓ `36afa6e` | n/a | Pass |

Task 2 was `type="auto"` (no `tdd="true"`) — no RED/GREEN gate applies.

---
*Phase: 06-reports-data-export*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/services/export.py
- FOUND: app/routes/export.py
- FOUND: app/templates/pages/export.html
- FOUND: commit ebe66c3, 36afa6e, 549358e all present in git log
- uv run pytest tests/test_export.py -x -q: 8 passed
- uv run pytest (full suite): 193 passed
- uv run ruff check app/services/export.py app/routes/export.py app/main.py: All checks passed
