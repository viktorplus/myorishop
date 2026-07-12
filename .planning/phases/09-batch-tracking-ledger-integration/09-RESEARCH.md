# Phase 9: Batch Tracking & Ledger Integration - Research

**Researched:** 2026-07-11
**Domain:** Batch/lot-level stock tracking retrofitted onto an append-only SQLite ledger (FastAPI + SQLAlchemy 2.0 + Alembic + HTMX 2.x server-rendered forms)
**Confidence:** HIGH — grounded in direct reading of the live codebase (services, routes, templates, migrations 0001/0004/0007, test suite) plus targeted external verification (MDN date-input format, SQLite NULLS LAST support verified by executing a query against the project venv's SQLite 3.50.4)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Batch creation & receipt flow
- **D-01:** Batch creation is **resolve-or-create with operator choice**: after the product code AND warehouse are set on a receipt line, an HTMX lookup loads that product's open batches (quantity > 0) in that warehouse; the operator explicitly chooses "top up an existing batch" or "new batch" (the new-batch fields — expiry, location, comment — are shown only for the new-batch path). No silent server-side auto-merge (rejected: invisible matching logic contradicts the app's explicit-manual-selection philosophy; NULL-expiry equality matching is a known trap).
- **D-02:** The receipt form gains: a **required warehouse `<select>`** preselected to the Phase 8 seeded default warehouse, plus three optional fields per new batch — **expiry date** (LOT-03), **free-text storage-location tag** (WH-02, e.g. "стеллаж А3"), and **comment** (LOT-04). There is NO new price input: `Batch.price_cents` snapshots the existing "Цена продажи" field at batch creation time. Existing cost/sale/catalog semantics (op snapshot + card update) stay untouched; on a top-up the batch's frozen price is NOT rewritten (a changed typed price still updates the product card as today). Zero active warehouses → the form renders a blocking RU hint linking to warehouse creation instead of the batch picker (Phase 8 D-07 carried forward).
- **D-03:** No separate batch-management page in this phase. Batches are born only via receipts + the legacy migration; a batch disappears from pickers when its remaining quantity hits zero. `Batch` gets no soft-delete and no standalone CRUD.

#### Batch picker in operation forms (sale, write-off, return, correction)
- **D-04:** Picker presentation is an **inline batch table swapped in under the line by the code lookup** — columns: price, expiry, remaining quantity, comment (all four LOT-02 attributes readable). Selection is a radio row that syncs a per-row hidden `batch_id[]` input (customer-chip precedent) so the basket's parallel-array alignment (`code[]`/`qty[]`/`price[]`) is preserved; a 422 re-render must re-echo the picked batch per row. The same batch-list partial is reused under the single-line write-off and correction forms.
- **D-05:** Picking a batch **pre-fills the line's price with the batch's price** (replacing the current `Product.sale_cents` card pre-fill when a batch price exists), using the existing `hx-swap-oob` + "Цена подставлена — можно изменить" muted-hint convention and the typed-value before-swap guard. The operator can still override the price manually.
- **D-06:** When a product has **exactly one matching batch, it is auto-selected** — but rendered visibly highlighted with a muted note "Партия выбрана автоматически — единственная", and remains changeable. LOT-02's "manually selects" intent is preserved because the selection is visible and reversible; forcing a click on a no-choice decision only slows the operator.
- **D-07:** Batch ordering in the picker: **earliest expiry first, NULL expiry last**, tie-broken by oldest receipt. This nudges FEFO practice without auto-picking (which stays out of scope).
- **D-08:** The **return flow does NOT re-ask for a batch**: a return restores stock to the batch its origin sale line came from. The origin sale op carries its `batch_id`; the return form displays the origin batch info read-only. For pre-Phase-9 sale ops (batch_id NULL), the return targets the product's legacy batch.
- **D-09:** The per-batch oversell/over-removal warning (ROADMAP success criterion 4) plugs into the existing warn-but-allow `confirm=1` zero-write re-POST pattern unchanged — scoped to the picked batch's remaining quantity, not the product total.

#### Ledger schema & per-batch remaining quantity
- **D-10:** `Operation` gains a **nullable `batch_id` column via native `op.add_column`** — the exact precedent of migration 0004's `sale_id` (bare column, no DB-level inline FK — Alembic's SQLite dialect raises `NotImplementedError`; ORM-side `ForeignKey` only). The append-only triggers (`operations_no_update`/`operations_no_delete`) are NEVER touched and no historical row is mutated. `batch_id` on ledger rows is set at INSERT time only. Rejected: storing batch_id in the JSON `payload` (no index/FK, contradicts the repo's own `sale_id` precedent, PostgreSQL-portability friction) and backfilling old rows (mutates the ledger the whole architecture protects; risks future sync replay divergence).
- **D-11:** **`Batch.quantity` is a cached projection** maintained inside `record_operation()` exactly like the existing `Product.quantity` — SQL-side increment (`Batch.quantity + qty_delta`), same transaction, both projections updated together. `record_operation()` grows a `batch_id` parameter and stays the SINGLE write path. `rebuild_stock()` grows a per-batch pass plus the invariant check `Product.quantity == SUM(active batches' quantity)` per product.
- **D-12:** `batch_id` is **required at the service level** (raise `ValueError`) for all stock-affecting operation types (`receipt`, `sale`, `writeoff`, `return`, `correction` — qty_delta != 0); the qty_delta == 0 audit types (`price_change`, `product_created`, `product_edited`) stay batch-less (`batch_id=None`). A DB-level NOT NULL is impossible without batch-mode migration (would drop triggers) and NULL is reserved for legacy rows — so the guard lives in `record_operation()`.

#### Legacy data migration
- **D-13:** **One legacy batch per product with ledger stock > 0** (no legacy batches for zero-stock products; a single global cross-product batch rejected — a batch without product_id poisons every query and criterion 5 becomes unverifiable per product). Legacy batch quantity is seeded **from `SUM(operations.qty_delta)` computed in plain SQL in the migration — NOT from the `products.quantity` cache** — so success criterion 5 balances even against a stale cache.
- **D-14:** Legacy batch field values (frozen literals in the migration, per repo convention that migrations never import app modules): `warehouse_id` = the re-declared frozen default-warehouse UUID `00000000-0000-4000-8000-000000000010` (Phase 8 D-03 contract), `expiry` = NULL, `price_cents` = NULL (historical price unknown — the picker simply doesn't pre-fill a price for legacy batches; the card `sale_cents` pre-fill remains the fallback), name/comment = frozen string "Остаток до внедрения партий".
- **D-15:** Pre-batch operation rows stay untouched: **`batch_id` NULL means legacy**, resolved display-side. The /history view renders NULL `batch_id` with the legacy label (or a dash) at read time — attribution is a display concern, not a data rewrite.

### Claude's Discretion
- Exact `Batch` model column names and the batch-list partial filename(s).
- Exact shape of the receipt-form batch chooser UI (how "top up vs new" is rendered) within D-01's contract.
- How the per-row hidden `batch_id[]` sync is wired (`hx-on:change` vs alternative), and 422 re-echo mechanics.
- Whether the batch table on a basket line collapses/highlights after selection — any treatment that keeps the selection visible and changeable.
- Index placement for `operations.batch_id` and `batches` table indexes.
- How `compute_stock`-style per-batch recompute handles the NULL-bucket (legacy) special case in `rebuild_stock()`.

### Deferred Ideas (OUT OF SCOPE)
- "Merge batches" / batch-editing tooling — only becomes relevant if picker clutter appears despite D-01's top-up path; future milestone.
- Read-only per-product batch list on the product card or the CAT-01 stock page — nice-to-have surface, not required by LOT-01..05; can ride on a later phase.

Also explicitly out of scope (from CONTEXT.md domain boundary): warehouse transfers (WH-03), expiring-batches report (LOT-06), mobile flow (UI-01), automatic FEFO/FIFO selection, CSV batch columns (EXP-V2-01), standalone batch-management page.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WH-02 | Stock item has an optional free-text storage-location tag within its warehouse (e.g. "стеллаж А3") | `Batch.location` nullable String column, entered on the receipt form's new-batch path (D-02); see Batch model design + receipt flow pattern |
| LOT-01 | A product code can have multiple batches (lots), each with its own expiry date and price | New `batches` table keyed by product_id + warehouse_id, each row with its own `expiry`, `price_cents`, `location`, `comment`, cached `quantity`; migration 0008 design below |
| LOT-02 | At sale, operator sees a list of matching batches (price, expiry, remaining quantity, comment) and manually selects one | Inline batch-table picker swapped in by `/sales/lookup` (Pattern 2), `batch_id[]` parallel-array wiring (Pattern 3), D-06 single-batch auto-select, D-07 nullslast ordering (verified on SQLite 3.50.4) |
| LOT-03 | Optional expiry date field per batch | `<input type="date">` posts ISO `yyyy-mm-dd` regardless of locale [CITED: developer.mozilla.org/en-US/docs/Web/HTML/Element/input/date]; store as TEXT String(10); lexicographic sort = chronological |
| LOT-04 | Optional free-text comment per batch, shown in the sale-time batch picker | `Batch.comment` nullable String; picker column per D-04 |
| LOT-05 | Write-off, return, and stock correction also require selecting the specific batch | Same batch-list partial reused under writeoff/correction forms (scalar `batch_id`); returns inherit origin op's batch (D-08); `record_operation()` ValueError guard (D-12) is the enforcement backstop |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Stack is locked: Python 3.13, FastAPI, SQLAlchemy 2.0 (`Mapped[]`/`mapped_column()` style only), SQLite, Jinja2, htmx 2.0.10 vendored — no new frameworks, no async SQLAlchemy, no SPA.
- Money is integer cents (`*_cents Integer`) — never FLOAT/REAL.
- Portable ORM constructs only — no SQLite-specific SQL (`INSERT OR REPLACE`, `strftime`) that would break the future PostgreSQL migration.
- UUID String(36) PKs on business entities; UTC ISO text timestamps.
- The append-only operations log is never UPDATEd/DELETEd.
- Migrations: the project convention (stronger than CLAUDE.md's generic `render_as_batch` note) is **native ADD COLUMN / new-table only on `operations`** — batch mode silently drops the append-only triggers (frozen warning in 0001, precedent in 0004). Migrations never import app modules.
- UI text in Russian; code/comments/commits in English.
- Optional fields checked with `is not None`, never bare `or`.
- Do not commit unless asked (GSD workflow commits planning docs; `commit_docs: true`).

## Summary

Phase 9 introduces the `batches` table as the true stock-holding unit and threads `batch_id` through the single ledger write path (`record_operation()`), all five stock-affecting operation forms, and a one-time legacy-batch data migration. All 15 architectural decisions are already locked in CONTEXT.md; this research resolves the remaining HOW: exact migration mechanics (native add_column, frozen literals, plain-SQL legacy seed — verified against the actual dev DB which holds 16 operations / 6 products / 5 products with positive ledger stock), the HTMX wiring for the per-row `batch_id[]` parallel array (hidden input lives in a dedicated always-rendered picker wrapper row so array alignment can never drift), the per-batch oversell re-keying in `register_sale`/`register_writeoff`/`register_correction`, batch inheritance for returns, and the NULL-bucket handling in `rebuild_stock()`.

Two verified external facts anchor the design: HTML `<input type="date">` always submits ISO `yyyy-mm-dd` regardless of locale (store expiry as TEXT String(10), lexicographic = chronological), and `ORDER BY ... NULLS LAST` works on the project's SQLite (3.50.4; supported since SQLite 3.30) and PostgreSQL, so SQLAlchemy `nullslast()` gives D-07's ordering portably.

The single largest hidden cost of this phase is NOT the new code — it is that D-12 (batch_id required in `record_operation` for stock-affecting types) breaks the call signature relied on by most of the existing 262-test suite and every operation service. Plans must budget a Wave-0-style pass over `tests/conftest.py` fixtures and every service test alongside the schema work, or the suite goes red and stays red.

**Primary recommendation:** Build in strict dependency order — (1) model + migration 0008 + `record_operation`/`rebuild_stock` extension with updated test fixtures, (2) receipts (batch birth path), (3) sale picker + per-batch oversell, (4) writeoff/correction/returns + /history display. Never let a plan touch the UI before the write path and its tests are green.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Batch schema + legacy seed | Database (Alembic migration 0008) | — | Frozen literals, plain SQL; migrations never import app modules |
| Batch quantity cache + batch_id guard | Service (ledger.py `record_operation`) | — | Single write path invariant (FND-01); DB NOT NULL impossible without dropping triggers (D-12) |
| Batch↔product ownership validation | Service (ledger.py) | — | Security: client-submitted batch_id is untrusted; mirrors the existing IN-01 deleted-product guard |
| Open-batch queries + D-07 ordering | Service (new batches.py) | — | Reusable across sale/writeoff/correction pickers and the receipt chooser |
| Batch picker rendering + selection | Routes + Jinja partials | Browser (htmx swaps) | Server decides content (fill-vs-204 convention); browser only swaps and syncs the hidden input |
| `batch_id[]` array alignment | Jinja templates (structural) | Browser (row delete handler) | Alignment is guaranteed structurally (input always rendered per row), not by JS discipline |
| Per-batch oversell/over-removal warn | Service (sales/writeoffs/corrections) | Routes (confirm=1 re-POST) | Existing warn-but-allow pattern, re-keyed to batch_id |
| Return batch inheritance | Service (returns.py) | — | Origin op carries batch_id; NULL → legacy batch resolution is server logic |
| Legacy display (/history) | Route/template (read-time) | — | D-15: attribution is a display concern, never a data rewrite |
| Expiry date validation | Service (parse + `date.fromisoformat`) | Browser (`<input type="date">`) | Browser gives ISO format; server must still validate (form values are untrusted) |

## Standard Stack

**No new dependencies.** This phase is built entirely on the already-installed, already-pinned stack.

### Core (existing, verified installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.* (pinned) | `Batch` model, `nullslast()` ordering, dual projection updates | Already the ORM; `nullslast()` renders portable `NULLS LAST` [VERIFIED: executed against venv SQLite 3.50.4] |
| Alembic | 1.18.* (pinned) | Migration 0008 (batches table + operations.batch_id + legacy seed) | Project convention; native add_column precedent in 0004 |
| htmx | 2.0.10 vendored | Picker swap, oob price fill, confirm=1 re-POST | All required interaction patterns already exist in-repo (lookup fill, oob swap, warn-but-allow) |
| Python stdlib `uuid` | 3.13 stdlib | Deterministic legacy-batch ids in the migration (`uuid.uuid5`) | stdlib import is allowed in migrations (the ban is on *app* modules); uuid5 makes the seed replay-deterministic per product |
| Python stdlib `datetime.date` | 3.13 stdlib | `date.fromisoformat()` server-side expiry validation | Zero-dependency ISO date validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.* | Test suite (262 tests currently collected) | Every wave; fixtures in `tests/conftest.py` need a warehouse+batch pass |
| httpx | 0.28.* | TestClient route tests | Picker fragment / 422 re-echo / confirm=1 route tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `nullslast(Batch.expiry.asc())` | `order_by(Batch.expiry.is_(None), Batch.expiry)` | Boolean-expression ordering works on any SQLite version; `nullslast()` is more explicit and verified working here — prefer it, keep the boolean form as the noted fallback if a target DB ever predates 3.30 |
| TEXT String(10) ISO expiry | `sa.Date` column | `Date` maps to TEXT in SQLite anyway; the repo convention is explicit TEXT ISO strings (timestamps already String(32)), and String(10) keeps the frozen-literal migration trivial |
| `uuid.uuid5` deterministic legacy ids | `uuid.uuid4` random ids | Both acceptable (seed is data-dependent, so replay determinism only matters per-DB); uuid5 keyed on product_id makes re-running against the same data reproducible and simplifies debugging |

**Installation:** none — `uv sync` already provides everything.

## Package Legitimacy Audit

This phase installs **zero external packages** — all work is on the existing pinned stack. The Package Legitimacy Gate is satisfied vacuously.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Receipt form                          Sale basket / Writeoff / Correction forms
  code input ──hx-get──► /receipts/lookup      code[] input ──hx-get──► /sales/lookup
  warehouse <select> ─hx-get─► /receipts/batches       │ (main: name fill; oob: batch
       │ (renders batch CHOOSER:                       │  PICKER into #batch-wrap-{row})
       │  ◉ top up existing batch rows                 ▼
       │  ◉ new batch → expiry/location/comment)   batch radio ──hx-get──► /sales/batch-pick
       ▼                                               │ (main: re-rendered picker w/ selection
  POST /receipts                                       │  + synced hidden batch_id[];
       │                                               │  oob: price fill w/ typed-value guard)
       ▼                                               ▼
  register_receipt()                              POST /sales | /writeoff | /corrections
   resolve-or-create Batch ───┐                        │
   (same txn as product        │                  per-BATCH oversell check (warn-but-allow,
    auto-create)               │                   confirm=1 zero-write re-POST) 
                               ▼                        │
                    ┌──────────────────────────────────▼─────────────────┐
                    │ record_operation(type_, product_id, qty_delta,      │
                    │                  batch_id=..., ...)                 │
                    │  • ValueError if stock-affecting type w/o batch_id  │
                    │  • ValueError if batch.product_id != product_id     │
                    │  • INSERT operation row (batch_id set at INSERT)    │
                    │  • Product.quantity  += qty_delta  (existing)       │
                    │  • Batch.quantity    += qty_delta  (NEW, same txn)  │
                    └──────────────────────┬───────────────────────────---┘
                                           ▼
                    SQLite: operations (append-only, triggers UNTOUCHED)
                            products.quantity ◄─ rollup cache
                            batches.quantity  ◄─ per-lot cache
                            (both re-derivable: rebuild_stock per-batch pass
                             + NULL-bucket legacy attribution + invariant check)

Returns: origin sale op ──► origin.batch_id (or legacy batch when NULL) ──► record_operation
/history: Operation LEFT OUTER JOIN Batch ──► NULL batch_id renders legacy label (read-time only)
```

### Recommended Project Structure (delta)

```
app/
├── models.py                      # + Batch model; + Operation.batch_id column
├── services/
│   ├── ledger.py                  # record_operation(batch_id=...), rebuild_stock per-batch pass
│   ├── batches.py                 # NEW: open_batches(), resolve legacy batch, get-and-validate helpers
│   ├── receipts.py                # warehouse select + batch resolve-or-create
│   ├── sales.py                   # batch_id[] parsing, per-batch oversell, batch price freeze source
│   ├── writeoffs.py               # scalar batch_id, per-batch oversell
│   ├── corrections.py             # scalar batch_id, count-mode diffs vs Batch.quantity, over-removal warn
│   ├── returns.py                 # origin batch inheritance + legacy fallback
│   └── operations.py              # history_view outer-joins Batch
├── routes/
│   ├── receipts.py                # + /receipts/batches chooser endpoint
│   ├── sales.py                   # + /sales/batch-pick endpoint; _build_lines grows batch_id
│   ├── writeoffs.py, corrections.py  # lookup responses gain oob batch picker
│   └── history.py                 # passes batch info to rows
├── templates/partials/
│   ├── batch_picker.html          # NEW: shared batch-list table (radio rows + hidden input)
│   ├── receipt_batch_chooser.html # NEW: top-up-vs-new chooser + new-batch fields
│   ├── sale_row.html              # + always-rendered <tr id="batch-wrap-{row}"> wrapper
│   └── history_rows.html          # + legacy label / batch annotation
alembic/versions/
└── 0008_batches.py                # NEW: batches table, operations.batch_id, legacy seed
tests/
├── conftest.py                    # + warehouse/batch fixtures; stocked_product gains a batch
└── test_batches.py                # NEW
```

### Pattern 1: Dual cached projection in the single write path (D-11/D-12)

**What:** `record_operation()` grows `batch_id: str | None = None`; for stock-affecting types it is mandatory and both caches update with SQL-side increments in the same transaction.
**When to use:** Every stock write — there is no other writer.

```python
# Source: extension of app/services/ledger.py (existing IN-02 pattern)
STOCK_AFFECTING_TYPES = frozenset({"receipt", "sale", "writeoff", "return", "correction"})

def record_operation(session, *, type_, product_id, qty_delta, ...,
                     batch_id: str | None = None, commit: bool = True) -> Operation:
    ...existing product guards...
    batch = None
    if type_ in STOCK_AFFECTING_TYPES:
        if batch_id is None:
            raise ValueError(f"batch_id is required for {type_!r} operations")  # D-12
        batch = session.get(Batch, batch_id)
        if batch is None:
            raise ValueError(f"unknown batch: {batch_id!r}")
        if batch.product_id != product_id:          # security: untrusted client id
            raise ValueError("batch does not belong to product")
    elif batch_id is not None:
        raise ValueError(f"{type_!r} operations are batch-less")  # audit types stay NULL

    op = Operation(..., batch_id=batch_id, ...)
    session.add(op)
    product.quantity = Product.quantity + qty_delta          # existing (UNCHANGED)
    if batch is not None:
        batch.quantity = Batch.quantity + qty_delta          # NEW, same transaction
    if commit:
        session.commit()
    return op
```

**Note on `Product.quantity`:** semantics unchanged — it remains SUM over ALL of that product's operations, batch-tagged or not (ARCHITECTURE.md Anti-Pattern 2). The existing line is not touched.

### Pattern 2: Structural `batch_id[]` alignment — hidden input in an always-rendered wrapper row

**What:** `sale_row.html` renders TWO `<tr>`s per basket line: the existing input row plus a picker wrapper row `<tr id="batch-wrap-{row}">` whose single `<td colspan="5">` ALWAYS contains `<input type="hidden" name="batch_id[]">` (empty until a batch is picked). The picker table renders inside this same wrapper.
**Why:** the basket posts parallel positional arrays (`code[]`/`qty[]`/`price[]` zipped in `non_blank_lines()`); if `batch_id[]` inputs were only created after a lookup, a line whose lookup never fired would shift every later line's batch attribution (milestone PITFALLS.md Pitfall 7). Rendering the hidden input unconditionally per row makes the arrays structurally equal-length in document order — alignment cannot drift.
**Delete-row handling:** the existing button does `this.closest('tr').remove()` — it must also remove the wrapper row: `hx-on:click="this.closest('tr').remove(); var w=document.getElementById('batch-wrap-{{ row_id or 'first' }}'); if (w) w.remove()"`. Both inputs of that line vanish together, so alignment survives add/delete in any order.
**`non_blank_lines()` extension:** grow the shared helper (and the route's `_build_lines`) with a fourth strictly-aligned array. A line's blankness test stays keyed on code/qty/price (a stray batch_id on an otherwise-blank row should not resurrect it) — but zip all four with `strict=False` replaced by explicit length normalization: pad `batch_id[]` with `""` to `len(codes)` before zipping, so a malformed post degrades to "no batch picked" (which `record_operation` then rejects loudly) instead of misattributing.

### Pattern 3: Server-driven batch selection (radio → re-rendered picker + oob price)

**What:** each radio row in `batch_picker.html` carries:

```html
<input type="radio" name="batch_pick_{{ row_id or 'first' }}" value="{{ batch.id }}"
       {% if batch.id == selected_batch_id %}checked{% endif %}
       hx-get="/sales/batch-pick"
       hx-vals='{"row": "{{ row_id }}", "batch_id": "{{ batch.id }}", "code": "{{ code }}"}'
       hx-target="#batch-wrap-{{ row_id or 'first' }}"
       hx-swap="outerHTML">
```

`/sales/batch-pick` re-queries the batch (fresh remaining quantity — also defuses stale-list drift), re-renders the whole wrapper row with: the selected radio checked, the row visually highlighted, the hidden `batch_id[]` input set to the selection — plus an **oob** `#price-wrap-{row}` (or `#price-{row}`) td carrying the batch price with the hint "Цена подставлена из партии — можно изменить". The existing form-level `hx-on::oob-before-swap` guard (id startsWith 'price' + non-empty value → shouldSwap=false) already protects operator-typed prices with zero new guard code (D-05).
**Why server-driven, not pure client JS:** re-rendering the wrapper server-side means the hidden input, the radio state, and the highlight can never disagree, the remaining-quantity column refreshes on every pick, and the 422 re-echo path (below) reuses the exact same partial. One extra round trip is irrelevant on localhost.
**Price-fill ordering rule:** `/sales/lookup` must SKIP its card `sale_cents` price fill when the product has ≥1 open batch (otherwise the card fill occupies the input and the value-based oob guard would then block the batch price — contradiction with D-05's "replacing the card pre-fill"). Fallback per D-14: when the picked batch's `price_cents` is NULL (legacy batch), `/sales/batch-pick` fills the card `sale_cents` instead (with the existing card hint text).
**D-06 auto-select:** when `/sales/lookup` finds exactly one open batch, it renders the picker with that radio pre-checked, hidden input pre-set, row highlighted, and the muted note "Партия выбрана автоматически — единственная" — and fills the price by the same rules (batch price, card fallback). Still changeable: it is just a pre-checked radio.

### Pattern 4: 422 / warn re-echo of picked batches (D-04)

**What:** `_build_lines()` gains `batch_ids: list[str]`; for each echoed line with a non-empty batch_id the route does `session.get(Batch, batch_id)` and passes the batch into the line dict. `sale_row.html`'s wrapper row then renders the hidden input with the echoed value plus a compact selected-batch summary (price/expiry/remaining/comment, highlighted) via the same `batch_picker.html` partial in "selected-only" mode — or the full picker if you re-query open batches per line (either satisfies D-04; the selected-summary render is cheaper and the operator can always re-open the full list by re-triggering the code lookup). An echoed batch_id that no longer resolves (deleted DB row, tampering) renders as "no batch picked" with the empty hidden input — the service guard is the backstop.
**Warn path too:** the oversell/below-minimum warn response re-renders the form partial through the same `_build_lines`, so batch echo works identically; the confirm=1 button re-POSTs the intact form (hidden inputs included) via `form="sale-form"` — no extra wiring.

### Pattern 5: Receipt batch chooser (resolve-or-create, D-01/D-02)

**What:** the receipt form gains a required warehouse `<select name="warehouse_id">` (active warehouses only — note `list_warehouses()` deliberately includes deleted rows; add an `active_warehouses()` helper or filter in the route) preselected to `DEFAULT_WAREHOUSE_ID` when that row is still active, else the first active one. A `#batch-chooser` div below it is populated by `/receipts/batches?code=...&warehouse_id=...`:
- triggered by `hx-trigger="change"` on the warehouse select (hx-include the code input), AND
- refreshed by the existing `/receipts/lookup` response as an additional oob swap (extend that request's `hx-include` to carry the warehouse select).

Chooser content: radio "◉ Пополнить партию: {expiry} · {price} · {remaining} · {comment}" per open batch in that warehouse (D-07 ordering) + radio "◉ Новая партия" which un-hides the three new-batch fields (expiry `<input type="date">`, location, comment) — same client-side radio show/hide + disabled toggling idiom as the correction form's count/delta blocks (a disabled input never submits). POST carries `batch_choice` = an existing batch id or `"new"`. `register_receipt()` resolves in the same transaction: existing id → validate it belongs to (product, warehouse) and top up (frozen `price_cents` NOT rewritten); `"new"` → create `Batch(product_id, warehouse_id, expiry, location, comment, price_cents=sale_cents, quantity=0)` then `record_operation(type_="receipt", batch_id=batch.id, ...)`.
**Unknown/new product code:** no open batches exist → chooser renders only the new-batch path (auto-selected).
**Zero active warehouses:** render the blocking RU hint linking to /warehouses instead of the chooser (D-02); the POST must also re-check server-side (a stale form could still submit).

### Pattern 6: Return batch inheritance (D-08)

`register_return()` inherits `origin.batch_id`. When the origin is a pre-Phase-9 op (`batch_id is None`), resolve the product's legacy batch (`is_legacy == 1 and product_id == origin.product_id`). The return form shows the target batch read-only (or the legacy label). See Open Question 1 for the no-legacy-batch edge case.

### Pattern 7: rebuild_stock per-batch pass with NULL-bucket attribution (D-11, discretion resolved)

Add an `is_legacy` marker column (Integer 0/1, default 0; set to 1 only by migration 0008's seed) so the legacy batch of a product is identifiable without fragile string matching. Then every batch quantity stays re-derivable from the ledger alone:

```python
# Batch quantity from ledger alone (FND-01 extended):
#   normal batch:  SUM(qty_delta WHERE batch_id = b.id)
#   legacy batch:  SUM(qty_delta WHERE batch_id = b.id)                 -- post-migration ops on it
#                + SUM(qty_delta WHERE product_id = b.product_id
#                                 AND batch_id IS NULL)                 -- the frozen legacy bucket
```

Invariant check per product: `Product.quantity == SUM(batches.quantity) + null_bucket_sum_if_uncaptured`, where `null_bucket_sum_if_uncaptured` is `SUM(qty_delta WHERE product_id = p AND batch_id IS NULL)` **only when the product has no legacy batch** (D-13 seeds legacy batches only for ledger stock > 0; the dev DB verifiably contains at least one product with non-positive ledger stock — its NULL ops are captured by no batch, and the invariant must account for that rather than fail). Log/raise on mismatch per existing repair philosophy.

### Anti-Patterns to Avoid

- **Batch-mode Alembic migration on `operations`:** silently DROPs `operations_no_update`/`operations_no_delete` (frozen warning in 0001). Native `op.add_column` only, no inline FK (0004 precedent — Alembic SQLite dialect raises `NotImplementedError` on inline FK constraints).
- **Backfilling `operations.batch_id` with UPDATE:** the no-update trigger ABORTs it, and mutating the ledger breaks the sync-replay contract. NULL = legacy, display-side (D-15).
- **Storing batch_id in `Operation.payload` JSON:** unindexable, un-GROUP-BY-able; contradicts the `sale_id` column precedent (D-10, PITFALLS.md Pitfall 4).
- **Trusting client `batch_id` without ownership re-validation:** always verify `batch.product_id == product_id` (and, for receipt top-ups, `batch.warehouse_id == warehouse_id`) server-side before writing.
- **Repurposing `Product.quantity`:** it stays the batch-agnostic total; catalog, low-stock, reports, and export all read it unchanged.
- **Keeping correction count-mode diffed against `product.quantity`:** once batches exist, "counted" means "counted THIS batch" — diff against `Batch.quantity` of the picked batch, or the first post-migration recount corrupts every other batch (PITFALLS.md Pitfall 3).
- **Filling the card price AND the batch price into the same input:** decide the fill source server-side per line (open batches → batch price on pick; legacy NULL price → card fallback), never stack fills.
- **`hx-on::change` (double colon) for DOM change events:** `hx-on::x` is shorthand for the `htmx:x` event namespace; plain DOM events need single-colon `hx-on:change`. Note: `correction_form.html` currently uses `hx-on::change` on the mode radios — when touching that form this phase, verify the toggle actually fires and normalize to `hx-on:change` [ASSUMED — needs a 2-minute browser check; htmx 2.x docs distinguish the two forms].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Locale-safe date entry | Custom dd.mm.yyyy text parsing | `<input type="date">` + `datetime.date.fromisoformat()` | Browser posts ISO `yyyy-mm-dd` regardless of RU locale display [CITED: developer.mozilla.org/en-US/docs/Web/HTML/Element/input/date]; stdlib validates it in one call |
| NULL-last expiry ordering | Python-side sort of fetched rows / CASE hacks | `sqlalchemy.nullslast(Batch.expiry.asc())` | Renders `NULLS LAST` — verified working on venv SQLite 3.50.4, native on PostgreSQL |
| Schema change on `operations` | Hand-written ALTER TABLE SQL | Alembic native `op.add_column` (0004 precedent) | Preserves triggers; keeps the migration chain replayable |
| Soft-block confirmation | A new modal/JS confirm mechanism | Existing `confirm=1` zero-write re-POST pattern (sale/writeoff oversell partials) | One mechanism repo-wide; already tested; D-09 locks it |
| Batch quantity bookkeeping | Ad-hoc UPDATE statements in services | `record_operation()` dual projection | Single write path is the architecture's core invariant |

**Key insight:** every interaction this phase needs (debounced lookup, server-decides-fill-vs-204, oob fill with typed-value guard, warn-but-allow, parallel form arrays, radio show/hide with disabled toggling) already has a working, tested in-repo precedent. The plan should copy those precedents mechanically rather than invent variants.

## Runtime State Inventory

This is a schema + data-migration phase; the inventory below covers what exists outside the source tree.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/myorishop.db` — **live dev DB at Alembic head 0007 containing 16 operations, 6 products (5 with ledger stock > 0, at least one with non-positive stock — total cached quantity sum is negative)** [VERIFIED: queried directly] | Migration 0008 will create 5 legacy batches on this DB. Test the migration against a copy of this real file, not just a fresh DB. The negative-stock product exercises the D-13 "no legacy batch for ≤0 stock" branch and the rebuild invariant's NULL-bucket case — real data, free test case. |
| Stored data (backups) | `backups/` dir populated by the startup VACUUM backup (conftest disables it in tests) | None — backups are point-in-time copies; migration doesn't touch them |
| Live service config | None — app is fully local, no external services | None |
| OS-registered state | None found (run.bat launcher only; no scheduled tasks/services) | None |
| Secrets/env vars | `.env` consumed by pydantic-settings (db path, operator name, device_id) — no key references any renamed entity | None |
| Build artifacts | uv-managed `.venv` — no batch-related artifacts | None |

## Common Pitfalls

### Pitfall 1: The D-12 guard breaks the existing test suite and every service call site at once
**What goes wrong:** making `batch_id` mandatory in `record_operation()` for stock-affecting types instantly breaks `tests/conftest.py::stocked_product`, every test in test_ledger/test_sales/test_writeoffs/test_corrections/test_returns/test_receipts that stages stock, and all five operation services — before any new feature works.
**Why it happens:** the guard is a one-line change with a 262-test blast radius.
**How to avoid:** sequence the plan so the same wave that adds the guard also (a) updates conftest with `warehouse`/`batch` fixtures (`Base.metadata.create_all` already covers new tables), (b) updates every service to pass batch_id, (c) updates the affected tests. Do not split "guard" and "callers" across waves.
**Warning signs:** a plan wave ends with the suite red "to be fixed later".

### Pitfall 2: `batch_id[]` array drift on row delete or lookup-less lines
**What goes wrong:** `batch_id[2]` describes a different logical line than `code[2]` → sale silently attributed to the wrong batch.
**How to avoid:** Pattern 2 (hidden input always rendered per row, delete removes both `<tr>`s, `batch_id[]` padded to `len(codes)` before zipping). **Write the drift test before the picker ships:** add 3 rows, delete the middle one, pick different batches on the remaining two, submit, assert each written op's batch matches its line's product.
**Warning signs:** hidden input rendered only inside the lookup response; `zip(..., strict=False)` silently truncating a short batch array.

### Pitfall 3: 422/warn re-render drops the picked batches
**What goes wrong:** operator picks batches on 3 lines, one qty is invalid, the 422 re-render loses all picks — operator re-picks everything or, worse, submits with empty batch ids.
**How to avoid:** Pattern 4 — `_build_lines` carries batch_id, wrapper row re-renders hidden input + selected summary. Test: POST with picked batch + invalid qty → response HTML contains the batch_id hidden value.

### Pitfall 4: Card price fill fights the batch price fill
**What goes wrong:** lookup fills card `sale_cents` into the empty price input; the later batch pick's oob fill is then blocked by the value-based `oob-before-swap` guard — D-05's "batch price replaces card pre-fill" never happens.
**How to avoid:** `/sales/lookup` skips the price fill when the product has ≥1 open batch (batch pick becomes the sole fill source); `/sales/batch-pick` falls back to card `sale_cents` when the batch price is NULL (legacy, D-14).
**Warning signs:** manual test — type code of a batched product, pick a batch with a different price than the card: input must show the batch price.

### Pitfall 5: Migration seeds legacy quantity from the cache instead of the ledger
**What goes wrong:** `products.quantity` may be stale; criterion 5 ("totals still balance") then fails against a rebuilt ledger.
**How to avoid:** D-13 locked — the seed reads `SELECT product_id, SUM(qty_delta) FROM operations GROUP BY product_id HAVING SUM(qty_delta) > 0` in plain SQL via `op.get_bind()`. Never touch `products.quantity` in the migration.

### Pitfall 6: Trigger loss via any table-rebuild operation on `operations`
**What goes wrong:** any `batch_alter_table("operations")` (even to add an FK or NOT NULL) rebuilds the table and silently drops the append-only triggers.
**How to avoid:** native `op.add_column` with a bare String(36) column (no inline FK — Alembic SQLite raises `NotImplementedError` anyway, per 0004's verified note), `op.create_index` after. Verification step for the plan: after `alembic upgrade head`, assert `SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'operations_no_%'` returns 2, and an `UPDATE operations ...` still ABORTs.

### Pitfall 7: Correction count-mode still baselines on the product total
**What goes wrong:** counting one batch while the diff runs against `product.quantity` writes a delta that corrupts every other batch's implied stock.
**How to avoid:** correction becomes batch-scoped: the current-qty hint shows the picked batch's quantity (update the hint when a batch is picked — the batch-pick response can oob-refresh `#current-qty-hint`), and `qty_delta = counted - batch.quantity`. Delta mode: over-removal (`-qty_delta > batch.quantity`) goes through the confirm=1 warn (criterion 4 covers corrections).

### Pitfall 8: Stale picker quantities between lookup and submit
**What goes wrong:** remaining quantity shown at lookup time changes before submit (another form, earlier basket line of the same batch).
**How to avoid:** the display may be stale by design (single operator, low risk); the authoritative guard is the POST-time per-batch aggregation check against current `Batch.quantity` (D-09), which must aggregate the SAME batch across multiple basket lines before comparing (re-key the existing `requested_by_product` dict to batch_id — PITFALLS.md Pitfall 2). `/sales/batch-pick` re-rendering fresh data on every selection further narrows the window.

### Pitfall 9: NULL-expiry ordering diverges between SQLite and future PostgreSQL
**What goes wrong:** bare `ORDER BY expiry ASC` puts NULLs FIRST on SQLite but LAST on PostgreSQL — silent behavior flip after the planned DB move.
**How to avoid:** always order with explicit `nullslast(Batch.expiry.asc())` (verified working here; supported since SQLite 3.30.0, PostgreSQL native). Tie-break `Batch.created_at.asc()` (oldest receipt, D-07).

### Pitfall 10: Receipt top-up validated only client-side
**What goes wrong:** a stale/crafted POST tops up a batch belonging to a different product or warehouse.
**How to avoid:** `register_receipt` re-validates `batch.product_id == product.id and batch.warehouse_id == warehouse_id` before writing (the ledger guard checks product ownership; the warehouse check is receipt-specific).

## Code Examples

Verified patterns from the repo and official sources.

### Migration 0008 skeleton (native add_column + plain-SQL legacy seed)

```python
# Source: repo precedents 0004 (native add_column) + 0007 (frozen seed); values FROZEN, no app imports
import uuid
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0008", "0007"

DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"   # re-declared, 0007 D-03 contract
LEGACY_COMMENT = "Остаток до внедрения партий"                    # D-14 frozen literal
_SEED_CREATED_AT = "2026-07-11T00:00:00+00:00"
_LEGACY_NS = uuid.UUID("00000000-0000-4000-8000-00000000000b")   # frozen namespace for uuid5

def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("warehouse_id", sa.String(36), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=True),        # ISO yyyy-mm-dd
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),     # WH-02
        sa.Column("comment", sa.String(200), nullable=True),      # LOT-04
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("is_legacy", sa.Integer(), nullable=False),     # 1 only for migration-seeded rows
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"],
                                name=op.f("fk_batches_product_id_products")),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"],
                                name=op.f("fk_batches_warehouse_id_warehouses")),
    )
    op.create_index(op.f("ix_batches_product_id"), "batches", ["product_id"])

    # NATIVE add-column, BARE (no inline FK) — 0004 sale_id precedent; triggers untouched.
    op.add_column("operations", sa.Column("batch_id", sa.String(36), nullable=True))
    op.create_index(op.f("ix_operations_batch_id"), "operations", ["batch_id"])

    # D-13: legacy batch per product with LEDGER stock > 0 (plain SQL, never the cache).
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT product_id, SUM(qty_delta) AS qty FROM operations "
        "GROUP BY product_id HAVING SUM(qty_delta) > 0"
    )).fetchall()
    for product_id, qty in rows:
        conn.execute(
            sa.text(
                "INSERT INTO batches (id, product_id, warehouse_id, expiry, price_cents, "
                "location, comment, quantity, is_legacy, created_at, updated_at) "
                "VALUES (:id, :pid, :wid, NULL, NULL, NULL, :comment, :qty, 1, :ts, :ts)"
            ),
            {"id": str(uuid.uuid5(_LEGACY_NS, product_id)), "pid": product_id,
             "wid": DEFAULT_WAREHOUSE_ID, "comment": LEGACY_COMMENT,
             "qty": qty, "ts": _SEED_CREATED_AT},
        )

def downgrade() -> None:
    op.drop_index(op.f("ix_operations_batch_id"), table_name="operations")
    op.drop_column("operations", "batch_id")     # native DROP COLUMN — index dropped first (0004 mirror)
    op.drop_index(op.f("ix_batches_product_id"), table_name="batches")
    op.drop_table("batches")
```

### Batch model (models.py — column names are discretion, resolved here)

```python
# Source: repo conventions (UUID String(36) PK, ISO text timestamps, integer cents)
class Batch(Base):
    """Stock-holding unit (LOT-01): one product x one warehouse x one lot.

    D-03: NO deleted_at and NO standalone CRUD — a batch leaves pickers when
    quantity hits 0. is_legacy=1 marks the migration-seeded per-product
    legacy batch (D-13/D-14) so returns fallback (D-08) and the
    rebuild_stock NULL-bucket pass can find it without string matching.
    """
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    expiry: Mapped[str | None] = mapped_column(String(10))      # ISO yyyy-mm-dd (LOT-03)
    price_cents: Mapped[int | None] = mapped_column(Integer)    # sale-price snapshot at creation
    location: Mapped[str | None] = mapped_column(String(100))   # WH-02 free-text tag
    comment: Mapped[str | None] = mapped_column(String(200))    # LOT-04
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # cached projection
    is_legacy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)

# Operation gains (0004 sale_id mirror — ORM FK for insert ordering + PG portability):
#   batch_id: Mapped[str | None] = mapped_column(
#       ForeignKey("batches.id", name="fk_operations_batch_id_batches"), index=True)
```

### Open-batch query with D-07 ordering (new app/services/batches.py)

```python
# Source: sqlalchemy nullslast — NULLS LAST verified on venv SQLite 3.50.4 (supported since 3.30.0)
from sqlalchemy import nullslast, select

def open_batches(session, product_id: str, warehouse_id: str | None = None) -> list[Batch]:
    """Open batches (quantity > 0) — earliest expiry first, NULL expiry last,
    tie-broken by oldest receipt (D-07). Sale picker: all warehouses.
    Receipt chooser: pass warehouse_id (D-01)."""
    stmt = select(Batch).where(Batch.product_id == product_id, Batch.quantity > 0)
    if warehouse_id is not None:
        stmt = stmt.where(Batch.warehouse_id == warehouse_id)
    return list(session.scalars(
        stmt.order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
    ))

def legacy_batch(session, product_id: str) -> Batch | None:
    """The migration-seeded legacy batch for D-08 pre-batch return fallback."""
    return session.scalars(
        select(Batch).where(Batch.product_id == product_id, Batch.is_legacy == 1)
    ).first()
```

### Per-batch oversell re-key in register_sale (D-09)

```python
# Source: re-key of the existing requested_by_product block (app/services/sales.py:137-153)
requested_by_batch: dict[str, int] = {}
batches_by_id: dict[str, Batch] = {}
for line in resolved:
    batch = line["batch"]           # resolved+validated earlier alongside product
    requested_by_batch[batch.id] = requested_by_batch.get(batch.id, 0) + line["qty"]
    batches_by_id[batch.id] = batch

oversold = [
    {"product": ..., "batch": batches_by_id[bid],
     "available": batches_by_id[bid].quantity, "requested": requested}
    for bid, requested in requested_by_batch.items()
    if requested > batches_by_id[bid].quantity
]
# below_minimum block unchanged; both computed before any return (existing Pitfall-2 discipline)
```

### rebuild_stock per-batch pass + invariant (D-11 + NULL-bucket discretion)

```python
# Source: extension of app/services/ledger.py rebuild_stock / compute_stock patterns
def compute_batch_stock(session, batch: Batch) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0))
        .where(Operation.batch_id == batch.id))
    if batch.is_legacy:
        total += session.scalar(
            select(func.coalesce(func.sum(Operation.qty_delta), 0))
            .where(Operation.product_id == batch.product_id, Operation.batch_id.is_(None)))
    return total

def rebuild_stock(session) -> None:
    for product in session.scalars(select(Product)).all():
        product.quantity = compute_stock(session, product.id)          # existing pass
    batch_total_by_product: dict[str, int] = {}
    legacy_products: set[str] = set()
    for batch in session.scalars(select(Batch)).all():                 # NEW pass
        batch.quantity = compute_batch_stock(session, batch)
        batch_total_by_product[batch.product_id] = (
            batch_total_by_product.get(batch.product_id, 0) + batch.quantity)
        if batch.is_legacy:
            legacy_products.add(batch.product_id)
    # Invariant (D-11): product rollup == sum of its batches, PLUS the uncaptured
    # NULL bucket for products the migration seeded no legacy batch for (ledger sum <= 0).
    for product in session.scalars(select(Product)).all():
        expected = batch_total_by_product.get(product.id, 0)
        if product.id not in legacy_products:
            expected += session.scalar(
                select(func.coalesce(func.sum(Operation.qty_delta), 0))
                .where(Operation.product_id == product.id, Operation.batch_id.is_(None)))
        if product.quantity != expected:
            raise ValueError(f"stock invariant violated for product {product.id!r}")
    session.commit()
```

### Expiry validation (receipt service)

```python
# Source: MDN — input type=date value is always yyyy-mm-dd; server still validates untrusted input
from datetime import date

def parse_optional_expiry(raw: str, errors: dict, key: str = "expiry") -> str | None:
    s = raw.strip()
    if not s:
        return None                                  # optional (LOT-03)
    try:
        return date.fromisoformat(s).isoformat()     # normalize + validate
    except ValueError:
        errors[key] = "Укажите срок годности в формате ГГГГ-ММ-ДД."
        return None
```

### sale_row.html wrapper row (Pattern 2 structural alignment)

```html
{# After the existing main <tr>, ALWAYS rendered so batch_id[] stays index-aligned with code[] #}
<tr id="batch-wrap-{{ row_id or 'first' }}">
  <td colspan="5">
    <input type="hidden" name="batch_id[]" value="{{ batch_id or '' }}">
    {% if selected_batch %}{# 422/warn re-echo: compact highlighted summary, still changeable #}
      {% include "partials/batch_picker.html" %}{# selected-only mode #}
    {% endif %}
  </td>
</tr>
{# /sales/lookup response adds: <tr id="batch-wrap-{row}" hx-swap-oob="outerHTML">…picker…</tr> #}
```

## State of the Art

| Old Approach (v1.0 in-repo) | Current Approach (this phase) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| One `Product.quantity` per product | Two-tier cache: product rollup (unchanged semantics) + per-batch detail | Phase 9 | Oversell/pickers read Batch.quantity; reports/catalog/export untouched |
| Oversell keyed by product_id | Keyed by batch_id, same warn-but-allow shell | Phase 9 | Criterion 4 |
| Card `sale_cents` price pre-fill | Batch price on pick (card fallback for NULL-price legacy batches) | Phase 9 | D-05/D-14 |
| Correction counted vs product total | Counted vs picked batch's quantity | Phase 9 | Prevents cross-batch corruption |

**Deprecated/outdated:** milestone PITFALLS.md Pitfall 7's suggestion to *backfill* existing operation rows to a legacy batch is superseded by locked D-10/D-15 (NULL = legacy, no ledger mutation; legacy batches are seeded as `batches` rows only). Likewise PITFALLS.md Pitfall 5's "freeze cost from the batch" does not apply as written: the locked D-02 gives `Batch` a *sale-price* snapshot only (no cost field) — `unit_cost_cents` continues to freeze from `Product.cost_cents` exactly as today, so profit reporting is unchanged. Plans must follow CONTEXT.md where the two documents disagree.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `hx-on::change` (double colon) on `correction_form.html` mode radios listens for a nonexistent `htmx:change` event and the working DOM-event form is `hx-on:change` | Anti-Patterns | Low — if the existing toggle works, use whatever it uses; verify in-browser during the corrections wave (2-minute check) |
| A2 | The operator's production data is the dev DB `data/myorishop.db` (16 ops) or a similarly small file; no other live DB copies exist that migration 0008 must be rehearsed against | Runtime State Inventory | Migration is data-shape-driven (SUM per product), so size doesn't matter; but rehearse on a copy of whatever the real file is before upgrading it |
| A3 | Pre-Phase-9 sale ops needing a return can reference a product that received NO legacy batch (ledger stock ≤ 0 at migration) — handled by lazy-create (Open Question 1) | Pattern 6 | If unhandled, such a return 500s or is rejected; the recommended lazy-create needs planner sign-off since it adds a third batch birth path beside D-03's two |

## Open Questions (RESOLVED)

1. **Return of a pre-batch sale line for a product WITHOUT a legacy batch (D-08 × D-13 tension)** — RESOLVED (Plan 09-05: lazy-create the legacy batch inside `register_return`, third birth path)
   - What we know: D-13 seeds legacy batches only for ledger stock > 0. A product fully sold out (ledger sum 0) before migration still has returnable sale ops with `batch_id NULL`; D-08 says such returns target "the product's legacy batch" — which doesn't exist. The dev DB verifiably contains a non-positive-stock product, so this is not hypothetical.
   - What's unclear: whether to lazily create the legacy batch (same frozen field values, `is_legacy=1`, quantity 0) inside `register_return`'s transaction, or reject the return with an RU error.
   - Recommendation: **lazy-create in `register_return`** — it is the only way D-08 works for all legacy sales, it reuses the exact D-14 field contract, and the batch is created with quantity 0 then incremented via `record_operation` (single-write-path preserved). Document it in the plan as an explicit, deliberate third birth path (migration + receipts + legacy-return fallback).

2. **Default-warehouse preselect when the seeded default is soft-deleted** — RESOLVED (Plan 09-02: preselect `DEFAULT_WAREHOUSE_ID` if active else first active alphabetically; zero active → blocking hint)
   - What we know: Phase 8 allows soft-deleting any warehouse (warn-but-allow on the last one). D-02 says preselect the seeded default.
   - Recommendation: preselect `DEFAULT_WAREHOUSE_ID` if active, else the first active warehouse alphabetically; zero active → blocking hint (already locked). Trivial; note it in the receipt plan so it isn't decided ad hoc in code review.

3. **Where /history shows batch info (D-15 display shape)** — RESOLVED (Plan 09-05 Task 2: `history_view` LEFT OUTER JOIN to Batch, muted second line inside the existing «Товар» cell, no ninth column)
   - What we know: history_rows.html has 8 columns; `history_view` joins Product only. NULL batch_id must render a legacy label or dash.
   - Recommendation: `history_view` gains a LEFT OUTER JOIN to Batch (`select(Operation, Product, Batch).outerjoin(Batch, Operation.batch_id == Batch.id)`); render batch info as a muted second line inside the existing "Товар" cell (comment/expiry, or "До партий" for NULL on stock-affecting types, dash for audit types) rather than a ninth column — avoids widening the table ahead of the Phase 11 mobile pass. Planner's call on exact wording.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | run/test workflow | ✓ | 0.11.11 | pip+venv (per CLAUDE.md) |
| Python (project venv) | runtime | ✓ | 3.13.13 | — |
| SQLite (venv bundled) | DB, NULLS LAST | ✓ | 3.50.4 (≥3.30 needed for NULLS LAST) | `expiry.is_(None)` boolean ordering |
| Alembic migration chain | migration 0008 | ✓ | head = 0007 on `data/myorishop.db` | — |
| pytest suite | validation | ✓ | 262 tests collected | — |
| htmx | picker UI | ✓ | 2.0.10 vendored (`app/static/htmx.min.js`) | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none needed — all present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (with httpx 0.28.* TestClient) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| Quick run command | `uv run pytest tests/test_batches.py tests/test_ledger.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOT-01 | Multiple batches per product code, each with own warehouse/expiry/price/comment; dual quantity projection | unit | `uv run pytest tests/test_batches.py -x -q` | ❌ Wave 0 |
| LOT-02 | Sale lookup renders picker (price/expiry/qty/comment); batch required per line; single-batch auto-select; D-07 ordering | integration (TestClient) | `uv run pytest tests/test_sales.py -x -q` | ✅ extend |
| LOT-03 | Optional expiry: empty→NULL, ISO validated, NULLS LAST ordering | unit | `uv run pytest tests/test_batches.py -k expiry -x -q` | ❌ Wave 0 |
| LOT-04 | Comment stored and rendered in picker HTML | integration | `uv run pytest tests/test_sales.py -k picker -x -q` | ✅ extend |
| LOT-05 | Write-off/correction require batch; correction counted-mode diffs vs batch qty; return inherits origin batch (+ legacy fallback) | unit + integration | `uv run pytest tests/test_writeoffs.py tests/test_corrections.py tests/test_returns.py -x -q` | ✅ extend |
| WH-02 | Location tag saved on new-batch receipt, echoed in chooser/picker | integration | `uv run pytest tests/test_receipts.py -k location -x -q` | ✅ extend |
| Criterion 4 | Per-batch oversell warn (same batch on two lines aggregated; other batch's stock irrelevant) | unit | `uv run pytest tests/test_sales.py -k oversell -x -q` | ✅ extend |
| Criterion 5 | Migration 0008 on a seeded DB: legacy batch per stock>0 product, quantity == ledger SUM, triggers intact, rebuild invariant holds | integration (migration test) | `uv run pytest tests/test_batches.py -k migration -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_batches.py tests/test_ledger.py -x -q` (plus the suite file being touched)
- **Per wave merge:** `uv run pytest -q` (full 262+ suite — mandatory because D-12 has repo-wide blast radius)
- **Phase gate:** full suite green + `ruff check .` before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_batches.py` — Batch model, open_batches ordering (NULL expiry last), compute_batch_stock/rebuild invariant incl. NULL bucket, migration seed test (run 0008 against a temp DB seeded with pre-batch operations incl. a ≤0-stock product; assert legacy batches, quantities, and both triggers survive)
- [ ] `tests/conftest.py` — `warehouse` fixture (plus seeded default-id option), `batch` fixture; `stocked_product` updated to create its batch and pass `batch_id` to `record_operation`
- [ ] Signature-change sweep: every existing test calling `record_operation`/`register_sale`/`register_writeoff`/`register_correction`/`register_return` or POSTing those forms needs batch wiring — budget this explicitly (test_ledger, test_sales, test_writeoffs, test_corrections, test_returns, test_receipts, test_smoke, test_history at minimum)
- [ ] Array-drift test (Pitfall 2): basket add/delete rows out of order → batch attribution matches per line

## Security Domain

`security_enforcement: true`, ASVS level 1. Single-operator local app — the bar is data integrity, not confidentiality.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Out of scope v1 (locked project constraint — single local user) |
| V3 Session Management | no | No sessions exist |
| V4 Access Control | partial | Object-level validation: submitted `batch_id` must belong to the submitted product (and warehouse, for receipt top-ups) — server-side, in the service layer |
| V5 Input Validation | yes | Existing conventions: allow-lists (mode/reason), isascii+isdigit qty guards, `parse_optional_cents`; NEW: `date.fromisoformat` for expiry, batch ownership re-validation, `batch_choice` allow-list ("new" or a resolvable batch id) |
| V6 Cryptography | no | None introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered/stale `batch_id` (wrong product's batch, exhausted batch, forged id) | Tampering | `record_operation` guard: `session.get(Batch)` + `batch.product_id == product_id` ValueError (mirrors IN-01 and the returns origin re-validation precedent) |
| `confirm=1` replay without seeing the warning | Repudiation/Tampering | Existing pattern already re-runs all checks server-side on every POST; extend identically for per-batch scope — never trust the flag alone |
| Parallel-array injection (extra/missing batch_id[] entries) | Tampering | Pad/normalize `batch_id[]` length server-side before zip; missing batch → loud ValueError, never positional guess |
| XSS via batch comment/location in picker HTML | Tampering | Jinja autoescape only (repo rule: never `|safe` on stored text — comments/locations are untrusted-at-rest like product names) |
| Untrusted `row` id echoed into hx attributes | Injection | Reuse the existing `_ROW_ID_RE` format-validation precedent (routes/sales.py CR-01) for any new endpoint accepting `row` |

## Sources

### Primary (HIGH confidence)
- Direct code reading this session: `app/models.py`, `app/services/{ledger,sales,receipts,writeoffs,corrections,returns,warehouses,operations}.py`, `app/routes/{sales,receipts,returns,history}.py`, `app/templates/partials/{sale_row,sale_form,sale_lookup,sale_customer,receipt_form,writeoff_form,writeoff_oversell,correction_form,return_form,history_rows}.html`, `alembic/versions/{0001,0004,0007}*.py`, `tests/conftest.py`, `pyproject.toml`
- Live environment verification: venv Python 3.13.13 / SQLite 3.50.4; `ORDER BY ... NULLS LAST` executed successfully; Alembic head 0007; 262 tests collected; `data/myorishop.db` row counts queried
- `.planning/phases/09-batch-tracking-ledger-integration/09-CONTEXT.md` (locked decisions), `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` (reconciled — two superseded points noted in State of the Art)

### Secondary (MEDIUM confidence)
- MDN `<input type="date">` — value always `yyyy-mm-dd` regardless of locale (fetched this session) — https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/date
- SQLite NULLS FIRST/LAST added in 3.30.0 — web search corroborated by [sqlitetutorial.net ORDER BY](https://www.sqlitetutorial.net/sqlite-order-by/) and [sqlite.org SELECT docs](https://sqlite.org/lang_select.html), and independently confirmed by local execution (raising the effective confidence to HIGH for THIS environment)

### Tertiary (LOW confidence)
- htmx `hx-on:` single- vs double-colon semantics — training knowledge, flagged `[ASSUMED]` (A1) with an in-browser verification step

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; everything verified installed and pinned
- Architecture: HIGH — all structural decisions locked in CONTEXT.md; this research only resolves wiring, all grounded in read code
- Migration mechanics: HIGH — 0004/0007 precedents read verbatim; dev DB shape verified by query
- Pitfalls: HIGH for repo-specific items (grounded in code), MEDIUM for the htmx `hx-on::change` note (A1)

**Research date:** 2026-07-11
**Valid until:** 2026-08-10 (stable local stack; re-verify only if dependencies are re-pinned)
