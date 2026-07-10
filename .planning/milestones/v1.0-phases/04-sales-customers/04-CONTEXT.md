# Phase 4: Sales & Customers - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Advisor (grounded recommendations; external research skipped — well-understood local CRUD domain on established patterns). User decided each of the four gray areas interactively.

<domain>
## Phase Boundary

Selling products through the append-only ledger, plus customer profiles. Operator records a sale (as a multi-line basket) by product code with quantity; each line is a `sale` operation (qty_delta < 0) so stock decreases and the sale is saved to history. Sale price can be overridden per line (SAL-02). Each sale line snapshots unit cost and unit sale price at sale time so profit reports stay correct after later price changes (SAL-05). Selling more than is in stock triggers a warning with explicit confirm-to-proceed (SAL-04). A sale can optionally be linked to a customer (SAL-03); operator can create/edit customer profiles (name, surname, consultant number) — CST-01 — and view a customer's purchase history: what, when, at what price (CST-02).

**Not in this phase:** write-off, sale-linked return, stock correction, full operation-history browsing (Phase 5); reports and CSV export (Phase 6); purchase-frequency reminders / interested-customers lists (deferred CST-V2-01/02).

</domain>

<decisions>
## Implementation Decisions

### Sale Entry Flow
- **D-01:** Sale is a **basket (multi-line)**: one sale = several product lines to (at most) one optional customer — matches how an Oriflame reseller fills a catalog order and keeps customer history as one order. (User chose basket over the simpler single-line "save & next".)
- **D-02:** Fast entry lives *inside* the basket: add a line (code → name/prices auto-fill, quantity, sale price), add another, then one "Оформить продажу" (Finalize) writes all lines + attaches the customer in ONE transaction. Reuse the receipt form's autofill/focus ergonomics per line (D-02/D-03 of Phase 3).
- **D-03:** Sale header + lines: a sale/order **header** record (id UUID, optional customer_id, created_at/created_by) groups the lines; each product line is a `sale` **operation** (qty_delta < 0) linked back to the header. Exact link mechanism (dedicated `sale_id` column on operations vs payload vs a `sale_lines` table) is a schema decision for research/planning — the constraint is: stock is still computed ONLY from ledger `sale` operations, and the header must be reconstructable/portable for future sync. Empty basket cannot be finalized.

### Customer Linking (SAL-03, CST-01)
- **D-04:** Customer is **optional** — a walk-in sale with no customer is valid.
- **D-05:** In the sale form: search existing customers (HTMX autocomplete, reuse the 204/debounce lookup pattern) **and** quick-create a new customer inline (name, surname, consultant number) without leaving the sale.
- **D-06:** Separate `/customers` page for full CRUD (create/edit/list) and the customer detail view.
- **D-07:** New `customers` table: id (UUID), name, surname, consultant_number, created_at/updated_at, plus a lowercase shadow for Cyrillic-safe search consistent with Phase 2's `name_lc` approach (planner's discretion on exact columns/indexes).

### Oversell Warning (SAL-04)
- **D-08:** On finalize, if any line sells more than current stock, show an inline warning (which product, available vs requested) with an explicit **«Продать всё равно»** confirm button. No silent block.
- **D-09:** After confirmation the sale proceeds and stock **may go negative** — the ledger is the source of truth; a later correction (Phase 5) fixes counts. (User chose allow-negative over hard floor-at-zero.)

### Price & Cost Snapshot (SAL-02, SAL-05)
- **D-10:** Sale price per line **pre-fills from the product card** `sale_cents` and is **editable per line** (SAL-02). The snapshot stored on the `sale` operation is the actual entered price (`unit_price_cents`).
- **D-11:** Unit **cost is frozen** from the product card `cost_cents` at the moment of sale into `unit_cost_cents` (SAL-05) — profit reports stay correct after later price changes.
- **D-12:** If the card `cost_cents` is empty (NULL), store the snapshot as **NULL** and show profit as «неизвестна» — the sale is NOT blocked (keeps fast entry). Sale price NULL should not be allowed (a sale needs a price); planner confirms validation.

### Claude's Discretion
- Exact templates/partials structure, basket UI layout, empty-state and confirmation texts (RU)
- Migration numbering (0004+) and index choices; whether sale lines are a table or payload-linked operations
- Where/how the oversell check runs (per-line as added vs at finalize) — must warn+confirm before any negative write
- Customer purchase-history view layout on the customer detail page (must show product, date, quantity, unit price per CST-02)
- Whether the recent-sales list is a partial under the form or its own view

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (patterns to reuse)
- `.planning/phases/01-foundation-ledger-core/01-CONTEXT.md` — ledger single write path, money(int cents)/UUID/UTC conventions, append-only triggers
- `.planning/phases/02-catalog-dictionary-search/02-CONTEXT.md` — dictionary 204 lookup pattern, `name_lc` Cyrillic-safe search, price_change ops, soft-delete rejection (IN-01)
- `.planning/phases/03-goods-receipt-backup/03-CONTEXT.md` — receipt "save & next" fast-entry form, autofill/focus ergonomics, one-transaction ledger write (closest analog to the sale line)

### Project docs
- `.planning/REQUIREMENTS.md` — SAL-01..SAL-05, CST-01, CST-02 definitions (and deferred CST-V2-01/02)
- `.planning/ROADMAP.md` — Phase 4 goal + success criteria
- `.planning/PROJECT.md` — core value (fast, reliable entry; correct profit), out-of-scope decisions

No external specs/ADRs — requirements fully captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/ledger.py` — `record_operation` single write path; `OPERATION_TYPES` already includes `"sale"` (`app/models.py:34`); `compute_stock`/`rebuild_stock` for stock reads and oversell checks
- `app/models.py` — `Operation` already has `unit_cost_cents` + `unit_price_cents` (SAL-05 snapshot fields) and JSON `payload`; `Product.cost_cents/sale_cents/catalog_cents`, `quantity`
- `app/services/receipts.py` + `app/routes/receipts.py` + `app/templates/pages/receipt_form.html` (+ partials `receipt_lookup.html`, `receipt_price_inputs.html`, `receipt_rows.html`) — closest analog for the per-line sale form, autofill, and recent-list partials
- `app/services/dictionary.py` + `GET /dictionary/lookup` (204 pattern) — name auto-fill on code entry
- `app/services/catalog.py` — `parse_optional_cents`, price fields, soft-delete guard
- `app/core.py` — `to_cents` (comma/dot), `format_cents`, `utcnow_iso`, `new_id`
- `tests/conftest.py` — tmp-path SQLite engine, session, seeded product, TestClient fixtures

### Established Patterns
- Thin routes / fat services; typed `Form(...)` inputs; HTMX partials; RU UI text; autoescape (no `|safe`); ruff + pytest gates
- ALL stock changes only through the ledger service, staged with `commit=False`, ONE commit per request (WR-03)
- Alembic migrations frozen (no imports of mutable app constants) — follow 0001/0002/0003 style; SQLite `render_as_batch=True`
- Money as integer cents; UUID PKs; UTC ISO text timestamps

### Integration Points
- New migration 0004: `customers` table (+ lowercase shadow/index); sale-header structure and the operation↔header link
- New: `app/services/sales.py`, `app/services/customers.py`; `app/routes/sales.py`, `app/routes/customers.py`; templates for sale (basket) form + customer pages; nav links in `base.html`
- Ledger service accepts `sale` ops (qty_delta < 0) — extend/reuse, do NOT bypass

</code_context>

<specifics>
## Specific Ideas

- Core value = fast, correct entry: keep per-line entry quick (autofill, comma/dot money input) even inside the basket; one commit finalizes the whole sale.
- UI text in Russian throughout.
- Profit correctness is the point of the cost snapshot — never recompute profit from current card prices; always read the frozen `unit_cost_cents`/`unit_price_cents`.

</specifics>

<deferred>
## Deferred Ideas

- Purchase-frequency analysis + "customer running low" reminders — CST-V2-01, later milestone (needs months of history)
- On goods receipt, surface likely-interested customers — CST-V2-02, later milestone
- Sale-linked returns, write-offs, stock corrections, full history browsing — Phase 5
- Sales/profit/customer reports and CSV export — Phase 6
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-Sales & Customers*
*Context gathered: 2026-07-09*
