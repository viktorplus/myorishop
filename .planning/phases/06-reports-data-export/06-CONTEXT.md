# Phase 6: Reports & Data Export - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Advisor (grounded recommendations; external research skipped — well-understood local reporting/CSV domain, same precedent as Phases 4 and 5). User decided each of the four gray areas interactively.

<domain>
## Phase Boundary

Read-only reporting over the existing operations ledger, plus flat-file data export. Operator can view sales/profit for a day/week/month/custom period (RPT-01), current stock levels including a low-stock list (RPT-02), write-off reports for a period (RPT-03), top-selling and long-unsold ("stale") products (RPT-04), and export products/sales/customers to CSV (BCK-02).

**Not in this phase:** any new operation types or ledger writes (this phase is 100% read-only over data already captured by Phases 1–5); date-range filtering on `/history` itself (still out of scope — reports are separate views, not a `/history` upgrade); purchase-frequency reminders / interested-customer lists (deferred CST-V2-01/02); multi-currency, sync, roles (out of scope per PROJECT.md).

</domain>

<decisions>
## Implementation Decisions

### Period selection & local-day boundaries (RPT-01)
- **D-01:** Preset buttons (Сегодня / Неделя / Месяц) pre-fill an editable "с/по" (from/to) date range — one code path always: two date query params. User can adjust the dates after clicking a preset. (Chosen over a mode-toggle radio and over plain date-inputs-only.)
- **D-02:** **Local-day boundary correctness is mandatory regardless of UI**: operations are stored as UTC ISO text (`Operation.created_at`); "day/week/month" boundaries MUST be computed by converting local midnight (via `ZoneInfo(settings.display_tz)`, same tz already used by `iso_to_local`) to UTC before filtering — never slice the UTC string by date directly, or evening sales shift into the wrong day's report.

### Report page structure (RPT-01..04)
- **D-03:** **Separate page per report type** (e.g. `/reports/sales`, `/reports/stock`, `/reports/writeoffs`, `/reports/products`), each with its own nav entry — matches the existing project convention of one route+template+nav-link per capability (`/receipts`, `/sales`, `/writeoff`, `/returns`, `/corrections`, `/history`). (Chosen over one unified dashboard and over a single tabbed HTMX page.) The stock/low-stock report (RPT-02) does not need a period selector at all — keeping it a separate page avoids mixing period-based and non-period reports on one screen.
- Planner's discretion: exact URLs, whether a `/reports` landing page links out to the four report pages, or nav lists them directly.

### Low-stock & stale-product thresholds (RPT-02, RPT-04)
- **D-04:** **Both thresholds are per-product, configurable on the product card** — not global-only settings, not hardcoded. This requires a schema change: new nullable columns on `products` (e.g. `low_stock_threshold`, `stale_days`) plus product-form fields to set them (planner's discretion on exact column names/migration number).
- **D-05:** **Global fallback default** from settings (e.g. `settings.low_stock_threshold`, `settings.stale_days`) applies to any product whose per-product field is empty/NULL — so products never silently drop out of the "мало/залежалось" report just because the operator hasn't set a per-product value yet. Effective threshold = per-product value if set, else the global default.

### CSV export (BCK-02)
- **D-06:** **Three separate CSV files** (products.csv, sales.csv, customers.csv), each its own download button, on a **dedicated `/export` page** — mirrors the existing `/backup` page pattern (dedicated route, simple list/buttons). (Chosen over a combined ZIP archive and over scattering export buttons across existing pages.)
- **D-07:** Each CSV is a streamed `StreamingResponse` built with `csv.writer`, encoded **`utf-8-sig`** (UTF-8 with BOM) so Cyrillic product/customer names open correctly in Excel — this is a hard technical requirement, not a style choice.

### Claude's Discretion
- Exact URLs/route names, template/partial structure for each report page.
- Migration number and exact column names for the per-product threshold fields (D-04).
- Names/keys of the new global fallback settings (D-05).
- Sales/profit report grouping and layout details (e.g. whether profit is shown per line, per product, or only as a period total) — must use the frozen `unit_cost_cents`/`unit_price_cents` snapshot per SAL-05, never recompute from current product card prices.
- Write-off report grouping — group by the existing `reason_code` categories from Phase 5 (`damaged`/`expired`/`lost`/`personal`/`gift`/`other`), since that's what those categories were designed for (05-CONTEXT.md D-03).
- Top-selling ranking metric (units vs revenue vs profit) and lookback window for RPT-04 — default recommendation: rank by units sold within the selected report period; "stale" uses `stale_days` independent of the period selector (it's about recency of last sale, not a report period).
- Exact CSV column sets for each entity export.
- RU UI text, empty-state and confirmation wording.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (patterns to reuse)
- `.planning/phases/01-foundation-ledger-core/01-CONTEXT.md` — ledger single write path, money(int cents)/UUID/UTC conventions (this phase reads these conventions, writes none).
- `.planning/phases/02-catalog-dictionary-search/02-CONTEXT.md` — `name_lc` Cyrillic-safe search/sort pattern (relevant to CSV export ordering and product listing in reports).
- `.planning/phases/04-sales-customers/04-CONTEXT.md` — D-11/D-12: frozen `unit_cost_cents`/`unit_price_cents` snapshot per sale line — sales/profit reports MUST read these frozen values, never the current product card prices (SAL-05 guarantee).
- `.planning/phases/05-stock-operations-history/05-CONTEXT.md` — D-01..D-03: write-off `reason_code` category set (`damaged`/`expired`/`lost`/`personal`/`gift`/`other`) is the exact grouping key for the write-off report (RPT-03); D-14: date-range filtering was deliberately deferred from `/history` to this phase's period reporting — but reports are separate pages (D-03 above), not a `/history` upgrade.

### Project docs
- `.planning/REQUIREMENTS.md` — RPT-01..RPT-04, BCK-02 definitions; "Direct editing of stock quantity" and other out-of-scope items still apply (unchanged by this phase).
- `.planning/ROADMAP.md` — Phase 6 goal + the 5 success criteria (`## Phase 6: Reports & Data Export`).
- `.planning/PROJECT.md` — core value (correct stock & profit figures), single-currency/single-operator constraints.

No external specs/ADRs — requirements fully captured in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/operations.py` — `history_view()` (paginated, filtered ledger read: `select(Operation, Product).join(...)`, `OPERATION_TYPES` filter, has-next-sentinel pagination) — the closest analog for building period-filtered report queries; `filter_products()` for a product picker.
- `app/models.py` — `Operation` (`type`, `qty_delta`, `unit_cost_cents`, `unit_price_cents`, `payload`, `sale_id`, `created_at`), `OPERATION_TYPE_LABELS` / `WRITEOFF_REASONS` (RU label constants, already exposed as Jinja globals via `app/routes/__init__.py`), `Product` (`quantity`, `cost_cents`, `sale_cents`, `catalog_cents`, `deleted_at`), `Sale` (header, `customer_id`), `Customer`.
- `app/core.py` — `utcnow_iso`, `iso_to_local`, `format_cents`, `to_cents`; `ZoneInfo` already imported here — reuse for local-day boundary math (D-02).
- `app/config.py` (`settings`) — `display_tz`, `backup_keep`, `backup_dir` etc. already live here via pydantic-settings; add the new fallback threshold settings (D-05) the same way.
- `app/services/backup.py` — `list_backups()` / `_size_label()` pattern and the `/backup` page structure (`app/templates/pages/backup.html`, `partials/backup_list.html`) — direct template for the new `/export` page (D-06) and its file-listing UX (though export produces CSV, not DB copies).
- `app/routes/__init__.py` — shared `templates` env with `local_dt` / `cents` filters and RU-label globals — reuse in every new report template, do not re-instantiate `Jinja2Templates`.
- `tests/conftest.py` — tmp SQLite engine, session, seeded product, TestClient fixtures.

### Established Patterns
- Thin routes / fat services; typed `Form(...)` inputs where forms exist (reports are mostly query-param GETs); HTMX partials for rows tables; RU UI text; autoescape (no `|safe`); ruff + pytest gates.
- Read-only services are plain `select()` over SQLAlchemy Core/ORM — no SQLite-specific SQL (portable to future PostgreSQL sync target).
- Alembic migrations frozen (no imports of mutable app constants); SQLite `render_as_batch=True`; follow 0001–0005 numbering style. This phase's migration adds the two nullable per-product threshold columns (D-04) — first schema change purely for reporting.
- Money as integer cents; UUID PKs; UTC ISO text timestamps; Cyrillic-safe lowercase shadows (`name_lc`, `search_lc`) for search/sort — CSV export should sort using these shadows where relevant.

### Integration Points
- New services: likely `app/services/reports.py` (sales/profit, write-offs, top/stale) and `app/services/stock.py` or folded into `reports.py` (current levels + low-stock); `app/services/export.py` for CSV streaming.
- New routes: one route module per report page (or a `reports.py` router with multiple paths) + `app/routes/export.py`; new templates under `app/templates/pages/` per D-03; nav links in `base.html`.
- New migration: nullable `low_stock_threshold` / `stale_days` (or similar) columns on `products` (D-04) + corresponding `app/config.py` fallback settings (D-05).
- CSV export uses FastAPI `StreamingResponse` + Python `csv.writer`, `utf-8-sig` encoding (D-07) — no new dependency needed (csv is stdlib).

</code_context>

<specifics>
## Specific Ideas

- Reports must never recompute profit from current product-card prices — always read the frozen `unit_cost_cents`/`unit_price_cents` snapshot on each `sale` operation (carries forward SAL-05 from Phase 4).
- Write-off report groups by the exact `reason_code` set already established in Phase 5, in Russian label form via the existing `WRITEOFF_REASONS` constant.
- UI text in Russian throughout; CSV files must open correctly in Excel with Cyrillic (`utf-8-sig`).
- `/export` page should feel like a sibling of `/backup` — same "simple page listing available downloads" ergonomics the operator already knows.

</specifics>

<deferred>
## Deferred Ideas

- Date-range filtering directly on `/history` — stays deferred; period reporting lives in the new `/reports/*` pages instead (per Phase 5 D-14, resolved here as "separate pages", not a `/history` upgrade).
- Combined ZIP export, single-dashboard report layout, global-only (non-per-product) thresholds — considered and explicitly not chosen (see Implementation Decisions above).
- Purchase-frequency reminders / interested-customer lists — CST-V2-01/02, later milestone.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Reports & Data Export*
*Context gathered: 2026-07-10*
