---
phase: 6
slug: reports-data-export
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-10
---

# Phase 6 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| product form → POST /products, POST /products/{id} | untrusted threshold input (`low_stock_threshold`, `stale_days` raw strings) | form strings, low sensitivity |
| browser → GET /reports/* (sales, stock, writeoffs, products) | period query params (`from`, `to`) | date strings |
| browser → GET /export/*.csv | none (zero client-supplied params on any export route) | CSV byte stream |
| service layer → SQLite | all report/export queries must stay parameterized ORM | SQL parameters |
| CSV export → Excel (later, offline) | operator-entered free text (names, consultant numbers) rendered as CSV cells | CSV cell values |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-06-01 | Tampering | `parse_optional_int` (app/services/catalog.py) | mitigate | ASCII-digit-only allow-list with int32 upper bound (`<= 2_147_483_647`, WR-03 fix); non-conforming input never reaches the DB (catalog.py:43-56) | closed |
| T-06-02 | Tampering | `parse_optional_int` / product_form.html | mitigate | Explicit empty-string vs `"0"` distinction at the parsing boundary — an operator-entered `0` is stored as integer `0`, never coerced to `None`/default (catalog.py:50-52) | closed |
| T-06-03 | Repudiation | `update_product` audit trail | mitigate | `low_stock_threshold`/`stale_days` included in `old_fields`/`new_fields`, drives a `product_edited` op (catalog.py:212-280) | closed |
| T-06-04 | Denial of Service / Tampering | `_resolve_period` (app/routes/reports.py) | mitigate | `date.fromisoformat` wrapped in `try/except ValueError`; malformed/inverted ranges fall back to today with a RU error, never an uncaught exception (reports.py:56-65; reused unmodified by all four period-based reports) | closed |
| T-06-05 | Tampering | `local_day_bounds_utc` / period math | mitigate | Half-open `[start, end)` UTC range via `ZoneInfo(settings.display_tz)`, never a raw UTC-string date slice (core.py:62-80) | closed |
| T-06-06 | Information Disclosure | sales/top-selling result partials | accept | Jinja global autoescape, zero `\|safe` in any Phase 6 template; single local operator, no untrusted multi-tenant boundary | closed |
| T-06-07 | Tampering (logic error) | `effective_low_stock_threshold` | mitigate | Explicit `is not None` check, not a bare `or` — correctly-configured zero-threshold products stay visible (stock.py:19-25) | closed |
| T-06-08 | Information Disclosure | `reports_stock.html` | accept | Read-only, no client params; no data exposed beyond what `/products` already shows | closed |
| T-06-09 | Tampering / Information Disclosure | app/routes/export.py | mitigate | Zero client-supplied filename/path/Form/Query params on any of the three CSV routes; server-hardcoded filenames only (export.py:18-35); pinned by `test_web_export_ignores_client_params` | closed |
| T-06-10 | Tampering (CSV/formula injection) | `_csv_safe` (app/services/export.py) | mitigate | Free-text cells starting with `=`, `+`, `-`, `@` are apostrophe-prefixed; applied to every free-text cell across all three exports, including `consultant_number` (export.py:32-39,152 — CR-01 code-review fix, commit `0278925`); pinned by `test_customers_csv_roundtrip` | closed |
| T-06-11 | Information Disclosure | full-table CSV dumps (incl. soft-deleted products) | accept | Single local operator, no multi-tenant boundary; explicit full historical-dump design; WR-01 fix added a "Удалён" column so deleted rows stay distinguishable | closed |
| T-06-12 | Information Disclosure | `writeoffs_report_rows.html` (reason labels) | accept | `reason_code` looked up against the `WRITEOFF_REASONS` allow-list (reports.py:115-124); rendered via autoescape, never `\|safe` | closed |
| T-06-13 | Tampering (logic error) | `_effective_stale_days` | mitigate | Explicit `is not None` check, same pattern as T-06-07 (reports.py:132-141) | closed |
| T-06-14 | Information Disclosure | `stale_products` query scope | accept | Deliberately excludes soft-deleted products (`.where(Product.deleted_at.is_(None))`, reports.py:189) — a scope decision, not a security control failure | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-06-01 | T-06-06 | Product/category names in sales & top-selling reports rely on Jinja autoescape only; no untrusted multi-tenant boundary in v1 | operator (plan-time disposition) | 2026-07-10 |
| AR-06-02 | T-06-08 | `/reports/stock` has no access control; duplicates data already visible on `/products`; single local operator | operator (plan-time disposition) | 2026-07-10 |
| AR-06-03 | T-06-11 | CSV exports are full unfiltered dumps including soft-deleted rows — explicit design intent for single-operator data portability; WR-01 fix keeps deleted rows distinguishable | operator (plan-time disposition) | 2026-07-10 |
| AR-06-04 | T-06-12 | `reason_code` labels sourced from operation payload, validated against `WRITEOFF_REASONS` at both write time (Phase 5) and read time; never rendered with `\|safe` | operator (plan-time disposition) | 2026-07-10 |
| AR-06-05 | T-06-14 | `stale_products` deliberately excludes soft-deleted products (RESEARCH Open Question 2) — a scope/UX decision, not a security gap | operator (plan-time disposition) | 2026-07-10 |

*Accepted risks do not resurface in future audit runs.*

---

## Code Review Follow-Through

Phase 6 went through `06-REVIEW.md` (1 critical, 4 warning, 4 info findings) followed by `06-REVIEW-FIX.md` (all 5 critical+warning findings fixed, 0 skipped). Of direct security relevance:
- **CR-01** (critical): `consultant_number` bypassed `_csv_safe` in `stream_customers_csv` — fixed in commit `0278925`, closing T-06-10 fully across all three exports.
- **WR-03**: `parse_optional_int` had no upper-bound check (int32 overflow risk on future PostgreSQL migration) — fixed in commit `7e981cb`, now enforced as part of T-06-01's mitigation.
- **WR-04**: `parse_optional_cents` accepted negative amounts with no validation — fixed in commit `77fcbdf`; related input-validation hardening, not itself a registered Phase 6 threat.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-10 | 14 | 14 | 0 | gsd-security-auditor |

Verification run: `uv run pytest tests/test_export.py tests/test_reports.py tests/test_catalog.py -q` → 76 passed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-10
