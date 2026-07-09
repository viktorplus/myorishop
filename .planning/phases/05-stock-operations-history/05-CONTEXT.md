# Phase 5: Stock Operations & History - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Advisor (grounded recommendations; external research skipped — well-understood local-CRUD domain on established ledger patterns). User decided each of the four gray areas interactively.

<domain>
## Phase Boundary

Every non-sale stock movement plus the full audit trail, all written through the append-only ledger:

- **Write-off (OPS-01):** operator removes stock with a reason; a `writeoff` operation (qty_delta < 0) decreases stock.
- **Return (OPS-02):** operator registers a return linked to the original sale; a `return` operation (qty_delta > 0) increases stock.
- **Correction (OPS-03):** operator corrects stock quantity; the adjustment is recorded as a `correction` operation, never a direct edit of `products.quantity`.
- **History (OPS-04):** operator browses the full operation history — what, when, how much — across all products.

**Not in this phase:** period reports (sales/profit/stock/write-off/top/stale) and CSV export → Phase 6 (RPT-01..04, BCK-02). The write-off *report* is Phase 6; this phase only captures the reason so that report can group later. Purchase-frequency reminders / interested-customer lists remain deferred (CST-V2-01/02).

</domain>

<decisions>
## Implementation Decisions

### Write-off — reason capture (OPS-01)
- **D-01:** Reason is a **hybrid**: a **required category** from a fixed list + an **optional free-text note**. (User chose hybrid over free-text-only or categories-only.)
- **D-02:** Both stored in the operation `payload` — proposed shape `{"reason_code": "<latin>", "note": "<free text or empty>"}`. `reason_code` values are Latin/portable; RU labels live in a code constant for the dropdown (mirrors how UI text is kept RU while stored values stay portable).
- **D-03:** Default category set (RU label → code), adjustable by planner if the operator wants different wording: Брак → `damaged`, Просрочка → `expired`, Потеря → `lost`, Личное использование → `personal`, Подарок → `gift`, Прочее → `other`. `other` is the escape hatch that pairs naturally with the note. This set is what Phase 6's RPT-03 report will group by.
- **D-04:** Write-off is by product code (reuse the receipt/sale lookup + name autofill ergonomics), quantity required (positive int), no price fields. Stock may go to/through zero — consistent with the ledger-is-truth stance from Phase 4 (D-09); a later correction fixes counts if needed. Planner confirms whether an oversell-style warning is shown on write-off (recommended: warn but allow, reusing the Phase 4 confirm pattern — Claude's discretion).

### Return — sale linking (OPS-02)
- **D-05:** Return **starts from a line of the original sale** (user chose this over a standalone code form or an unlinked return). Entry point: the recent-sales list and/or a customer's purchase history (both already render `sale` operations — `partials/recent_sales.html`, `partials/purchase_history.html`). Operator picks the sale line to return.
- **D-06:** The return is a `return` operation with **qty_delta > 0**, carrying `sale_id` = the original `Sale.id` (the `Operation.sale_id` column already exists) and `product_id` = the sold product. It links back to the exact origin so OPS-02's "linked to the original sale" is literally true.
- **D-07:** **Price/cost symmetry:** the return copies `unit_price_cents` and `unit_cost_cents` **from the original sale line's snapshot** (not from the current product card). A return therefore reverses exactly the frozen amounts the sale recorded — profit stays correct after later price changes (preserves the SAL-05 guarantee from Phase 4).
- **D-08:** **Partial returns allowed.** The returnable quantity for a line = quantity sold on that line − quantity already returned against it. The service must aggregate prior `return` ops for that `sale_id`+`product_id` so an operator cannot return more than was sold (or more than remains returnable). Planner decides exact aggregation (by sale line vs by sale+product) — the constraint is: returned qty ≤ remaining returnable.

### Correction — input mode (OPS-03)
- **D-09:** **Both input modes** offered (user chose this over count-only or delta-only):
  - **Counted quantity (absolute):** operator enters the physically counted stock; system computes `qty_delta = counted − current_quantity` and writes it as a `correction` op. Show the current cached quantity next to the input so the operator sees what they're adjusting from. Natural for stocktakes, avoids sign mistakes.
  - **Delta (+/−):** operator enters the difference directly; written as-is. This is the existing draft behavior.
- **D-10:** Correction is **always recorded as a `correction` operation**, never a direct edit of `products.quantity` (OPS-03 core rule; the single write path `record_operation` already enforces this). A zero net delta should be a no-op / rejected gracefully (nothing to record).
- **D-11:** Optional reason/note for the correction in `payload` (e.g. `{"note": "...", "mode": "count"|"delta"}`). Recommended default mode in the UI = counted quantity (safer); delta is the secondary toggle — planner's discretion on default selection.
- **D-12:** This **replaces the walking-skeleton `POST /ops`** correction (`app/routes/ops.py`, which takes a raw `qty_delta` with no reason and renders the single-product home ledger). Migrate its behavior into the real correction flow; do not leave two correction paths.

### History browsing (OPS-04)
- **D-13:** A **dedicated `/history` page** (user chose this over extending home or per-card only): all operations, all products, newest first.
- **D-14:** **Filters:** by operation type and by product. **Date-range filtering is deferred to Phase 6** (that's where period reporting lives) — Phase 5 ships type + product filters only, to avoid duplicating the reports work.
- **D-15:** **Pagination / limit** so the ledger stays fast as it grows (e.g. 50 rows/page or "load more" — planner's discretion on mechanism; must not load the entire ledger unbounded like the current 50-row home view does implicitly).
- **D-16:** **Columns:** type (RU-labeled), product (name/code), quantity (signed ±), unit price / unit cost where present, reason (from `payload` — category + note for write-offs, note for corrections), who (`created_by`), when (`created_at | local_dt`). Reuse and extend `partials/ledger_rows.html`.
- **D-17:** Add a **nav link** in `base.html` (e.g. «История» / «Операции»). The home page's single-product ledger view can stay as-is or be simplified — Claude's discretion — but the authoritative full history is `/history`.

### Claude's Discretion
- Page/route/template structure and naming: whether write-off, return, and correction are three separate pages/forms or share a shell; exact URLs (e.g. `/writeoff`, `/returns`, `/corrections`, `/history`).
- Migration number **0005** if any schema is needed — but note: `writeoff`/`return`/`correction` are **already in `OPERATION_TYPES`** and `Operation.sale_id`/`payload` already exist, so **no schema change is expected** for the core flows. Only add a migration if a genuinely new column/index is justified (e.g. an index to speed the returnable-qty aggregation) — otherwise none.
- Exact RU UI text, empty-state and confirmation wording; layout of each form.
- Whether write-off shows an oversell-style warn/confirm (recommended: yes, reuse Phase 4 pattern) and floor behavior.
- Default correction input mode in the UI (recommended: counted quantity).
- Pagination mechanism and page size for `/history`; whether a per-product history view is also surfaced on the product card (optional, not required by OPS-04).
- Exact `payload` key names/shape (proposals above are guidance, not locked schema).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (patterns to reuse)
- `.planning/phases/01-foundation-ledger-core/01-CONTEXT.md` — ledger single write path, append-only triggers (no UPDATE/DELETE on operations), money(int cents)/UUID/UTC conventions.
- `.planning/phases/02-catalog-dictionary-search/02-CONTEXT.md` — 204 lookup pattern, `name_lc` Cyrillic-safe search, soft-delete rejection (IN-01), price_change ops.
- `.planning/phases/03-goods-receipt-backup/03-CONTEXT.md` — code→name autofill + focus ergonomics, one-transaction ledger write (closest analog for the write-off entry form).
- `.planning/phases/04-sales-customers/04-CONTEXT.md` — sale header + `sale` operations + `Operation.sale_id` link, frozen `unit_cost_cents`/`unit_price_cents` snapshot (D-11/D-12), oversell warn/confirm + allow-negative (D-08/D-09), `recent_sales`/`purchase_history` partials (return entry points).

### Project docs
- `.planning/REQUIREMENTS.md` — OPS-01..OPS-04 definitions; note RPT-03 (write-off report) and BCK-02 (CSV) are Phase 6, and "Direct editing of stock quantity" is explicitly out of scope (corrections go through OPS-03).
- `.planning/ROADMAP.md` — Phase 5 goal + the 4 success criteria.
- `.planning/PROJECT.md` — core value (fast, reliable entry; correct stock & profit), ledger-is-source-of-truth stance.

No external specs/ADRs — requirements fully captured in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/ledger.py` — `record_operation` (single write path; accepts `type_`, `qty_delta` signed, `unit_cost_cents`, `unit_price_cents`, `payload`, `sale_id`, `commit`); `compute_stock` / `rebuild_stock` for ledger-derived stock; `ledger_view` (current single-product home view — to be superseded by `/history`).
- `app/models.py` — `OPERATION_TYPES` **already includes** `writeoff`, `return`, `correction`; `Operation` has `qty_delta`, `unit_cost_cents`, `unit_price_cents`, `payload` (JSON), and `sale_id` (FK → sales.id, set at INSERT only). No new operation types or columns needed for the core flows.
- `app/services/sales.py` — `recent_sales(session, limit)` returns `sale` ops joined to products (return entry point); the register_sale snapshot logic (D-10/D-11) is the model for return's price/cost copy.
- `app/services/customers.py` + `app/templates/partials/purchase_history.html` — customer purchase history (per-customer return entry point; shows product/date/qty/unit price).
- `app/services/receipts.py` + `app/templates/pages/receipt_form.html` (+ `receipt_lookup.html`, `receipt_price_inputs.html`) — closest analog for the write-off form's code→name autofill.
- `app/services/dictionary.py` + `GET /dictionary/lookup` (204 pattern) — name autofill on code entry.
- `app/core.py` — `to_cents` (comma/dot), `format_cents`, `utcnow_iso`, `new_id`; `local_dt` Jinja filter for timestamps.
- `app/templates/partials/ledger_rows.html` — extend for the `/history` table (currently: type, qty, who, when — add product, price/cost, reason).
- `app/routes/ops.py` — the walking-skeleton `POST /ops` correction to be replaced by the real correction flow (D-12).
- `tests/conftest.py` — tmp SQLite engine, session, seeded product, TestClient fixtures.

### Established Patterns
- Thin routes / fat services; typed `Form(...)` inputs; HTMX partials; RU UI text; autoescape (no `|safe`); ruff + pytest gates.
- ALL stock changes only through `record_operation`, staged `commit=False`, ONE commit per request (WR-03). Operations are append-only (DB triggers ABORT UPDATE/DELETE) — a return/correction is a NEW row, never a mutation.
- Money as integer cents; UUID PKs; UTC ISO text timestamps; Cyrillic-safe lowercase shadows for search.
- Alembic migrations frozen (no imports of mutable app constants); SQLite `render_as_batch=True`; follow 0001–0004 style. Migration 0005 only if a genuinely new column/index is justified (likely none).

### Integration Points
- New services: `app/services/writeoffs.py`, `app/services/returns.py`, and correction logic (new `app/services/corrections.py` or fold into an operations service) — all built on `record_operation`.
- New routes/templates: write-off form, return-from-sale flow, correction form, and `/history` page + filter partials; nav links in `base.html`.
- Return must aggregate prior `return` ops per `sale_id`+`product_id` to enforce the returnable-qty cap (D-08) — an index on `operations.sale_id` already exists.
- `POST /ops` (home correction) is superseded — migrate, don't duplicate.

</code_context>

<specifics>
## Specific Ideas

- Ledger-is-truth carries into every op here: returns and corrections are new immutable rows; profit correctness comes from copying the sale line's frozen snapshot on return (never recompute from current card prices).
- Fast entry ergonomics from receipts/sales (code→name autofill, comma/dot money input, per-line focus) apply to the write-off form.
- Reason capture is designed for Phase 6: write-off `reason_code` categories are the exact grouping keys RPT-03 will report on.
- UI text in Russian throughout; stored codes in Latin for portability.

</specifics>

<deferred>
## Deferred Ideas

- Write-off / sales / profit / stock reports and CSV export — Phase 6 (RPT-01..04, BCK-02). This phase only captures the data (reasons, operations) those reports consume.
- Date-range filtering on history — folded into Phase 6's period reporting rather than duplicated here (D-14).
- Per-product history view on the product card — optional, not required by OPS-04 (Claude's discretion).
- Purchase-frequency reminders / interested-customer lists — CST-V2-01/02, later milestone.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.

</deferred>

---

*Phase: 5-Stock Operations & History*
*Context gathered: 2026-07-09*
