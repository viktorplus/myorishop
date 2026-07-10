# Phase 2: Catalog, Dictionary & Search - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning
**Mode:** Autonomous (recommended answers auto-accepted per user's full-auto directive)

<domain>
## Phase Boundary

Product catalog management on top of the Phase 1 foundation: create/edit product cards, reference dictionary (code → name) with auto-fill, instant search by partial code or name, and visible price history. No receipts/sales yet (Phases 3–4). All writes that change prices go through the operations ledger.

</domain>

<decisions>
## Implementation Decisions

### Product Cards
- Pages: /products (list + search), /products/new (create), /products/{id}/edit (edit); product card detail shows price history
- Fields: code (required, unique among non-deleted), name (required), category (optional free text with datalist suggestions from existing categories), cost_cents, sale_cents, catalog_cents (all optional)
- Soft delete via deleted_at; deleted products hidden from lists/search; operations on soft-deleted products are REJECTED in the service layer (resolves review finding IN-01)
- Direct stock quantity editing stays impossible (corrections only, Phase 5)

### Reference Dictionary
- Separate `dictionary` table: code (PK, TEXT), name (TEXT) — pre-loadable code→name reference, editable via simple UI page /dictionary (add/edit rows, paste-friendly)
- On product create / receipt forms: typing a known code auto-fills name via HTMX GET lookup (debounced ~300ms)
- Dictionary is a helper only; products remain the catalog source of truth

### Search
- Instant search on /products: single input, HTMX-driven partial results (debounced ~300ms), case-insensitive LIKE on code prefix and name substring
- Results ranked: exact code match first, code prefix next, name substring last; cap 20 rows
- Cyrillic case-insensitivity: normalize with Python-side lower() comparison via SQLAlchemy func.lower (SQLite NOCASE is ASCII-only) — store a lowercase shadow column `name_lc` maintained by the service layer for indexable search

### Price History
- Price changes recorded as ledger operations (type `price_change`, qty_delta=0) with payload {field, old_cents, new_cents}; product row updated in same transaction via the single write path (extend app/services — catalog service calls ledger)
- Product card shows price history table (when, who, field, old → new) read from operations
- Creating a product records operation type `product_created` (qty_delta=0) for audit; editing non-price fields records `product_edited` with changed fields in payload

### Claude's Discretion
- Exact template structure, pagination (optional if list is long), empty-state texts
- Migration numbering and index choices (index on products.code, products.name_lc)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/services/ledger.py — record_operation single write path (extend/reuse; do NOT bypass)
- app/db.py (engine + PRAGMAs + APPEND_ONLY_TRIGGERS), app/core.py (to_cents ROUND_HALF_UP, format_cents, utcnow_iso, new_id)
- app/templates/base.html (RU layout, vendored htmx), partials pattern from ledger_rows.html
- tests/conftest.py fixtures (tmp-path SQLite engine, session, seeded product, TestClient)

### Established Patterns
- Thin routes / fat services; typed Form inputs; HTMX partials; autoescape, no |safe; ruff + pytest gates
- Alembic migrations frozen (no imports of mutable app constants) — follow migration 0001 style

### Integration Points
- New migration 0002: dictionary table, products.name_lc + indexes; new operation types accepted by ledger service
- routes: app/routes/products.py, app/routes/dictionary.py; nav link in base.html

</code_context>

<specifics>
## Specific Ideas

- UI text Russian; fast entry with minimal clicks (core value)
- Money input accepts both comma and dot decimal separator (to_cents already handles)

</specifics>

<deferred>
## Deferred Ideas

- Barcode input — out of scope (v1)
- Excel import of dictionary — out of scope per user decision (manual entry); paste-friendly UI is the concession
- Operations on soft-deleted products semantics beyond rejection (restore flow) — minimal restore link on product card is Claude's discretion

</deferred>
