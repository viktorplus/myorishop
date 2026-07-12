# Phase 10: Warehouse Transfers & Expiry Reporting - Research

**Researched:** 2026-07-12
**Domain:** FastAPI + HTMX server-rendered feature extension on an append-only SQLite ledger with per-batch stock projection
**Confidence:** HIGH (every claim verified against the actual Phase 8/9 code in this repo)

## Summary

This phase adds two small features on top of the fully-shipped Phase 9 batch ledger, with the user steer *«максимально примитивно»*. Both features are pure extensions of machinery that already exists and is proven in production code — no new libraries, no new interaction patterns, and (confirmed below) **no database migration**.

**WH-03 (transfers)** is a two-row ledger write through the existing single write path `record_operation()`: a `transfer` row with negative `qty_delta` on the source batch and a `transfer` row with positive `qty_delta` on a newly-created destination batch, both staged `commit=False` and closed with one `session.commit()`. The destination batch copies the source's frozen `price_cents` (this is *how* cost/price history is preserved), plus `expiry`, `comment`, `location`. Because both rows carry the same `product_id`, `Product.quantity` nets to zero while the two `Batch.quantity` projections move; the `rebuild_stock()` invariant holds automatically. The over-quantity guard reuses the writeoff `confirm=1` warn-but-allow pattern verbatim, scoped to the source batch's remaining quantity.

**LOT-06 (expiry report)** is a read-only page at `/reports/expiry` mirroring `/reports/stock`: a new read helper querying open batches (`quantity > 0`) with a non-NULL `expiry`, ordered earliest-first, with expired rows (`expiry < today`) visually flagged. No threshold, no filters.

**Primary recommendation:** Add `"transfer"` to BOTH `OPERATION_TYPES` (app/models.py) and `STOCK_AFFECTING_TYPES` (app/services/ledger.py), plus a RU label in `OPERATION_TYPE_LABELS`. Build a new `app/services/transfers.py` + `app/routes/transfers.py` mirroring the writeoff route/service shape (lookup → batch_picker → confirm gate). Add `expiring_batches()` to `app/services/batches.py` and a `/reports/expiry` route mirroring `/reports/stock`. Register the new router in `app/main.py`. No Alembic migration.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Transfers get a dedicated `/transfers` page (one per the operation-page-per-route convention). A nav link is added in `app/templates/base.html`.
- **D-02:** Transfer flow: enter product code → HTMX lookup lists that product's open batches (`quantity > 0`) via the shared `batch_picker.html` → pick source batch → pick a destination warehouse `<select>` (active warehouses only; the source batch's own warehouse excluded/disabled) → enter quantity → submit. Reuse the existing lookup + batch-picker machinery.
- **D-03:** A transfer is two ledger rows in one transaction via `record_operation()` (staged `commit=False`, one commit): a `transfer` row with negative `qty_delta` on the source batch, and a `transfer` row with positive `qty_delta` on the destination batch. Append-only triggers never touched.
- **D-04:** New operation type `"transfer"` added to `STOCK_AFFECTING_TYPES` (so `batch_id` mandatory on both rows; existing batch-ownership guard applies unchanged). A RU display label «Перемещение» is added wherever op types render.
- **D-05:** The destination batch is ALWAYS created new, inheriting `price_cents`, `expiry`, `comment`, and the storage-location tag from the source batch (only `warehouse_id` differs; `is_legacy=0`; fresh `id`). No resolve-or-create / top-up matching at the destination. Full transfer drives source batch to `quantity = 0`; partial transfer leaves the remainder.
- **D-06:** Transferring more than the source batch's remaining quantity reuses the existing per-batch warn-but-allow `confirm=1` zero-write re-POST pattern, scoped to the source batch's remaining quantity.
- **D-07:** The expiry report shows ALL open batches with a set expiry date, NO threshold. Scope: `quantity > 0` AND non-NULL `expiry` (legacy NULL-expiry batches excluded automatically). Sorted earliest expiry first. Expired batches (`expiry < today`) visually marked but stay in the list. Columns: product, warehouse, expiry date, remaining quantity, price, comment. No warehouse filter, no period filter (the `/reports/*` `period_filter.html` is NOT reused).
- **D-08:** The report is read-only at `/reports/expiry` inside the `/reports/*` family (mirrors `/reports/stock`), with a link on the reports landing (`reports_landing.html`). No inline write-off/list action. Nav stays under the existing «Отчёты» entry.

### Claude's Discretion
- Exact `/transfers` route/handler and template/partial filenames; how the destination-warehouse `<select>` excludes the source warehouse (server-filtered list vs disabled option).
- Exact RU label string for the `transfer` op type and how the two paired rows render/group in `/history` (two lines vs one combined line — either acceptable as long as both directions are visible).
- Exact query/service shape for the expiry report (new helper in `app/services/batches.py` vs `app/services/reports.py`) and the expired-marker styling.
- Whether the transfer service lives in a new `app/services/transfers.py` or extends an existing module.
- Index/query specifics for the expiry query.

### Deferred Ideas (OUT OF SCOPE)
- Configurable expiry threshold / "expiring within N days" filter — dropped for primitiveness.
- Warehouse filter on the expiry report.
- Inline "write off this expired batch" action from the report — operator uses the existing write-off page.
- Resolve-or-create / top-up of the destination batch (merge with an existing matching batch) — deferred.
- Mobile-flow screens (UI-01, Phase 11); auto-FEFO/FIFO (permanently out of scope); CSV warehouse/batch columns (EXP-V2-01, deferred); standalone batch-management/CRUD page.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WH-03 | User can transfer stock (a batch or part of it) from one warehouse to another without losing cost/price history | `record_operation()` two-row pattern (Finding 1); destination batch copies frozen `price_cents` (Finding 5); `confirm=1` over-qty guard (Finding 4); no-migration confirmation (Finding 8) |
| LOT-06 | Report of batches with an approaching or passed expiry date | `open_batches()` query idiom + new `expiring_batches()` helper (Finding 2); `/reports/stock` read-only page pattern (Finding 6); ISO-text expiry comparison for the expired marker (Finding 7) |

## Project Constraints (from CLAUDE.md)

Actionable directives the planner must honor:
- **Money as integer cents** — `price_cents` is `Integer`; never FLOAT/REAL. The destination batch copies `price_cents` as an int.
- **Portable ORM-only queries** — no SQLite-specific SQL (`INSERT OR REPLACE`, `strftime`). Use SQLAlchemy `select()` constructs only; the codebase already uses `nullslast()` for portability.
- **UUID String(36) PKs** — new destination batch gets `new_id()`; never an autoincrement int.
- **UTC ISO-8601 TEXT timestamps** — `created_at`/`updated_at` via `utcnow_iso()` (handled inside model defaults / `record_operation`). Note the expiry-report "today" comparison must use the operator's LOCAL date (`settings.display_tz`), not UTC — matching the receipt-service precedent (Finding 7).
- **Single write path** — Operation rows and `products.quantity`/`Batch.quantity` are written ONLY through `record_operation()`. The transfer service must not INSERT operations or mutate quantities directly.
- **Migrations never import app modules; native `ADD COLUMN`/new-table only** — moot here: no migration (Finding 8).
- **Optional fields checked with `is not None`, never bare `or`** — relevant when copying `price_cents` (a `0` price would be falsy).
- **RU for UI strings, English for code/comments/commits.**
- **GSD workflow** — edits must flow through a GSD command (already in effect).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Transfer validation (qty, batch ownership, warehouse, over-qty gate) | API/Backend service (`transfers.py`) | — | All stock invariants live server-side; the client `batch_id`/`warehouse_id` are untrusted (T-09 tampering mitigation, mirrors writeoffs/receipts) |
| Transfer ledger write (2 rows, dual projection) | Ledger single write path (`record_operation`) | — | The ONLY sanctioned writer of operations + quantity caches (FND-01) |
| Destination batch creation | API/Backend service | — | Batches are born only via receipts + migration + (now) transfers; still no CRUD surface |
| Source-batch lookup + picker fill | Frontend server (HTMX partial swap) | Browser (radio → hidden input sync) | Server decides fill vs 204; browser only swaps — the `/receipts/lookup` contract |
| Over-quantity warn-but-allow | API/Backend (zero-write check) | Browser (confirm re-POST via `hx-vals`) | Read-only check server-side; `confirm=1` bypass is a form-associated re-POST |
| Expiry report query | API/Backend read helper | — | Read-only; portable ORM; no writes |
| Expiry report rendering + expired marker | Frontend server (Jinja page) | — | Full-page render (no HX partial), mirrors `/reports/stock` |
| Transfer history attribution | Frontend server (read-time join) | — | `history_view` already LEFT-JOINs Batch; both rows render with «Партия: …» automatically |

## Standard Stack

No new packages. Every dependency this phase needs is already installed and pinned in `pyproject.toml`.

### Core (already present — versions verified in `pyproject.toml`)
| Library | Version (constraint) | Purpose | Why Standard |
|---------|----------------------|---------|--------------|
| fastapi | 0.139.* | Routing, `Form(...)` parsing, `TemplateResponse` | The app's framework; new `/transfers` + `/reports/expiry` routes are ordinary routers `[VERIFIED: pyproject.toml]` |
| sqlalchemy | 2.0.* | ORM `select()` queries, session, SQL-side quantity increment | Single-write-path + read helpers are all 2.0 `select()` style `[VERIFIED: app/services/*.py]` |
| jinja2 | 3.1.* | Server-rendered templates + `{% include %}` partials | `batch_picker.html` reuse, new report page `[VERIFIED: pyproject.toml]` |
| python-multipart | 0.0.32 | HTML `Form(...)` body parsing | Every operation POST needs it `[VERIFIED: pyproject.toml]` |
| htmx (vendored) | 2.0.10 | Code lookup, batch-picker swap, confirm re-POST | `app/static/htmx.min.js`, offline `[CITED: CLAUDE.md]` |

### Supporting (dev — already present)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.* | Test runner | Service + route tests for both features `[VERIFIED: pyproject.toml]` |
| httpx | 0.28.* | `TestClient` transport | Route tests via `client` fixture `[VERIFIED: tests/conftest.py]` |
| ruff | 0.15.* | Lint + format | `ruff check` / `ruff format` on new files `[VERIFIED: pyproject.toml]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two `record_operation()` rows | A single `transfer` row with `qty_delta=0` + warehouse in payload | Rejected: breaks the per-`Batch.quantity` projection (no way to move stock between two batches with one row); contradicts D-03 and the dual-projection invariant |
| New `app/services/transfers.py` | Extend `app/services/batches.py` (writes) | Rejected: `batches.py` is deliberately read-only ("this module never writes", `[VERIFIED: app/services/batches.py:1-7]`). A write feature belongs in its own service, matching writeoffs/receipts |
| `expiring_batches()` in `batches.py` | New `app/services/reports.py` helper | Either is acceptable per D-07 discretion. Recommendation: put it in `batches.py` beside `open_batches()` — it is a batch query sharing the same `quantity > 0` idiom |

**Installation:** None. `uv sync` already provides everything.

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** All code reuses libraries already pinned in `pyproject.toml` and verified present in the repo. No `npm`/`pip`/`cargo` install step, so no slopsquat surface.

## Architecture Patterns

### System Architecture Diagram

**Transfer flow (WH-03):**
```
Browser (/transfers page)
  │  type product code (hx-get, debounced)
  ▼
GET /transfers/lookup ──► lookup_prefill() ─► name + open_batches(product)  (ALL warehouses)
  │  server decides fill vs 204; oob-swap batch_picker.html
  ▼
Browser picks source-batch radio (hx-get) ──► GET /transfers/batch-pick
  │  re-query open batches (fresh qty), re-validate ownership, echo picked id
  ▼
Browser picks destination warehouse <select> (active, minus source WH) + qty
  │  submit (hx-post)
  ▼
POST /transfers ──► transfers.register_transfer(session, code, batch_id, dest_wh_id, qty, confirm)
        │
        ├─ validate: qty>0, product active, source batch owned by product,
        │            dest_wh active & != source WH
        ├─ if confirm != "1" and qty > source_batch.quantity:
        │       return {"oversell": {...}}  ──► warn partial (zero writes)  ◄── re-POST confirm=1
        │
        ├─ create destination Batch (copy price_cents/expiry/comment/location, new id, dest WH)
        ├─ session.add(dest_batch)
        ├─ record_operation(type_="transfer", product, qty_delta=-qty, batch_id=source.id, commit=False)
        ├─ record_operation(type_="transfer", product, qty_delta=+qty, batch_id=dest.id,   commit=False)
        └─ session.commit()   ─►  Product.quantity net 0; source.qty −qty; dest.qty +qty
  ▼
success partial: fresh form + «Перемещение сохранено» + refreshed recent list (oob)
```

**Expiry report flow (LOT-06):**
```
Browser (/reports landing link)
  ▼
GET /reports/expiry ──► expiring_batches(session)
        │  select(Batch, Product, Warehouse)
        │    .where(Batch.quantity > 0, Batch.expiry.is_not(None))
        │    .order_by(Batch.expiry.asc())
        ▼
  compute today = local date (settings.display_tz).isoformat()
  render pages/reports_expiry.html  (row.expiry < today → «просрочено» marker)
```

### Recommended Project Structure (new/changed files)
```
app/
├── models.py                         # +"transfer" in OPERATION_TYPES; +label in OPERATION_TYPE_LABELS
├── main.py                           # +import transfers; +include_router(transfers.router)
├── services/
│   ├── ledger.py                     # +"transfer" in STOCK_AFFECTING_TYPES (one-line set edit)
│   ├── transfers.py                  # NEW — register_transfer() + recent_transfers()
│   └── batches.py                    # +expiring_batches() read helper
├── routes/
│   ├── transfers.py                  # NEW — /transfers, /transfers/lookup, /transfers/batch-pick, POST /transfers
│   └── reports.py                    # +/reports/expiry route
└── templates/
    ├── base.html                     # +«Перемещение» nav link
    ├── pages/
    │   ├── transfer_form.html        # NEW (mirror pages/writeoff_form.html)
    │   └── reports_expiry.html       # NEW (mirror pages/reports_stock.html)
    └── partials/
        ├── transfer_form.html        # NEW (mirror partials/writeoff_form.html)
        ├── transfer_lookup.html      # NEW (mirror partials/writeoff_lookup.html)
        ├── transfer_batch_wrap.html  # NEW (mirror partials/writeoff_batch_wrap.html)
        ├── transfer_oversell.html    # NEW (mirror partials/writeoff_oversell.html)
        └── transfer_rows.html        # NEW recent-transfers list (mirror writeoff_rows.html)
    # reports_landing.html            # +«Сроки годности» link
```

### Pattern 1: Two-row transfer through the single write path
**What:** Stage both ledger rows before one commit; both carry the same `product_id`.
**When to use:** The transfer POST handler, after validation and the confirm gate.
**Example:**
```python
# Source: derived from app/services/receipts.py:203-257 (session.add(batch) + record_operation commit=False + one commit)
# and app/services/ledger.py:34-127 (record_operation signature/guards)
dest = Batch(
    id=new_id(),
    product_id=product.id,
    warehouse_id=dest_warehouse_id,
    name=source.name,                 # discretion: copy source name (preserve identity) — see Open Q1
    expiry=source.expiry,
    price_cents=source.price_cents,   # THIS preserves cost/price history (frozen snapshot copied)
    location=source.location,
    comment=source.comment,
    quantity=0,
    is_legacy=0,
)
session.add(dest)
record_operation(session, type_="transfer", product_id=product.id,
                 qty_delta=-qty, batch_id=source.id, commit=False)
record_operation(session, type_="transfer", product_id=product.id,
                 qty_delta=+qty, batch_id=dest.id, commit=False)
session.commit()
```
Note: `record_operation` resolves the batch via `session.get(Batch, batch_id)`, which autoflushes the pending `dest` row first, so `dest.id` is found. This is the exact receipts.py precedent (a brand-new batch passed to `record_operation` in the same transaction). `[VERIFIED: app/services/receipts.py, app/services/ledger.py]`

### Pattern 2: Warn-but-allow over-quantity (confirm=1), scoped to source batch
**What:** A read-only check that returns a warning payload with ZERO writes; `confirm=1` re-POST bypasses it.
**Example:**
```python
# Source: app/services/writeoffs.py:92-102
if confirm != "1" and qty > source_batch.quantity:
    return ({"oversell": {"product": product,
                          "available": source_batch.quantity,
                          "requested": qty}}, {})
```
UI side mirrors `partials/writeoff_oversell.html`: a `.error-block` with a `button ... form="transfer-form" hx-post="/transfers" hx-vals='{"confirm": "1"}'` and a client-only dismiss button. `[VERIFIED: app/templates/partials/writeoff_oversell.html]`

### Pattern 3: Read-only report page mirroring /reports/stock
**What:** A plain GET route that renders a full page (no HX partial), calling a read helper.
**Example:**
```python
# Source: app/routes/reports.py:153-165 (reports_stock_page)
@router.get("/reports/expiry")
def reports_expiry_page(request: Request, session: Session = Depends(get_session)):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()
    context = {"rows": expiring_batches(session), "today": today}
    return templates.TemplateResponse(request, "pages/reports_expiry.html", context)
```
`[VERIFIED: app/routes/reports.py]`

### Anti-Patterns to Avoid
- **Writing operation rows or quantities outside `record_operation()`** — breaks FND-01 single-write-path and the append-only guarantee. The transfer service must only *create the destination Batch row* directly (batches are not ledger rows); all stock movement goes through `record_operation()`.
- **Resolve-or-create at the destination** — explicitly rejected by D-05 (avoids the NULL-expiry equality-matching trap from Phase 9 D-01). Always create a fresh destination batch.
- **Reusing `period_filter.html` on the expiry report** — D-07: expiry is not a period query. The report has no date-range UI.
- **Comparing expiry against a UTC "today"** — would mis-flag batches near midnight. Use `settings.display_tz` local date (receipts.py precedent).
- **Trusting the client `batch_id` / `warehouse_id` / destination `<select>`** — re-validate ownership and active-warehouse membership server-side (T-09 mitigations, mirrors writeoffs/receipts).
- **Copying `price_cents` with a bare `or`** — a legitimate `0`-cent price would be dropped. Copy the attribute directly (it is an int-or-None; direct assignment preserves both).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Move stock between warehouses atomically | Custom SQL UPDATE of two batch quantities | Two `record_operation()` calls, `commit=False`, one commit | Single write path keeps the ledger append-only, updates both projections in one transaction, and keeps the rebuild invariant valid `[VERIFIED: app/services/ledger.py]` |
| Source-batch selection UI | New picker markup | `partials/batch_picker.html` via a `transfer_batch_wrap.html` wrapper | Shared partial already renders price/expiry/qty/comment radios + hidden input; the writeoff wrapper is a 1:1 template `[VERIFIED: app/templates/partials/writeoff_batch_wrap.html]` |
| Code→name lookup | New lookup endpoint logic | `lookup_prefill()` + the `/receipts/lookup` 204-vs-fill contract | Server decides fill vs no-op; typed name never clobbered `[VERIFIED: app/services/receipts.py:260-287]` |
| Over-quantity confirmation | New modal/JS state | `confirm=1` zero-write re-POST | Proven warn-but-allow pattern; no client state `[VERIFIED: app/services/writeoffs.py, writeoff_oversell.html]` |
| "Today" for expiry comparison | `date.today()` (UTC-ish, ambiguous) | `datetime.now(ZoneInfo(settings.display_tz)).date()` | Matches how the app computes local dates everywhere (receipts batch-name date) `[VERIFIED: app/services/receipts.py:210]` |
| Op-type RU label rendering | Inline conditionals | `OPERATION_TYPE_LABELS` Jinja global | Already exposed to every template; just add the `"transfer"` entry `[VERIFIED: app/routes/__init__.py:18]` |

**Key insight:** This phase is almost entirely *wiring existing, verified components together*. The only genuinely new logic is `register_transfer()` (validate → confirm gate → create dest batch → two writes) and `expiring_batches()` (one `select()`). Everything else is template/route mirroring.

## Runtime State Inventory

> Included because the phase touches shared runtime constants (`OPERATION_TYPES`, `STOCK_AFFECTING_TYPES`) that gate write-path behavior — even though it is a feature-add, getting these registrations wrong causes silent runtime failures.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | No renamed keys/collections. `operations.type` is `String(20)` with **no CHECK constraint** and no enum table; `"transfer"` is simply a new value. Destination batch is an ordinary `batches` row. | None — no data migration. |
| Live service config | None. Single local app, no external services. | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | None referenced by name. `settings.display_tz` (existing) is reused for the local-date comparison. | None. |
| Build artifacts / registrations | `OPERATION_TYPES` tuple (app/models.py:34) gates `record_operation`'s `unknown operation type` guard; `STOCK_AFFECTING_TYPES` frozenset (app/services/ledger.py:18) gates the mandatory-batch guard; `OPERATION_TYPE_LABELS` dict (app/models.py:59) renders the `/history` «Тип» column; `history_rows.html:35` tuple gates the batch-attribution second line; `main.py` router registration list. | **Code edits (not migrations):** add `"transfer"` to `OPERATION_TYPES`, `STOCK_AFFECTING_TYPES`, and `OPERATION_TYPE_LABELS`; register the new router in `main.py`. `history_rows.html` needs NO change (transfer is stock-affecting, so it already gets the «Партия: …» line). |

**Canonical question — what still holds the old state after a source rename?** N/A (no rename). The one non-obvious runtime gotcha: **forgetting to add `"transfer"` to `OPERATION_TYPES`** makes `record_operation` raise `ValueError: unknown operation type: 'transfer'`; **forgetting `STOCK_AFFECTING_TYPES`** makes it treat transfer as an audit type and raise `'transfer' operations are batch-less` when a `batch_id` is passed. Both must be added together. `[VERIFIED: app/services/ledger.py:72-100]`

## Common Pitfalls

### Pitfall 1: Registering `"transfer"` in only one of the two type sets
**What goes wrong:** `record_operation` raises at the first transfer.
**Why:** `OPERATION_TYPES` (models.py) is the "is this a real type" gate; `STOCK_AFFECTING_TYPES` (ledger.py) is the "does this require a batch" gate. They are independent.
**How to avoid:** Add `"transfer"` to both, plus `OPERATION_TYPE_LABELS`. A test asserting a successful transfer covers this.
**Warning signs:** `ValueError: unknown operation type` or `'transfer' operations are batch-less`.

### Pitfall 2: Destination-batch creation ordering vs `record_operation`
**What goes wrong:** `record_operation` can't find the destination batch → `unknown batch`.
**Why:** `record_operation` does `session.get(Batch, batch_id)`. The new `dest` must be `session.add()`-ed before the positive-delta call so autoflush inserts it first.
**How to avoid:** `session.add(dest)` immediately after constructing it, before either `record_operation`. (Receipts.py proves this exact sequence works.) `[VERIFIED: app/services/receipts.py:224-248]`

### Pitfall 3: Net-zero product delta breaks a naive oversell check
**What goes wrong:** If someone later adds a product-level oversell check to transfers, it would never trip (product total is unchanged).
**Why:** A transfer is stock-neutral at the product level; only batch quantities move. The correct guard is **per source batch** (D-06), exactly like the writeoff per-batch guard.
**How to avoid:** Scope the `confirm=1` check to `source_batch.quantity`, never `product.quantity`.

### Pitfall 4: Transfer to the same warehouse
**What goes wrong:** A no-op batch split, or (worse) a stale form posting the source warehouse.
**Why:** The destination `<select>` should exclude the source WH, but the client is untrusted.
**How to avoid:** Server-side, reject `dest_warehouse_id == source_batch.warehouse_id` with a RU error, in addition to filtering/disabling it in the `<select>`. `[CITED: 10-CONTEXT.md D-02]`

### Pitfall 5: Expiry sort/compare correctness
**What goes wrong:** Wrong ordering or mis-flagged "expired".
**Why:** `expiry` is ISO `yyyy-mm-dd` TEXT — lexicographic sort == chronological sort (safe). The expired marker compares `b.expiry < today_iso` (string compare, also safe for ISO). But `today` must be the LOCAL date.
**How to avoid:** `order_by(Batch.expiry.asc())`; compute `today = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()`. NULL expiry is filtered out by the `is_not(None)` clause so `nullslast` is unnecessary (but harmless). `[VERIFIED: app/models.py:160-162, app/services/batches.py:30]`

### Pitfall 6: HTMX 422 swap + focus-after-swap
**What goes wrong:** Validation errors silently discarded, or focus not returned to «Код».
**Why:** htmx 2 does not swap 4xx by default; the app's `htmx-config` opts 422 in. `autofocus` does not fire inside swapped content — the forms use an explicit `hx-on::load` focus hook.
**How to avoid:** Mirror `writeoff_form.html` exactly — return the form partial with `status_code=422` on validation errors, and use the `focus_code` → `hx-on::load="...focus()"` hook. `[VERIFIED: app/templates/base.html:9-10, app/templates/partials/writeoff_form.html:6]`

### Pitfall 7: Defensive rollback before re-querying the session on POST failure
**What goes wrong:** A commit-time error leaves the session in pending-rollback; the subsequent `_form_extras`/recent-list SELECT raises `PendingRollbackError` → raw 500.
**Why:** Documented in receipts.py CR-01 / writeoffs.py WR-03.
**How to avoid:** Wrap the service call in `try/except`, `session.rollback()` + log, return the form partial with a RU form error at 422. `[VERIFIED: app/routes/writeoffs.py:135-150, app/routes/receipts.py:193-210]`

## Code Examples

### Expiry report read helper (new, in app/services/batches.py)
```python
# Source: pattern derived from app/services/batches.py:15-32 (open_batches) +
# app/services/operations.py:33-38 (Product/Warehouse joins for display)
from sqlalchemy import select
from app.models import Batch, Product, Warehouse

def expiring_batches(session: Session) -> list[dict]:
    """Open batches (quantity > 0) with a set expiry, earliest first (LOT-06/D-07).

    Legacy batches (NULL expiry) are excluded by the is_not(None) filter.
    Read-only; portable ORM (no SQLite-specific SQL, D-05 sync-readiness).
    """
    rows = session.execute(
        select(Batch, Product, Warehouse)
        .join(Product, Batch.product_id == Product.id)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Batch.quantity > 0, Batch.expiry.is_not(None))
        .order_by(Batch.expiry.asc(), Batch.created_at.asc())
    ).all()
    return [{"batch": b, "product": p, "warehouse": w} for b, p, w in rows]
```

### Register the new router (app/main.py)
```python
# Source: app/main.py:8-24, 41-55 — add to the import tuple and the include list
from app.routes import (..., transfers, ...)
app.include_router(transfers.router)
```

### Add the op type + label (app/models.py)
```python
# Source: app/models.py:34-43, 59-68
OPERATION_TYPES = (
    "receipt", "sale", "writeoff", "return", "correction",
    "transfer",                       # NEW — WH-03
    "price_change", "product_created", "product_edited",
)
OPERATION_TYPE_LABELS = {
    ..., "correction": "Корректировка",
    "transfer": "Перемещение",        # NEW — WH-03
    ...,
}
```

### Add to the stock-affecting set (app/services/ledger.py)
```python
# Source: app/services/ledger.py:18
STOCK_AFFECTING_TYPES = frozenset(
    {"receipt", "sale", "writeoff", "return", "correction", "transfer"}
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Product-level stock only | Per-batch `Batch.quantity` projection alongside `Product.quantity` | Phase 9 (migration 0008) | Transfers move batch quantities; product total stays net-zero |
| `declarative_base()` legacy style | SQLAlchemy 2.0 `DeclarativeBase` + `Mapped[]` | Project inception | New code uses `select()`, `Mapped[]` — no 1.x idioms |
| batch_id optional | batch_id mandatory for `STOCK_AFFECTING_TYPES` | Phase 9 D-12 | `"transfer"` joining that set makes batch mandatory on both rows automatically |

**Deprecated/outdated:** None relevant. No package upgrades in scope.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The destination batch should copy the source's `name` (auto-generated «{product.name} — {date}» label) rather than regenerate it | Pattern 1 / Open Q1 | Low — `name` is a nullable display label (String(220)); either choice is cosmetic. D-05 does not list `name` among the inherited fields, so this is a discretion call. Regenerating with today's date is equally valid |
| A2 | RU label for `"transfer"` is «Перемещение» | Code Examples | Low — D-04 gives «Перемещение» as an example; exact string is discretion |

**Note:** No assumptions touch compliance, security, retention, or performance targets. Both are cosmetic/discretionary and explicitly delegated to Claude's discretion in CONTEXT.md.

## Open Questions

1. **Destination batch `name` field**
   - What we know: D-05 lists `price_cents`, `expiry`, `comment`, `location` as inherited; `is_legacy=0`, fresh `id`, differing `warehouse_id`. `Batch.name` is a nullable auto-label.
   - What's unclear: copy source `name` vs regenerate «{product.name} — {today}».
   - Recommendation: **Copy the source `name`** — it preserves the batch's visual identity/history across the move (consistent with "don't lose history"). Regeneration is acceptable if the planner prefers a transfer-dated label. Flag for the planner as a one-line decision.

2. **`/history` rendering of the two paired rows**
   - What we know: `history_view` LEFT-JOINs Batch; each row already carries its own `batch`. Both `transfer` rows are stock-affecting, so `history_rows.html` renders the «Партия: …» second line for each automatically. The source row shows `qty_delta` negative, the destination positive.
   - What's unclear: whether to visually group the pair (D-03/discretion allows two separate lines).
   - Recommendation: **Two separate rows** (no template change needed beyond the label already covered by `OPERATION_TYPE_LABELS`). Both directions are visible, satisfying the "recorded in history" success criterion with zero extra work. Confirm this satisfies success criterion 2 during planning.

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* + FastAPI `TestClient` (httpx 0.28.*) `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_transfers.py -x` (new file) |
| Full suite command | `uv run pytest` |

Shared fixtures already available in `tests/conftest.py`: `session`, `product`, `warehouse`, `batch` (empty batch in a warehouse), `stocked_product` (ledger-backed stock via a batched receipt), `client` (TestClient with `get_session` overridden and startup backup disabled). A transfer test needs a *stocked source batch in a known warehouse* plus a *second active warehouse* — extend the `stocked_product`/`batch` fixtures or build inline. `[VERIFIED: tests/conftest.py]`

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WH-03 | Transfer writes exactly two `transfer` ops (source −qty, dest +qty) in one transaction | unit | `uv run pytest tests/test_transfers.py::test_transfer_writes_two_rows -x` | ❌ Wave 0 |
| WH-03 | `Product.quantity` unchanged (net-zero); source `Batch.quantity` −qty; dest `Batch.quantity` +qty | unit | `uv run pytest tests/test_transfers.py::test_transfer_projections -x` | ❌ Wave 0 |
| WH-03 | Destination batch inherits `price_cents`/`expiry`/`comment`/`location`, differs only in `warehouse_id`, `is_legacy=0`, new id | unit | `uv run pytest tests/test_transfers.py::test_dest_batch_inherits_history -x` | ❌ Wave 0 |
| WH-03 | Full transfer drives source batch to `quantity=0` (drops out of `open_batches`) | unit | `uv run pytest tests/test_transfers.py::test_full_transfer_empties_source -x` | ❌ Wave 0 |
| WH-03 | Over-quantity: `confirm != "1"` returns oversell payload with ZERO writes; `confirm="1"` writes | unit | `uv run pytest tests/test_transfers.py::test_over_qty_confirm_gate -x` | ❌ Wave 0 |
| WH-03 | Same-warehouse transfer rejected with RU error | unit | `uv run pytest tests/test_transfers.py::test_reject_same_warehouse -x` | ❌ Wave 0 |
| WH-03 | Untrusted `batch_id` (other product) / inactive dest warehouse rejected | unit | `uv run pytest tests/test_transfers.py::test_reject_tampered_ids -x` | ❌ Wave 0 |
| WH-03 | `rebuild_stock()` invariant still holds after a transfer | unit | `uv run pytest tests/test_transfers.py::test_rebuild_invariant_after_transfer -x` | ❌ Wave 0 |
| WH-03 | Transfer appears in `/history` with «Перемещение» label, both directions | integration | `uv run pytest tests/test_transfers.py::test_transfer_in_history -x` | ❌ Wave 0 |
| WH-03 | `GET /transfers`, `/transfers/lookup`, `/transfers/batch-pick`, `POST /transfers` HTTP happy paths | integration | `uv run pytest tests/test_transfers.py -k route -x` | ❌ Wave 0 |
| LOT-06 | `expiring_batches()` returns only `quantity>0` AND non-NULL expiry, earliest first, legacy excluded | unit | `uv run pytest tests/test_batches.py::test_expiring_batches_filter_and_order -x` | ⚠️ extend existing `tests/test_batches.py` |
| LOT-06 | `GET /reports/expiry` renders rows; expired batch (`expiry < today`) carries the marker; empty state shown when none | integration | `uv run pytest tests/test_reports.py::test_expiry_report_page -x` | ⚠️ extend existing `tests/test_reports.py` |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_transfers.py -x` (new work) or the touched file's tests.
- **Per wave merge:** `uv run pytest` (full suite green).
- **Phase gate:** Full suite green + `ruff check` clean before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_transfers.py` — NEW file covering all WH-03 rows above.
- [ ] `tests/test_batches.py` — ADD `expiring_batches()` cases (file exists).
- [ ] `tests/test_reports.py` — ADD `/reports/expiry` route cases (file exists).
- [ ] Fixture: a stocked source batch + a second active warehouse (extend `conftest.py` or build inline in `test_transfers.py`).
- [ ] Framework install: none — pytest/httpx already in the dev group.

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high` in config. This is a single-operator local app (no auth in v1), so the relevant ASVS surface is input validation and access-control-of-untrusted-identifiers, not authn/session.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Single local operator, no auth in v1 (CLAUDE.md) |
| V3 Session Management | no | No sessions |
| V4 Access Control | yes | Server-side re-validation of `batch_id` ownership (`batch.product_id == product.id`) and destination warehouse active-membership — the client is untrusted (mirrors writeoffs T-09-12, receipts T-09-04/05) |
| V5 Input Validation | yes | `qty` parsed strictly (`isascii()`+`isdigit()`, `>0`); `warehouse_id`/`batch_id` checked against server-side sets; `confirm` allow-listed to `"1"`; expiry compared as validated ISO text |
| V6 Cryptography | no | No secrets/crypto in scope |

### Known Threat Patterns for {FastAPI + HTMX + SQLite ledger}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered `batch_id` naming another product's / another warehouse's batch | Tampering / Elevation | `record_operation` rejects `batch.product_id != product_id`; service re-checks source-batch ownership before the confirm gate `[VERIFIED: app/services/ledger.py:97-98, app/services/writeoffs.py:86-88]` |
| Tampered destination `warehouse_id` (inactive/deleted, or == source) | Tampering | Re-check against `active_warehouses(session)` and reject `== source.warehouse_id` server-side `[CITED: 10-CONTEXT.md D-02]` |
| Negative / non-integer / huge qty | Tampering | `isascii()+isdigit()` parse → `>0` guard (writeoffs precedent) `[VERIFIED: app/services/writeoffs.py:63-66]` |
| Stored XSS via batch `comment`/`location`/product name on the report or picker | Tampering (XSS) | Jinja autoescape only, NEVER `|safe` — the `batch_picker.html` and `history_rows.html` comments explicitly warn (T-09-11/T-05-18) `[VERIFIED: app/templates/partials/batch_picker.html:22-23]` |
| Ledger mutation to fake/undo a transfer | Repudiation / Tampering | Append-only DB triggers (`operations_no_update`/`operations_no_delete`) — transfers only INSERT; never touched `[VERIFIED: 09-CONTEXT.md, migration 0001]` |
| Double-submit racing two transfers of the same batch | Tampering | WAL single-writer + `commit=False`/one-commit discipline; `confirm=1` check reads fresh `batch.quantity`. Residual: an over-transfer past remaining is *allowed by design* (D-06 warn-but-allow) — not a vulnerability, a product decision |

No high-severity issues block this phase: all threats have an established mitigation already in the codebase that the new code inherits by reusing `record_operation()` and the writeoff/receipt validation shape.

## Environment Availability

Not applicable — this phase is code + template changes only, using the already-installed stack. No new external tools, services, runtimes, or CLIs. (`uv`, Python 3.13, and the pinned dependencies are the existing dev environment.)

## Sources

### Primary (HIGH confidence — read this session)
- `app/services/ledger.py` — `record_operation()` signature/guards, `STOCK_AFFECTING_TYPES`, dual projection, `rebuild_stock` invariant.
- `app/services/batches.py` — `open_batches()` query idiom, `active_warehouses()`, read-only contract.
- `app/services/receipts.py` — batch creation + `record_operation(commit=False)` + one-commit precedent; `lookup_prefill()` 204-vs-fill contract; local-date usage.
- `app/services/writeoffs.py` + `app/routes/writeoffs.py` — `confirm=1` warn-but-allow gate, per-batch scope, defensive rollback, form-echo pattern.
- `app/services/operations.py` — `history_view` LEFT-JOIN Batch (transfer rows render automatically).
- `app/models.py` — `OPERATION_TYPES` (no CHECK constraint on `operations.type`), `OPERATION_TYPE_LABELS`, `Batch` columns (`price_cents`, `expiry`, `comment`, `location`, `name`, `is_legacy`).
- `alembic/versions/0008_batches.py` — batches table shape; confirms `operations.type` gains values with no migration.
- `app/templates/partials/{batch_picker,writeoff_lookup,writeoff_batch_wrap,writeoff_form,writeoff_oversell,history_rows}.html`, `base.html`, `pages/reports_stock.html`, `reports_landing.html` — template mirroring targets.
- `app/routes/{receipts,reports,history}.py`, `app/routes/__init__.py`, `app/main.py` — route/registration/Jinja-globals patterns.
- `tests/conftest.py`, `pyproject.toml` — test harness, fixtures, pinned versions.
- `.planning/phases/10-warehouse-transfers-expiry-reporting/10-CONTEXT.md`, `09-CONTEXT.md`, `.planning/REQUIREMENTS.md` — locked decisions and requirement text.

### Secondary / Tertiary
- None needed — all findings verified directly against repo code; no external lookups required.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions read from `pyproject.toml`; no new packages.
- Architecture: HIGH — every pattern traced to a working, shipped call site in this repo.
- Pitfalls: HIGH — each pitfall is an in-code documented invariant (guard raises, trigger DDL, htmx-config, rollback comments).
- Security: HIGH — mitigations already present in reused code; single-user local app narrows the surface.

**Research date:** 2026-07-12
**Valid until:** 2026-08-11 (stable — pinned deps, no fast-moving external surface; re-verify only if Phase 9 ledger/batch code changes)
