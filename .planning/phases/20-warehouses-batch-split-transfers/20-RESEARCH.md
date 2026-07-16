# Phase 20: Warehouses & Batch-Split Transfers - Research

**Researched:** 2026-07-16
**Domain:** FastAPI/SQLAlchemy server-rendered CRUD (warehouse dedicated forms) + ledger-safe batch-split transfer logic
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Warehouse dedicated forms (WH-02)**
- **D-01: Picker list + single dedicated edit/delete page (Option B).** `/warehouses` becomes a plain picker table (name, address, item count, last receipt date — no inline `<input>` edit fields, no inline delete). Clicking a row's "Изменить" link navigates to `GET /warehouses/{id}/edit`, which hosts both the edit form and the delete action (with the existing warn-then-confirm / stock-blocked logic). `GET /warehouses/new` is the separate add form. This matches WH-02's own wording ("pick-a-warehouse-then-edit/delete flow") exactly, one destination for edit+delete, not two.
- **D-02: The existing warn-then-confirm and stock-blocked delete UI (WH-03 guard, already correct in `app/services/warehouses.py`) must be ported from its current in-list-row rendering to the edit page** — this is a real rework of the response shape (partial-swapped-in-list → page-level), not a copy-paste. `soft_delete_warehouse`'s guard logic itself is untouched; only where/how its warning renders changes.
- Rejected: Option A (full Products mirror, keeping an inline quick-delete link in the list in addition to edit-page delete) — two delete entry points is more than WH-02's text asks for. Rejected: Option C (add-only dedication, edit/delete stay inline) — does not close WH-02 for edit/delete.

**Item count & last receipt date (WH-01)**
- **D-03: "Item count" = distinct product count**, i.e. `COUNT(DISTINCT Batch.product_id)` per warehouse, filtered to `quantity > 0`. Chosen over total units (`SUM(quantity)`) and open-batch count. Open-batch count was explicitly rejected: XFER-01 ships in this same phase and batch-split transfers would inflate a batch-count metric with zero change in actual stock, undermining the number the phase itself introduces.
- **D-04: "Last goods receipt date" = a single grouped query for the whole page of warehouse ids**, not N+1 per row: `outerjoin(Operation, (Operation.batch_id == Batch.id) & (Operation.type == "receipt"))` joined to `Batch.warehouse_id`, `func.max(Operation.created_at)`, `group_by(Batch.warehouse_id)`. Model directly on `app/services/reports.py::stale_products`'s `outerjoin` + `func.max(...)` + `group_by` shape — this codebase's established anti-N+1 precedent for "last X date per parent row" (the `outerjoin`, not an inner join, so a warehouse with zero receipts still appears with `None`, not disappears).
- Both counts must be computed as page-wide grouped queries (IN(...) over the current page's warehouse ids), mirroring `app/services/batches.py::batches_for_products`'s "one query per page, not per-row" pattern — never per-row queries in a loop.

**Batch-split transfer semantics (XFER-01)**
- **D-05: One unified form covers both scenarios (Option 3).** Extend the existing `/transfers` form with optional destination-batch override fields (new expiry date, new condition/comment) AND relax `SAME_WAREHOUSE_ERROR` so submitting the same warehouse as source and destination becomes the in-place "split" operation (no separate route/service, no second UI for the operator to learn). The ledger layer (`record_operation`) has no warehouse-equality constraint to fight — this was verified, not assumed.
- **D-06: When destination warehouse == source warehouse, at least one override field (expiry or condition/comment) is REQUIRED — block with a validation error if both are blank.** This prevents a meaningless empty duplicate batch (same product, same warehouse, same expiry, same comment) from being created by mistake. Cross-warehouse transfers (destination ≠ source) keep today's behavior: override fields stay optional, blank means inherit from source, exactly as `register_transfer` already does.
- **D-07: `register_transfer`'s existing `dest = Batch(...)` construction is the extension point** — add two optional params (new expiry, new comment) that override `source.expiry`/`source.comment` when non-blank, falling back to the source's values when blank (mirrors the direct-assignment-never-bare-`or` convention already used for `price_cents` in that same constructor — a legitimate blank must not silently become "keep old value" via a falsy-string trap; treat "field present but blank" as "no override" explicitly, not via `or`).
- **D-08: Removing/relaxing `SAME_WAREHOUSE_ERROR` changes tested behavior** — `tests/test_transfers.py` currently asserts this guard fires for same-warehouse submissions; that test's premise needs to change to "same warehouse + no override fields → blocked (D-06's new error), same warehouse + at least one override → allowed."
- **D-09: `_dest_warehouses()` in `app/routes/transfers.py` currently filters the destination `<select>` to exclude the source batch's own warehouse** — this filtering must be removed/changed so the source warehouse becomes a selectable destination option again, otherwise D-05's same-warehouse path is unreachable from the UI.

**Code-review debt closure (not a formal requirement — pre-flagged in STATE.md)**
- **D-10: Fix WR-01 (batch-ownership leak) in BOTH `app/routes/transfers.py` AND `app/routes/writeoffs.py`.** Both files' POST create handlers (`transfers_create` at `transfers.py:130`, and the equivalent in `writeoffs.py:123`) currently do `session.get(Batch, batch_id.strip())` with no ownership/product-match check before re-rendering `selected_batch` into the picker on error/oversell/exception branches. Port the same 4-line ownership guard already proven in each file's own `*_batch_pick` endpoint.
- **D-11: Fix WR-02 (unstripped qty echo) in `transfers.py` ONLY.** `writeoffs.py` already computes the real parsed quantity from `operation.qty_delta` for its success echo. In `transfers.py`, `register_transfer`'s success return dict needs the actual transferred integer added, and `transfers_create`'s `context["saved"]` must use that integer instead of the raw `qty` form string.

### Claude's Discretion
- Exact Russian wording for the "override this portion's expiry/condition" fields on the transfer form, and for D-06's new validation error message.
- Whether the edit-page delete button on `/warehouses/{id}/edit` uses a full-page redirect response or an HTMX-driven in-place update, as long as the warn/stock-blocked states remain reachable and legible on that page.
- Whether `app/routes/mobile_transfers.py` needs the same override-field/same-warehouse changes — **RESOLVED by this research: yes.** Verified `mobile_transfers.py` calls `register_transfer` directly with the same signature as desktop, and has its own duplicate `_dest_warehouses()` filter. See Pitfall 3 below.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. The code-review debt closure (D-10/D-11) is not scope creep: it was pre-flagged in STATE.md as intended for this exact phase, and touches lines this phase rewrites anyway.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WH-01 | Warehouse list shows the current item count and the date of the last goods receipt for each warehouse | Pattern 1 (grouped aggregate query, modeled on verified `stale_products`/`batches_for_products` precedents); Standard Stack N/A (no new deps); see Pitfall 1 for preserving existing list features |
| WH-02 | Add/edit/delete warehouse are reached via links that open a dedicated form (add form, or pick-a-warehouse-then-edit/delete flow) | Code Examples section (mirrors verified `app/routes/products.py` GET `/new`/`/{id}/edit` pattern); Pitfall 1 and Pitfall 2 cover preserving list functionality and test rewrite scope |
| WH-03 | A warehouse can only be deleted while it holds zero stock | Already implemented and verified in `app/services/warehouses.py::soft_delete_warehouse` (stock guard checked first, non-overridable) — this phase only relocates its rendering, logic is untouched |
| XFER-01 | Transferring part of a batch whose moved portion has a different expiry date or condition from the remaining source batch creates a new destination batch and moves only that portion into it, leaving the source batch's remaining quantity and attributes unchanged | Pattern 2 (verified `dest = Batch(...)` extension point) + Pattern 3 (ownership check) + Pitfall 3 (mobile parity), Pitfall 4 (validation ordering), Pitfall 5 (override field visibility) |
</phase_requirements>

## Summary

This phase has no new external dependencies, no new database columns, and no new architectural
patterns — it is a pure extension/refactor of code that already exists and already works
correctly at the domain-logic level. Every canonical reference cited in `20-CONTEXT.md` was
read directly from the current repository (not training knowledge) and confirmed accurate:
`app/services/warehouses.py::soft_delete_warehouse`'s stock guard, `app/services/reports.py
::stale_products`'s outerjoin+group_by shape, `app/services/batches.py::batches_for_products`'s
page-wide query shape, `app/services/transfers.py::register_transfer`'s `dest = Batch(...)`
extension point, and `app/routes/transfers.py::_dest_warehouses`'s source-exclusion filter all
exist exactly as CONTEXT.md describes them, with exact line-level behavior verified below.

The two biggest findings beyond what CONTEXT.md already knew: (1) `app/routes/mobile_transfers.py`
**does** call `register_transfer` directly with the same five keyword arguments as desktop, and
it has its **own** independent `_dest_warehouses()` helper that duplicates desktop's
source-exclusion filter — so D-09's fix and D-05's override params must be threaded through the
mobile route and its own `_dest_warehouses()` too, not just desktop's. (2) The current
`/warehouses` page (`app/templates/pages/warehouses.html` +
`app/templates/partials/warehouse_rows.html`) is not simple inline-edit-only markup — it carries
a fully built-out filter/sort/status/pagination system (LIST-01..04, Phase 14) with per-column
filter inputs, a sort `<select>`, and a status filter reaching soft-deleted rows. D-01's
restructure to a "plain picker table" must preserve all of this list-management functionality
and only remove the inline `<input>` edit fields and the inline delete button — otherwise LIST-01
..04 regress. A large fraction of `tests/test_warehouses.py`'s existing web-slice tests
(`test_web_add_and_edit_rows`, `test_web_add_invalid_returns_swappable_422_partial`,
`test_web_delete_last_active_warehouse_warns_then_confirm_deletes`, and others) assert against
the CURRENT inline-row markup and will need rewriting for the new page shape — this is a bigger
test-surface change than CONTEXT.md's D-08 (which only calls out `tests/test_transfers.py`).

**Primary recommendation:** Follow CONTEXT.md's decisions D-01 through D-11 as locked; the
extension points they name are correct and load-bearing. Add mobile transfer route/template
parity (override params + `_dest_warehouses` filter removal) as a required task, not an
open question. Treat the warehouse list's existing filter/sort/pagination/status system as
a "must preserve" constraint on the D-01 restructure, and budget explicit rewrite effort for
`tests/test_warehouses.py`'s web-slice tests, not only `tests/test_transfers.py`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Warehouse CRUD (add/edit/delete) | Backend Server (FastAPI routes) | Database (SQLite via SQLAlchemy) | Thin routes in `app/routes/warehouses.py` delegate all writes to `app/services/warehouses.py`; no client-side state beyond form submission |
| Warehouse item-count / last-receipt-date metrics | Backend Server (grouped SQL query) | Database | Computed via SQLAlchemy aggregate queries against `batches`/`operations`, never cached columns — same pattern as `stale_products` |
| Warehouse delete guard (stock check, last-active warn) | Backend Server (`app/services/warehouses.py`) | Database | Pure server-side business rule; already implemented, only its rendering location moves |
| Batch-split transfer (override expiry/comment, same-warehouse split) | Backend Server (`app/services/transfers.py::register_transfer`) | Database (ledger write via `record_operation`) | All validation and the atomic two-row ledger write happen server-side; this is the single-write-path convention already established |
| Transfer form UI (desktop + mobile) | Frontend Server (Jinja2/HTMX server-rendered) | Browser (HTMX partial swaps) | No SPA; forms are rendered server-side, HTMX only swaps fragments — consistent with the rest of the app |

No client/browser-tier logic is introduced by this phase (no new JS beyond vendored HTMX
attribute wiring already used throughout the app).

## Package Legitimacy Audit

**Not applicable.** This phase introduces no new third-party packages. It uses only
`fastapi==0.139.0`, `sqlalchemy==2.0.51`, `alembic==1.18.5`, and `jinja2` — all already
installed and pinned in `pyproject.toml`, confirmed installed via:

```
$ uv run python -c "import fastapi, sqlalchemy, alembic; ..."
fastapi 0.139.0
sqlalchemy 2.0.51
alembic 1.18.5
```

`[VERIFIED: local venv via uv run]` — versions match `CLAUDE.md`'s Technology Stack table
exactly.

## Standard Stack

No new stack additions. This phase is pure application code within the existing stack
documented in `CLAUDE.md`.

### Alternatives Considered

Not applicable — no new technology choices in this phase.

## Architecture Patterns

### System Architecture Diagram

```
Operator (browser)
  |
  |-- GET /warehouses ------------------> [warehouses_page route] -> list_warehouses()
  |                                              |                        |
  |                                              v                        v
  |                                     picker table (name,        SELECT Warehouse rows
  |                                     address, item_count,       + NEW: grouped item-count
  |                                     last_receipt)              + last-receipt subqueries
  |
  |-- click "Изменить" ------> GET /warehouses/{id}/edit (NEW route)
  |                                   |
  |                                   v
  |                          warehouse_form.html (edit fields + delete button)
  |                                   |
  |            POST /warehouses/{id} (save) or POST /warehouses/{id}/delete (delete)
  |                                   |
  |                                   v
  |                     update_warehouse() / soft_delete_warehouse()
  |                     (stock guard -> last-active warn -> soft delete)
  |
  |-- GET /warehouses/new (NEW route) -> warehouse_form.html (add fields only)
  |                                   |
  |                            POST /warehouses (create) -> add_warehouse()
  |
  |-- GET /transfers -----------------> transfer_form.html
  |        |
  |        |-- code lookup -> GET /transfers/lookup -> open_batches() picker
  |        |-- batch pick  -> GET /transfers/batch-pick -> _dest_warehouses()
  |        |                        (NEW: no longer excludes source warehouse)
  |        |-- NEW: override fields (expiry, condition/comment) appear once
  |        |        a source batch AND a destination warehouse are selected
  |        v
  |   POST /transfers -> transfers_create()
  |                            |
  |                            v (WH-03/XFER-01 extension point)
  |                   register_transfer(..., new_expiry=, new_comment=)
  |                            |
  |            D-06: if dest_warehouse_id == source.warehouse_id
  |                  AND both override fields blank -> validation error
  |            else -> dest = Batch(expiry=new_expiry or source.expiry,
  |                                 comment=new_comment or source.comment, ...)
  |                    record_operation(-qty, source.id)
  |                    record_operation(+qty, dest.id)   <- single ledger write path
  |                    session.commit()
  |
  |-- Mobile: /m/transfers wizard --> transfers_step_dest.html
                                       |
                                       v (SAME register_transfer call, own
                                          _dest_warehouses() duplicate --
                                          NEEDS the same D-05/D-09 changes)
```

### Recommended Project Structure

No new files/directories needed beyond what CONTEXT.md's Integration Points already name:

```
app/
├── routes/
│   ├── warehouses.py         # restructure: add /new, /{id}/edit GET routes (D-01)
│   ├── transfers.py          # extend: override fields, ownership guard (D-05..D-11)
│   ├── mobile_transfers.py   # extend: same override params + _dest_warehouses fix
│   └── writeoffs.py          # touch only: ownership guard port (D-10)
├── services/
│   ├── warehouses.py         # extend list_warehouses() with D-03/D-04 grouped queries
│   └── transfers.py          # extend register_transfer() with D-06/D-07 override params
├── templates/
│   ├── pages/
│   │   └── warehouse_form.html   # NEW file, mirrors product_form.html structure
│   ├── partials/
│   │   ├── warehouse_rows.html   # simplify to picker table, KEEP filter/sort/status bar
│   │   ├── transfer_form.html    # add override fields
│   │   └── transfer_batch_wrap.html  # dest select gains source warehouse as an option
│   └── mobile_partials/
│       └── transfers_step_dest.html  # add override fields (mobile parity)
tests/
├── test_warehouses.py        # rewrite web-slice tests for new page shape
└── test_transfers.py         # update test_reject_same_warehouse premise (D-08)
```

### Pattern 1: Grouped page-wide aggregate query (D-03/D-04)
**What:** Compute a per-parent-row aggregate (count or max-date) for an entire page of parent
rows in ONE query, never N+1 per row.
**When to use:** Any list page showing a derived metric per row (warehouse item count, last
receipt date).
**Example (verified against the actual file, `app/services/reports.py:170-192`):**
```python
# Source: app/services/reports.py::stale_products (verified in this session)
last_sale = func.max(Operation.created_at).label("last_sale")
stmt = (
    select(Product, last_sale)
    .outerjoin(
        Operation,
        (Operation.product_id == Product.id) & (Operation.type == "sale"),
    )
    .where(Product.deleted_at.is_(None))
    .group_by(Product.id)
)
```
D-04's analogous query for warehouses:
```python
last_receipt = func.max(Operation.created_at).label("last_receipt")
stmt = (
    select(Batch.warehouse_id, last_receipt)
    .outerjoin(
        Operation,
        (Operation.batch_id == Batch.id) & (Operation.type == "receipt"),
    )
    .where(Batch.warehouse_id.in_(warehouse_ids))
    .group_by(Batch.warehouse_id)
)
```
Item count (D-03, distinct products with quantity > 0):
```python
item_count = func.count(func.distinct(Batch.product_id)).label("item_count")
stmt = (
    select(Batch.warehouse_id, item_count)
    .where(Batch.warehouse_id.in_(warehouse_ids), Batch.quantity > 0)
    .group_by(Batch.warehouse_id)
)
```
Both must be `IN(...)`-scoped to the current page's warehouse ids, mirroring
`app/services/batches.py::batches_for_products` (verified, `app/services/batches.py:37-53`) —
confirmed this file takes a `product_ids: list[str]` and does exactly one `.in_()` query,
grouping the results in Python afterward with `defaultdict(list)`.

### Pattern 2: Extension-point constructor with explicit override-or-inherit (D-07)
**What:** `register_transfer`'s `dest = Batch(...)` construction (verified,
`app/services/transfers.py:107-124`) already uses direct field assignment (never a bare `or`)
for `price_cents` — inheriting `source.price_cents` unconditionally today since there is no
override param yet. D-07 requires the SAME non-bare-`or` discipline for the two NEW override
params.
**Verified current code:**
```python
# Source: app/services/transfers.py:113-124 (verified in this session)
dest = Batch(
    id=new_id(),
    product_id=product.id,
    warehouse_id=dest_warehouse_id,
    name=source.name,
    expiry=source.expiry,
    price_cents=source.price_cents,
    location=source.location,
    comment=source.comment,
    quantity=0,
    is_legacy=0,
)
```
**Required change shape (D-06/D-07), NOT a bare `or` — a blank override must not silently
"win" over a real inherited value only when the override itself is truly blank:**
```python
new_expiry_clean = new_expiry.strip() if new_expiry else ""
new_comment_clean = new_comment.strip() if new_comment else ""
dest = Batch(
    ...,
    expiry=new_expiry_clean if new_expiry_clean else source.expiry,
    comment=new_comment_clean if new_comment_clean else source.comment,
    ...,
)
```
This mirrors the file's own established `price_cents=source.price_cents` direct-assignment
discipline (comment in the file's docstring, lines 1-12, explicitly calls this out as the
convention to follow).

### Pattern 3: Ownership-check-before-echo (D-10 port target)
**What:** Before re-rendering a client-submitted `batch_id` back into a picker on an error
branch, verify it belongs to the resolved product. This pattern EXISTS TODAY in the GET
batch-pick endpoints but is MISSING in the POST create handlers.
**Verified existing correct pattern** (`app/routes/transfers.py:92-96`,
`app/routes/writeoffs.py:85-88` — both identical):
```python
picked: Batch | None = None
if batch_id and product is not None:
    candidate = session.get(Batch, batch_id)
    if candidate is not None and candidate.product_id == product.id:
        picked = candidate
```
**Verified missing pattern (the bug, D-10 target)** — `app/routes/transfers.py:130` and
`app/routes/writeoffs.py:123` both currently do this instead, with NO ownership check:
```python
selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
```
Note: `app/routes/mobile_transfers.py::_pick_batch` (lines 74-83) ALREADY does the ownership
check correctly for its own error re-renders — mobile does NOT have this bug; D-10 is
desktop-only (`transfers.py` + `writeoffs.py`), confirming CONTEXT.md's scoping is accurate.

### Anti-Patterns to Avoid
- **N+1 per-row queries for item count / last receipt date:** the existing
  `list_warehouses()` iterates `session.scalars(select(Warehouse))` and filters/sorts in
  Python (verified, `app/services/warehouses.py:43-66`) — this is fine for warehouse rows
  themselves (small table) but the NEW metrics must NOT be computed with a per-row query
  inside that loop; use one grouped query per page as shown in Pattern 1.
- **Bare `or` for override fields:** `new_expiry or source.expiry` looks correct but a
  legitimate "explicitly clear this field" intent is impossible to distinguish from "field
  left blank" — not actually a risk here since D-06 makes at least one non-blank required for
  same-warehouse splits, but keep the explicit-strip-then-check style for clarity and to match
  the file's own established convention.
- **Two delete entry points:** CONTEXT.md's D-01 already rejects Option A (inline quick-delete
  AND edit-page delete) for this reason — confirmed correct; don't reintroduce a row-level
  delete button when building `warehouse_rows.html`'s new picker shape.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-warehouse item count / last receipt date | A Python loop computing these per warehouse row | SQLAlchemy grouped aggregate query (Pattern 1) | N+1 queries silently degrade as warehouse count grows; the codebase already has TWO precedents (`stale_products`, `batches_for_products`) for exactly this shape |
| Batch split write | A new standalone "split" table/model or a bespoke non-ledger write | Reuse `register_transfer` + `record_operation` (existing single-write-path) | The append-only ledger (`app/services/ledger.py::record_operation`, verified) is the ONLY sanctioned place `Operation` rows and `Batch.quantity`/`Product.quantity` projections are written — a parallel write path would break `rebuild_stock`'s invariant check |
| Same-warehouse "split" as a separate feature/route | A new `/transfers/split` endpoint and duplicate form | Relax `SAME_WAREHOUSE_ERROR` inside the existing `register_transfer`/`/transfers` flow (D-05) | Verified `record_operation` has no warehouse-equality constraint (`app/services/ledger.py`, no such check exists) — the guard was purely in `register_transfer`'s own validation, confirmed at `app/services/transfers.py:89-90` |

**Key insight:** every capability this phase needs (grouped aggregate queries, atomic
multi-row ledger writes, ownership-checked batch resolution) already has a working precedent
elsewhere in this codebase. The work is disciplined reuse/extension, not new mechanism design.

## Common Pitfalls

### Pitfall 1: Warehouse list restructure silently drops LIST-01..04 functionality
**What goes wrong:** D-01's "plain picker table" language could be read as "strip everything
back to a bare 3-column table," accidentally removing the name/address filter inputs, the
sort `<select>`, and the status filter (active/deleted/all) that Phase 14 (LIST-01..04)
already shipped and that 8+ existing tests assert on.
**Why it happens:** CONTEXT.md's D-01 focuses on the edit/delete affordance change (its actual
scope) and doesn't explicitly re-affirm the filter bar must survive.
**How to avoid:** Keep `warehouse_rows.html`'s filter-bar `<div class="filter-bar">`, the
per-column `filter-row` `<input>`s for name/address, and the status `<select>` — only replace
the per-row inline `name`/`address` `<input>` cells and the inline "Сохранить склад"/"Удалить"
buttons with a read-only name/address cell, item-count cell, last-receipt cell, and a single
"Изменить" link to `/warehouses/{id}/edit`.
**Warning signs:** If the plan's tasks don't mention preserving `list_status`/`list_sort`
query-param echoing (`_warehouses_context`'s existing `list_name`/`list_address`/etc. params,
verified at `app/routes/warehouses.py:37-89`) into the new edit-page redirect flow.

### Pitfall 2: `tests/test_warehouses.py` web-slice tests assume today's inline markup
**What goes wrong:** Tests like `test_web_add_and_edit_rows` (posts to `/warehouses/{id}` and
expects the row list swapped back with edited text inline), `test_web_add_invalid_returns_
swappable_422_partial`, and `test_web_delete_last_active_warehouse_warns_then_confirm_deletes`
(verified in `tests/test_warehouses.py:244-314`) all assert against the CURRENT single-page
inline-edit response shape. Once `/warehouses/{id}/edit` becomes a dedicated page and delete
moves there, these tests' request/response expectations are wrong by construction, not just
their premise.
**Why it happens:** CONTEXT.md's D-08 only names `tests/test_transfers.py`'s
`test_reject_same_warehouse` as needing a premise update — the warehouse test file's much
larger web-slice rewrite wasn't flagged.
**How to avoid:** Budget explicit plan tasks/waves for rewriting `tests/test_warehouses.py`'s
`test_web_*` section (lines ~225-369), not just adding new tests for `/warehouses/new` and
`/warehouses/{id}/edit`.
**Warning signs:** Running `uv run pytest tests/test_warehouses.py` after the restructure and
seeing failures in tests that were never touched by the plan.

### Pitfall 3: Mobile transfer flow silently diverges from desktop
**What goes wrong:** CONTEXT.md flagged this as "Claude's Discretion — verify during
research/planning." Verified: `app/routes/mobile_transfers.py:184-207` calls
`register_transfer(session, code=..., name=..., qty_raw=..., batch_id=..., dest_warehouse_id=...,
confirm=...)` — the exact same five-plus-confirm signature as desktop. It ALSO has its own
`_dest_warehouses()` (lines 36-40) that duplicates desktop's source-exclusion filter. If D-05
/D-06/D-07/D-09 only touch desktop's `app/routes/transfers.py`, the mobile wizard will (a)
still exclude the source warehouse from its destination radio list (D-09 not applied) and
(b) have no way to submit expiry/condition overrides (D-05/D-07 not applied) — same-warehouse
split becomes unreachable from mobile even after desktop ships it.
**Why it happens:** desktop and mobile are separate route/template trees by convention (noted
in CONTEXT.md's Established Patterns) and it's easy to treat "the phase" as "the desktop page."
**How to avoid:** Treat mobile parity as in-scope, not optional: remove the source-warehouse
filter from `mobile_transfers.py::_dest_warehouses` too, and add the same two override
`Form(...)` fields to `POST /m/transfers` plus corresponding fields in
`mobile_partials/transfers_step_dest.html`.
**Warning signs:** A plan that only lists `app/routes/transfers.py` and
`app/templates/partials/transfer_form.html` under "files touched" for XFER-01, with no mention
of `mobile_transfers.py` or `mobile_partials/transfers_step_dest.html`.

### Pitfall 4: Oversell/D-06 validation ordering interacts with confirm=1
**What goes wrong:** `register_transfer` currently checks `dest_warehouse_id == source.warehouse_id`
BEFORE the oversell warn-but-allow check (verified: same-warehouse check at lines 89-90 runs
before the oversell check at lines 92-105). D-06's new "same warehouse requires at least one
override field" validation must slot in at the SAME point (replacing the unconditional
same-warehouse rejection with a conditional one), not after the oversell check — otherwise a
same-warehouse submission with blank overrides could reach the oversell warn state before
being correctly rejected, producing a confusing two-step error flow for the operator.
**How to avoid:** Structure the new logic as: if `dest_warehouse_id == source.warehouse_id`
and both override fields are blank -> return the new blocking error immediately (same position
in the function as today's unconditional check), still before the oversell check.
**Warning signs:** A same-warehouse + blank-overrides submission that shows an oversell warning
instead of (or before) D-06's new validation error.

### Pitfall 5: `_wh_list` gating in `transfer_batch_wrap.html` assumes non-empty = "has a
real other destination"
**What goes wrong:** `app/templates/partials/transfer_batch_wrap.html:28-40` (verified) only
renders the destination `<select>` when `selected_batch_id and _wh_list`. Once D-09 removes the
source-warehouse exclusion from `_dest_warehouses()`, `_wh_list` will include the source
warehouse as an option even when it is the ONLY active warehouse — this is actually the
desired D-05 behavior (single-warehouse in-place split becomes reachable), but the override
fields (new UI, not yet built) must be visible/enabled specifically when the operator picks the
source warehouse as the destination, which the current template has no hook for.
**How to avoid:** Add the override fields unconditionally once a source batch is selected
(not conditionally on which destination is picked) — D-06's validation only requires them
when same-warehouse is chosen, but showing them always is simpler and matches "Claude's
Discretion" wording in CONTEXT.md about where these fields live.

## Runtime State Inventory

Not applicable — this phase is not a rename/refactor/migration phase. It adds behavior on top
of existing schema; no field/table renames occur.

## Code Examples

### Warehouse dedicated add/edit page structure (mirrors `app/routes/products.py`, verified)
```python
# Source: app/routes/products.py:174-203, 261-277 (verified in this session)
@router.get("/products/new")
def product_new(request: Request, code: str = "", session: Session = Depends(get_session)):
    context = {"product": None, ...}
    return templates.TemplateResponse(request, "pages/product_form.html", context)

@router.get("/products/{product_id}/edit")
def product_edit(request: Request, product_id: str, session: Session = Depends(get_session)):
    product = get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    context = {"product": product, ...}
    return templates.TemplateResponse(request, "pages/product_form.html", context)
```
D-01's `/warehouses/new` and `/warehouses/{id}/edit` should follow this exact GET-route shape;
`update_warehouse`'s existing `WAREHOUSE_NOT_FOUND_ERROR` dict-error return (not an exception)
means the edit route needs its own explicit `if warehouse is None: raise HTTPException(404)`
check before rendering (mirroring `product_edit`'s pattern using a fresh lookup, since
`update_warehouse` only returns the not-found error on the POST path today).

### Delete-with-redirect pattern (mirrors `app/routes/products.py:338-343`, verified)
```python
@router.post("/products/{product_id}/delete")
def product_delete(product_id: str, session: Session = Depends(get_session)):
    soft_delete_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": "/products"})
```
Products' delete is a simple one-shot HX-Redirect because it has no warn-then-confirm step.
Warehouses' delete is NOT this simple — `soft_delete_warehouse` has two possible warn states
(stock-blocked, last-active-warn) that must stay visible/interactive on the edit page (per
CONTEXT.md D-02, "Claude's Discretion" leaves HTMX-in-place vs. full-page redirect open) —
do not blindly copy the Products HX-Redirect-only pattern for the delete button; it must
render the SAME warn/stock-blocked states `warehouse_rows.html` shows today (lines 100-128,
verified), just relocated onto `warehouse_form.html`.

## State of the Art

Not applicable — no external ecosystem/library version drift concerns for this phase; all
tooling is pinned and already installed at the versions `CLAUDE.md` documents.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact Russian wording for the new override fields' labels and D-06's validation error message is left to planning/implementation (per CONTEXT.md's own Claude's Discretion) | Code Examples / Pattern 2 | Low — cosmetic, easily adjusted, explicitly deferred by the user already |
| A2 | The override fields should render unconditionally once a source batch is picked (Pitfall 5's recommendation), rather than only after the operator picks the source warehouse as destination | Pitfall 5 | Low-medium — if the planner instead makes them conditional on destination choice, it still satisfies XFER-01, just with one more interaction step; not a functional risk to the ledger |

**All other claims in this research were verified directly against the current repository
contents in this session** (file reads, `uv run` package version check, `uv run pytest` full
pass) — no WebSearch or training-data-only claims were needed for this phase, since it is
entirely internal codebase extension with a pinned, already-installed stack.

## Open Questions

None blocking. The one item CONTEXT.md flagged as unverified (`mobile_transfers.py` calling
`register_transfer` directly) is now resolved — confirmed yes, and its own duplicate
`_dest_warehouses()` filter is an additional, previously-unflagged detail (see Pitfall 3).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + uv venv | Running the app/tests | Yes | fastapi 0.139.0, sqlalchemy 2.0.51, alembic 1.18.5 (verified via `uv run python -c "import ..."`) | — |
| SQLite (`app.db`) | Local persistence | Yes (existing dev DB) | bundled `sqlite3` | — |
| pytest | Test suite | Yes | pinned `pytest==9.1.*` in `pyproject.toml` | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — this phase needs nothing beyond what is already
installed and working (`uv run pytest tests/test_transfers.py tests/test_warehouses.py` passes
41/41 at the start of this research session).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x (`pyproject.toml` pinned `pytest==9.1.*`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_warehouses.py tests/test_transfers.py -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WH-01 | Warehouse list shows item count + last receipt date | unit (service) | `uv run pytest tests/test_warehouses.py -k item_count -x` | ❌ Wave 0 — new tests needed in `list_warehouses` coverage |
| WH-01 | Item count / last-receipt uses a page-wide grouped query, not per-row | unit (service, query-count assertion or structural review) | `uv run pytest tests/test_warehouses.py -k last_receipt -x` | ❌ Wave 0 |
| WH-02 | `/warehouses` is a plain picker (no inline edit/delete) | web (route) | `uv run pytest tests/test_warehouses.py -k web_warehouses_page -x` | ✅ exists (needs rewrite, see Pitfall 2) |
| WH-02 | `/warehouses/new` renders add form; `POST /warehouses` creates | web (route) | `uv run pytest tests/test_warehouses.py -k warehouse_new -x` | ❌ Wave 0 |
| WH-02 | `/warehouses/{id}/edit` renders edit+delete form | web (route) | `uv run pytest tests/test_warehouses.py -k warehouse_edit -x` | ❌ Wave 0 |
| WH-03 | Delete blocked while stock > 0; succeeds at zero stock | unit (service) | `uv run pytest tests/test_warehouses.py -k stock_positive -x` | ✅ exists (`test_soft_delete_warehouse_blocked_when_stock_positive`), logic unchanged, only rendering location moves |
| XFER-01 | Same-warehouse split creates a new dest batch with only the moved qty, source unchanged | unit (service) | `uv run pytest tests/test_transfers.py -k same_warehouse -x` | ❌ Wave 0 — `test_reject_same_warehouse` must be renamed/rewritten (D-08) |
| XFER-01 | Cross-warehouse transfer with expiry/comment override | unit (service) | `uv run pytest tests/test_transfers.py -k override -x` | ❌ Wave 0 |
| XFER-01 | Blank overrides + same warehouse -> validation error, zero writes | unit (service) | `uv run pytest tests/test_transfers.py -k requires_override -x` | ❌ Wave 0 |
| D-10 (debt) | Batch-ownership leak fixed in `transfers.py`/`writeoffs.py` create handlers | unit/web | `uv run pytest tests/test_transfers.py tests/test_writeoffs.py -k ownership -x` | ❌ Wave 0 |
| D-11 (debt) | Success echo uses actual transferred qty, not raw form string | web | `uv run pytest tests/test_transfers.py -k qty_echo -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_warehouses.py tests/test_transfers.py -q`
- **Per wave merge:** `uv run pytest -q` (full suite — 41 tests currently pass as baseline;
  this phase's mobile-transfer touch also implicates `tests/test_mobile_transfers.py` if it
  exists — confirm during planning)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New service-level tests for `list_warehouses`' item-count/last-receipt grouped queries
      (WH-01)
- [ ] New route tests for `GET /warehouses/new` and `GET/POST /warehouses/{id}/edit` (WH-02)
- [ ] Rewrite of `tests/test_warehouses.py`'s `test_web_*` section (lines ~235-369) to match
      the new picker+dedicated-form page shape (see Pitfall 2)
- [ ] New/renamed tests in `tests/test_transfers.py` for D-05/D-06/D-07 (same-warehouse split,
      override fields, blank-override validation) replacing `test_reject_same_warehouse`'s old
      assertion (D-08)
- [ ] Confirm whether `tests/test_mobile_transfers.py` exists and needs the same parity
      additions as desktop's transfer tests (verify path during planning — not confirmed in
      this research session; only `app/routes/mobile_transfers.py` itself was read)
- [ ] New tests for D-10 (ownership guard in `transfers_create`/`writeoff_create`) and D-11
      (accurate qty echo) — these are regression tests for pre-existing advisory bugs, not new
      features, but need dedicated coverage since no test currently exercises the leak

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single local operator, no auth in v1 (per `CLAUDE.md` Constraints) |
| V3 Session Management | No | No sessions/auth in v1 |
| V4 Access Control | Yes | Batch-ownership check before trusting a client-submitted `batch_id` (D-10's target pattern, already proven in `transfers_batch_pick`/`writeoff_batch_pick`) — this IS the access-control-relevant pattern for this phase: preventing one product's batch data from being echoed/acted on via another product's context |
| V5 Input Validation | Yes | Qty parsing already uses the `isascii()+isdigit()` guard (never bare `int()`) per `app/services/transfers.py:59-62` (verified) — the new override fields (expiry, comment) should use the SAME `.strip()`-then-check discipline as existing `name`/`code`/`comment` fields elsewhere in the codebase (no new validation library needed; plain string handling matches project convention) |
| V6 Cryptography | No | No crypto surface in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Client-submitted `batch_id` naming another product's batch (IDOR-style) | Tampering / Information Disclosure | Ownership check (`candidate.product_id == product.id`) before any read-echo or write — ALREADY the pattern in `record_operation` (`app/services/ledger.py:99-100`, verified) and in the GET batch-pick endpoints; D-10 closes the remaining gap in the two POST create handlers |
| Client-submitted `dest_warehouse_id` naming an inactive/unknown warehouse | Tampering | `active_ids = {w.id for w in active_warehouses(session)}` membership check, verified at `app/services/transfers.py:86-88` — unchanged by this phase, still applies to the relaxed same-warehouse case |
| Stored XSS via batch `comment`/`location` free text rendered in the picker | Tampering (stored content) | Jinja2 autoescape only, `|safe` never used — verified in `batch_picker.html`'s own comment (line 22: "Jinja autoescape only, never `|safe`") — the new override comment field must follow the same discipline (no `|safe` filter) |

## Sources

### Primary (HIGH confidence) — all verified by direct file read in this session
- `app/services/warehouses.py` — `list_warehouses`, `add_warehouse`, `update_warehouse`,
  `soft_delete_warehouse`, `restore_warehouse` (full file read)
- `app/routes/warehouses.py` — all 6 routes, `_warehouses_context` (full file read)
- `app/services/transfers.py` — `register_transfer`, `recent_transfers` (full file read)
- `app/routes/transfers.py` — `_dest_warehouses`, all 4 routes (full file read)
- `app/routes/mobile_transfers.py` — full file read, confirmed `register_transfer` call +
  duplicate `_dest_warehouses`
- `app/routes/writeoffs.py` — full file read, confirmed `selected_batch` ownership gap
- `app/services/reports.py::stale_products` — full file read, confirmed outerjoin+group_by
- `app/services/batches.py` — `open_batches`, `batches_for_products`, `active_warehouses`
  (full file read)
- `app/services/ledger.py::record_operation` — full file read, confirmed no warehouse-equality
  constraint, confirmed mandatory `batch_id` + ownership check for stock-affecting types
- `app/models.py` — `Product`, `Warehouse`, `Batch` class definitions (grep + read, confirmed
  `expiry`/`comment`/`quantity` field shapes, no new columns needed)
- `app/routes/products.py` — full file read, confirmed dedicated add/edit page pattern to mirror
- `app/templates/pages/product_form.html`, `app/templates/pages/warehouses.html`,
  `app/templates/partials/warehouse_rows.html`, `app/templates/pages/transfer_form.html`,
  `app/templates/partials/transfer_form.html`, `app/templates/partials/transfer_batch_wrap.html`,
  `app/templates/partials/batch_picker.html`, `app/templates/mobile_partials/transfers_step_dest.html`
  — all read in full
- `tests/test_transfers.py`, `tests/test_warehouses.py` — full read, confirmed exact assertions
  that will need to change
- `alembic/versions/` directory listing — confirmed latest migration is `0014_drop_product_
  catalog_cents.py`, no pending migration needed for this phase (no new columns required)
- `uv run python -c "import fastapi, sqlalchemy, alembic; ..."` — confirmed installed versions
  match `CLAUDE.md` exactly
- `uv run pytest tests/test_transfers.py tests/test_warehouses.py -q` — confirmed 41/41 passing
  baseline before this phase's changes

### Secondary (MEDIUM confidence)
None — no WebSearch or Context7 lookups were needed; this phase is entirely internal codebase
extension with a pinned, already-verified stack.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new stack, versions verified against running venv
- Architecture: HIGH — every extension point read directly from source, line numbers cited
- Pitfalls: HIGH — derived from direct comparison of CONTEXT.md's claims against actual file
  contents, including one gap CONTEXT.md did not flag (test_warehouses.py web-slice rewrite
  scope) and one it flagged as unverified now resolved (mobile_transfers.py parity)

**Research date:** 2026-07-16
**Valid until:** 30 days (stable internal codebase, no fast-moving external dependency)
