# Phase 8: Warehouses - Research

**Researched:** 2026-07-11
**Domain:** Internal CRUD feature on an existing FastAPI + SQLAlchemy 2.0 + Alembic + Jinja2 + htmx stack (no new external technology)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Warehouse <-> stock attribution (the central architectural decision)**
- **D-01:** `Warehouse` is a **standalone table** in this phase — no FK added to `Product` or `Operation`. Modeled directly on the `Dictionary` precedent (migration 0002): a new table introduced with zero wiring into existing tables. The real stock<->warehouse link (`Batch.warehouse_id`) is Phase 9's job, per the ROADMAP.md dependency note ("structural prerequisite for Phase 9 — `Batch.warehouse_id` needs `Warehouse` to exist first").
- **D-02:** Success criterion 2 ("all existing v1.0 stock is automatically attributed to a seeded default warehouse after migration, with no data loss") is satisfied **conceptually**, not via an explicit FK row-by-row: the migration seeds exactly one default `Warehouse` row (via `op.bulk_insert`, same pattern as migration 0001's initial seed), and nothing is lost because nothing yet references warehouses to lose. Do NOT add a `Product.warehouse_id` column — that would model a false 1-product-to-1-warehouse relationship that Phase 9 immediately breaks (a product code can span multiple batches across multiple warehouses, LOT-01).
- **D-03:** Phase 9's `Batch` migration is expected to point its default "legacy batch" at this same seeded default-warehouse row (Phase 9 success criterion 5 already commits to a default legacy batch). Downstream planners for Phase 9 should treat the seeded warehouse's identity (e.g., a stable name or a documented lookup) as something Phase 9 can rely on.

**Warehouse fields**
- **D-04:** `Warehouse` has `name` (required) **plus an optional free-text address/note field** — mirrors the `Customer` model's optional-extras pattern (`surname`, `consultant_number`: nullable, no uniqueness enforced). Exact column name is the planner/executor's call (e.g. `address` or `note`).
- **D-05:** Standard soft-delete/audit columns matching the `Product`/`Customer` convention: `id` (UUID String(36) PK via `new_id`), `created_at`/`updated_at` (`utcnow_iso`), `deleted_at` (nullable, soft-delete only, no hard deletes).

**Default warehouse deletion guard**
- **D-06:** Soft-deleting the last remaining **active** warehouse uses the **warn-but-allow** pattern already established for oversell (`app/services/sales.py`) and below-minimum-price (Phase 7) — a warning block requiring one extra confirm click, not a hard block. This keeps the interaction language consistent app-wide; soft-delete is already fully reversible via restore, so nothing is destroyed either way.
- **D-07:** This guard governs *deletion*, not *consumption*. Phase 9's batch-creation flow must still defensively handle a "zero active warehouses" state on its own (e.g., clear message, disabled form) — it cannot assume the Phase 8 guard makes that state impossible forever (a fresh/test DB or manual data edit could still reach it).

**Management page style**
- **D-08:** Single settings-style page (`/warehouses`), **not** a full Products-style list+search+`/new`+`/{id}/edit` CRUD scaffold. Modeled on the existing `Dictionary` page pattern (`app/routes/dictionary.py`, `app/templates/pages/dictionary.html`, `app/templates/partials/dictionary_rows.html`): one page, inline add row, inline per-row edit, `hx-post`/`hx-swap="outerHTML"` against a shared rows partial.
- **D-09:** Unlike `Dictionary` (which has no delete today), this page adds inline delete/restore buttons directly in the row table — both active and soft-deleted warehouses stay visible in the same list (deleted rows shown distinctly, e.g. grayed out, with a "Восстановить" button), so a deleted warehouse is never a dead end reachable only via a direct edit URL. This is a deliberate deviation from the Products pattern (where a soft-deleted item disappears from the list entirely and is reachable only via `/products/{id}/edit`) — Products' pattern was rejected specifically because it creates a discoverability trap for a small, rarely-changing entity set. Reuse the existing `hx-confirm` delete / restore convention from `app/routes/products.py` for the actual delete/restore actions.
- **D-10:** No search bar, no pagination — matches the roadmap's own phrasing ("a warehouse management page", singular) and the expected cardinality (a handful of physical locations for a single small reseller, not hundreds).

### Claude's Discretion
- Exact column name for the optional address/note field (`address` vs `note` vs similar).
- Exact route module placement (new `app/routes/warehouses.py` vs. folding into an existing module) — new module is the obvious fit given `Dictionary`/`Product`/`Customer` precedent, but final call is the planner's.
- Exact partial filename for the rows table (suggested `warehouse_rows.html`, mirroring `dictionary_rows.html`).
- How exactly the active-row edit state and deleted-row restore state are visually/structurally distinguished in the single rows table (mirrors the existing `error_entry_id`-style branching already used in `dictionary_rows.html`).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. No scope-creep items were raised. Warehouse-to-stock wiring, per-batch location tags, and warehouse selection in operation forms were all recognized as Phase 9 territory during discussion, not pulled into this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WH-01 | User can create and manage multiple warehouses | Standard Stack / Architecture Patterns / Code Examples below give the exact model, migration, service, route, and template shape to implement create/edit/soft-delete/restore on a dedicated `/warehouses` page, reusing verified codebase conventions (Dictionary single-page CRUD + Product soft-delete/restore + Phase 7 warn-but-allow). |
</phase_requirements>

## Summary

This phase requires **zero new libraries or external technology** — it is a same-shape extension of patterns already proven three times in this codebase: the `Dictionary` single-page inline-CRUD (migration 0002 + `app/routes/dictionary.py` + `app/templates/pages/dictionary.html` + `app/templates/partials/dictionary_rows.html`), the `Product` soft-delete/restore convention (`app/services/catalog.py::soft_delete_product`/`restore_product` + `app/routes/products.py`), and the Phase 7 warn-but-allow confirm-gate pattern (`app/services/sales.py::register_sale` + `app/templates/partials/sale_price_warning.html`). All claims below are `[VERIFIED: codebase]` — confirmed by reading the actual files, not by web search, since this phase introduces no new package or API surface.

The one genuinely new interaction is the "last active warehouse" delete guard (D-06/D-07), which has no exact precedent in the codebase (the two existing warn-but-allow checks gate a multi-line **basket** re-POST, not a single-row **delete** action). Section "Architecture Patterns > Pattern 3" below adapts the same confirm=1 mechanics to a single delete route, modeled on the `error_entry_id` row-level branching already used in `dictionary_rows.html`.

**Primary recommendation:** Copy the `Dictionary` page/route/service triad file-for-file as the skeleton, add a `deleted_at` column and delete/restore routes matching `Product`'s convention, and gate the last-active-warehouse delete with a confirm=1 flag rendered inline in the same row (not a redirect, and not a separate warning page) — the Dictionary page has no separate detail/edit page to redirect to, so every write response must re-render `partials/warehouse_rows.html`, never `HX-Redirect`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Warehouse CRUD (create/edit) | API / Backend | Database / Storage | Plain server-rendered form POST + SQLAlchemy write, no client-side state — matches every existing catalog/dictionary/customer flow in this app. |
| Soft-delete / restore | API / Backend | Database / Storage | `deleted_at` toggle is a backend write; the warn-but-allow last-warehouse check is backend business logic (mirrors `sales.py`), never client-side. |
| Inline row rendering (active vs. deleted display) | Frontend Server (SSR) | — | Jinja2 template branching on `deleted_at`, rendered server-side; htmx only swaps the returned HTML fragment, it does not own any logic. |
| Default-warehouse seed | Database / Storage | — | A frozen Alembic migration (`op.bulk_insert`), not application code — matches migration 0001's `DEMO_PRODUCT_ID` seed pattern exactly. |

## Standard Stack

No new packages. This phase reuses the exact stack already pinned in `./CLAUDE.md` and `pyproject.toml`:

| Library | Version (from `pyproject.toml`, `[VERIFIED: codebase]`) | Purpose in this phase |
|---------|------|------------------------|
| FastAPI | 0.139.* | New `app/routes/warehouses.py` router |
| SQLAlchemy | 2.0.* | New `Warehouse` model in `app/models.py` |
| Alembic | 1.18.* | New migration `alembic/versions/0007_warehouses.py` |
| Jinja2 | 3.1.* | New `pages/warehouses.html` + `partials/warehouse_rows.html` |
| htmx | vendored `app/static/htmx.min.js` | Inline add/edit/delete/restore against the rows partial |
| pytest / httpx | 9.1.* / 0.28.* | New `tests/test_warehouses.py` |

**Installation:** None required — `uv sync` already installs everything this phase needs.

## Package Legitimacy Audit

Not applicable — this phase introduces no new third-party package. No `npm view` / `pip index versions` / registry check is needed.

## Architecture Patterns

### System Architecture Diagram

```
Browser (htmx)
   |  GET /warehouses                  -> full page (pages/warehouses.html)
   |  POST /warehouses                 -> add row
   |  POST /warehouses/{id}            -> edit row
   |  POST /warehouses/{id}/delete     -> soft-delete (may return warn-block instead)
   |  POST /warehouses/{id}/restore    -> restore
   v
app/routes/warehouses.py  (thin: parse Form(), call service, choose template)
   |
   v
app/services/warehouses.py
   |  - list_warehouses(session)              -> all rows, active+deleted, sorted
   |  - add_warehouse(session, ...)            -> (Warehouse|None, errors)
   |  - update_warehouse(session, id, ...)     -> (Warehouse|None, errors)
   |  - soft_delete_warehouse(session, id, confirm=False) -> (deleted: bool, warning: dict)
   |  - restore_warehouse(session, id)         -> None (idempotent)
   v
SQLAlchemy Session  ->  warehouses table (SQLite, WAL mode)
   ^
   |  seeded once at migration time
alembic/versions/0007_warehouses.py  (op.create_table + op.bulk_insert, frozen values only)
```

Every route returns EITHER the full page (`GET /warehouses`) OR `partials/warehouse_rows.html` (every POST) — there is no separate `/warehouses/{id}/edit` page to `HX-Redirect` to, unlike `Product`. This is the key structural difference from the Products delete/restore precedent and the most likely source of a copy-paste bug if `app/routes/products.py` is used as a template without adjustment (see Common Pitfalls #1).

### Recommended Project Structure
```
app/
├── models.py                          # + class Warehouse
├── routes/
│   └── warehouses.py                  # new: page + add/edit/delete/restore routes
├── services/
│   └── warehouses.py                  # new: CRUD + warn-but-allow last-warehouse guard
├── templates/
│   ├── pages/warehouses.html          # new: page shell + inline add form + include rows
│   └── partials/warehouse_rows.html   # new: shared swap target for every POST
alembic/versions/
└── 0007_warehouses.py                 # new: create_table + bulk_insert seed
tests/
└── test_warehouses.py                 # new: service + web + migration tests
```

### Pattern 1: Dictionary-style single-page inline CRUD
**What:** One page with an inline add form and an editable rows table; every POST swaps `#warehouse-rows` via `hx-target` + `hx-swap="outerHTML"`. No separate `/new` or `/{id}/edit` pages.
**When to use:** Small, rarely-changing reference-style entities (D-08/D-10) — exactly this phase.
**Example (from the actual codebase, `app/routes/dictionary.py`):**
```python
# Source: app/routes/dictionary.py (existing code, verbatim pattern to mirror)
@router.post("/dictionary")
def dictionary_add(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    entry, errors = add_entry(session, code=code, name=name)
    context = {
        "entries": list_entries(session),
        "errors": errors,
        "form": {"code": code, "name": name} if errors else {},
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_rows.html",
        context,
        status_code=422 if errors else 200,
    )
```
For warehouses, `entries` becomes `warehouses`, `dictionary_rows.html` becomes `warehouse_rows.html`, and the same shape is reused for add, edit, delete, and restore — every one of those four routes re-renders the rows partial, none of them redirect.

### Pattern 2: Product soft-delete/restore convention — adapted, NOT copied verbatim
**What:** `deleted_at` nullable column; delete sets it, restore clears it; both are idempotent no-ops if already in that state.
**When to use:** Every soft-deletable entity in this app (D-05/D-09).
**Example (service layer, directly reusable shape from `app/services/catalog.py`):**
```python
# Source: app/services/catalog.py (existing code — same pattern for Warehouse)
def soft_delete_product(session: Session, product_id: str) -> None:
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return
    product.deleted_at = utcnow_iso()
    session.commit()


def restore_product(session: Session, product_id: str) -> None:
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is None:
        return
    product.deleted_at = None
    session.commit()
```
**What must change for warehouses:** the ROUTE-level response. `app/routes/products.py` answers delete/restore with `Response(status_code=200, headers={"HX-Redirect": "/products"})` because Products has a separate `/products/{id}/edit` page to navigate away from/to. Warehouses has no such page (D-08) — the delete/restore routes must instead re-render `partials/warehouse_rows.html` in place, exactly like Dictionary's add/edit routes (Pattern 1). Do not import the `HX-Redirect` response shape from `products.py`.

### Pattern 3: Warn-but-allow last-active-warehouse guard (new synthesis, no exact precedent)
**What:** Before soft-deleting a warehouse, check whether it is the last remaining active one. If so and the caller has not confirmed, do NOT write; return a warning instead. A second click with `confirm=1` performs the delete regardless.
**When to use:** Exactly the D-06/D-07 guard on `soft_delete_warehouse`.
**Source pattern this is adapted from** (`app/services/sales.py::register_sale`, confirmed `[VERIFIED: codebase]`):
```python
# Source: app/services/sales.py (existing warn-but-allow shape, confirm flag)
if confirm != "1":
    below_minimum = [ ... ]   # read-only check, computed BEFORE any write
    if oversold or below_minimum:
        return result, {}     # ZERO writes, caller re-POSTs with confirm=1
# ... only past this point does the function stage/commit any write
```
**Adapted for a single-row delete** (recommended shape — not existing code, HIGH confidence since it's a direct, minimal transposition of the verified pattern above):
```python
def soft_delete_warehouse(
    session: Session, warehouse_id: str, *, confirm: bool = False
) -> tuple[bool, dict]:
    """Soft-delete one warehouse; warn-but-allow if it is the last active one.

    Returns (deleted, warning):
      (True, {})                    -> deleted (not last-active, or confirm=True)
      (False, {})                   -> unknown id or already deleted (no-op)
      (False, {"warehouse": w})     -> blocked pending confirm=1 re-POST
    """
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is not None:
        return False, {}

    if not confirm:
        active_count = session.scalar(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.deleted_at.is_(None))
        )
        if active_count <= 1:
            return False, {"warehouse": warehouse}

    warehouse.deleted_at = utcnow_iso()
    session.commit()
    return True, {}
```
The route passes `confirm=="1"` through (Form field, same convention as `app/routes/sales.py`'s `confirm: str = Form("")`), and on a blocked delete re-renders `warehouse_rows.html` with a `warning_id` context flag so ONLY that row branches into an inline warning block (mirrors `dictionary_rows.html`'s existing `error_entry_id` per-row branching — same file, same technique, different flag name). The warning button re-POSTs the SAME delete URL with `hx-vals='{"confirm": "1"}'`, targeting `#warehouse-rows` — never a full-page redirect (see Pattern 2).

### Anti-Patterns to Avoid
- **Copying `HX-Redirect` from `products.py` verbatim:** Warehouses has no `/edit` page to redirect to; every write response is a rows-partial re-render (Pattern 1/2).
- **Filtering `deleted_at IS NULL` in the page's own list query:** D-09 explicitly requires deleted warehouses to STAY VISIBLE in the same list (grayed out + Restore button) — unlike every other soft-deletable entity in this app. `list_warehouses` must NOT filter by `deleted_at`; filtering is only relevant for a FUTURE active-only picker (Phase 9), which does not exist yet.
- **Adding a `Product.warehouse_id` column "to be safe":** explicitly forbidden by D-02 — it models a false 1:1 relationship that Phase 9 immediately breaks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UUID primary keys | Custom id generator | `app.core.new_id()` | Already the sanctioned single source (D-05/D-06 convention doc in `app/core.py`), used by every model. |
| Timestamps | `datetime.now()` / naive datetimes | `app.core.utcnow_iso()` | UTC ISO-8601 text, lexicographically sortable, matches every other table. |
| Migration seed rows | Hand-written INSERT via raw SQL string interpolation | `op.bulk_insert` with a `sa.table()`/`sa.column()` shim, exactly as migration 0001 does for `DEMO_PRODUCT_ID` | Portable, typed, and matches the one existing precedent for a migration-time seed row. |
| Warn-but-allow confirm gating | A generic "confirmation framework" / middleware | The existing `confirm` Form-field + read-only-check-before-write shape from `sales.py` | Consistency: this app already has TWO instances of this exact shape (oversell, min-price); a third ad-hoc mechanism would fragment the UX language the user explicitly wants kept consistent (D-06). |

**Key insight:** Every technical building block this phase needs already exists in this codebase in a directly copyable form. The only design work is *composition* (which existing pattern applies to which route) — not invention of new mechanics.

## Common Pitfalls

### Pitfall 1: Copying the Products delete/restore route's `HX-Redirect` response
**What goes wrong:** Delete/restore appears to "work" (200 OK) but the browser navigates to a nonexistent flow, or the rows table never updates because the response was a redirect header instead of the rows partial.
**Why it happens:** `app/routes/products.py` is the only existing delete/restore precedent, and its response shape (`HX-Redirect` to a list page from a separate edit page) doesn't fit a single-page layout.
**How to avoid:** Model the delete/restore *route bodies* on Dictionary's add/edit routes (re-render `partials/warehouse_rows.html`), and only the *button markup* (`hx-confirm` text, `class="danger"`/`class="secondary"`) on Products' `product_form.html`.
**Warning signs:** A test asserting `response.headers["HX-Redirect"]` passes but a test asserting the rows partial reflects the change fails.

### Pitfall 2: Filtering out soft-deleted warehouses in the management page's own query
**What goes wrong:** A soft-deleted warehouse silently disappears from `/warehouses` with no way to restore it except a URL that doesn't exist yet — directly violating success criterion 3's spirit (D-09 explicitly rejects this behavior for THIS entity).
**Why it happens:** Every other soft-deletable query in the codebase (`Product`, and everywhere `deleted_at.is_(None)` appears) filters deleted rows out by convention — muscle-memory copy-paste would apply the same filter here.
**How to avoid:** `list_warehouses(session)` returns ALL rows (active + deleted); only the template distinguishes them visually (grayed out row + "Восстановить" button, per D-09).
**Warning signs:** A soft-deleted warehouse used in a test disappears from the `/warehouses` page response entirely instead of showing grayed-out with a restore button.

### Pitfall 3: Treating "no selectable option elsewhere" (success criterion 3) as something to implement in Phase 8
**What goes wrong:** Time spent building an "active warehouses" picker/dropdown helper that has no caller yet.
**Why it happens:** Success criterion 3 reads like it needs an active-filtered query used by some UI element.
**How to avoid:** Confirmed by grep — nothing in `app/` references `Warehouse` yet (Phase 8 is the first phase to introduce it), so there is currently no "elsewhere" for a deleted warehouse to wrongly appear in. This criterion is satisfied by the CONVENTION being correct and ready for Phase 9 to consume (e.g., expose a trivial `active_warehouses(session)` helper filtering `deleted_at.is_(None)`, even though nothing calls it yet) — not by building a picker now.
**Warning signs:** Scope creep into building dropdown/select UI for a field (`Batch.warehouse_id`) that doesn't exist until Phase 9.

### Pitfall 4: Forgetting the migration is a FROZEN, app-code-independent file (WR-06 project convention)
**What goes wrong:** `alembic/versions/0007_warehouses.py` imports `app.core.new_id` / `app.models.Warehouse` to build the seed row — looks convenient, but breaks replayability if those app modules ever change shape, and violates the project's own stated immutability rule (documented in every existing migration's docstring, e.g. 0001, 0002, 0006).
**Why it happens:** It is genuinely more convenient to reuse the real UUID generator than hand-write a UUID literal.
**How to avoid:** Hard-code a frozen UUID literal (e.g. following the `DEMO_PRODUCT_ID = "00000000-0000-4000-8000-000000000001"` style already in migration 0001) and a frozen ISO timestamp string, exactly as every existing migration does. Use `sa.table()`/`sa.column()` + `op.bulk_insert`, never an ORM model import.
**Warning signs:** `import app.models` or `import app.core` anywhere inside `alembic/versions/0007_warehouses.py`.

### Pitfall 5: Not documenting the seeded default warehouse's stable identity for Phase 9
**What goes wrong:** Phase 9's migration (which must point its "legacy batch" at this same default warehouse, per D-03) has no reliable way to look the row up — guessing at a name string is fragile if it's not been pinned as a frozen constant.
**Why it happens:** D-03 phrases this as a soft expectation ("a stable name or documented lookup"), which is easy to under-specify.
**How to avoid:** Pick one frozen UUID (e.g. `DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"`, next available slot after the existing `...0001` demo-product convention) and one frozen RU name (e.g. `"Склад по умолчанию"`) inside `0007_warehouses.py`'s `upgrade()`, and record both explicitly in this phase's PLAN.md/VERIFICATION.md so Phase 9's planner can copy them verbatim into its own frozen migration — Phase 9 migrations must NOT import Phase 8's migration module either (same WR-06 rule applies across phases).
**Warning signs:** Phase 9 research/planning has to re-derive or guess the default warehouse's id/name instead of finding it documented.

## Code Examples

### Model (add to `app/models.py`)
```python
# Source: pattern verified against Product/Customer in app/models.py
class Warehouse(Base):
    """Physical stock location (WH-01): standalone table, no FK wiring yet.

    D-01/D-02: Batch.warehouse_id (Phase 9) is the real stock link; this
    table exists on its own in Phase 8, seeded with one default row so
    Phase 9's legacy-batch migration has something stable to point at (D-03).
    """

    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
    # D-05: soft delete only; no hard deletes (matches Product convention).
    deleted_at: Mapped[str | None] = mapped_column(String(32))
```

### Migration (`alembic/versions/0007_warehouses.py`)
```python
# Source: pattern verified against alembic/versions/0001_initial_schema.py
"""warehouses (WH-01)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-11

Creates the standalone `warehouses` table (D-01: no FK from products/
operations yet — Batch.warehouse_id is Phase 9's job) and seeds exactly
one default row so success criterion 2 is satisfied conceptually: nothing
is lost because nothing yet references warehouses to lose (D-02).

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# D-03: frozen, documented identity Phase 9's legacy-batch migration can
# rely on without importing this module.
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
_SEED_CREATED_AT = "2026-07-11T00:00:00+00:00"


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
    )

    warehouses = sa.table(
        "warehouses",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("address", sa.String),
        sa.column("created_at", sa.String),
        sa.column("updated_at", sa.String),
    )
    op.bulk_insert(
        warehouses,
        [
            {
                "id": DEFAULT_WAREHOUSE_ID,
                "name": "Склад по умолчанию",
                "address": None,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("warehouses")
```

### Service (`app/services/warehouses.py`) — list/add/update, mirroring `dictionary.py`
```python
# Source: pattern verified against app/services/dictionary.py
def list_warehouses(session: Session) -> list[Warehouse]:
    """ALL rows, active + deleted (D-09) — sorted active-first, then by name.

    Cardinality is small (D-10: "a handful"), so sorting in Python after
    fetch avoids relying on ORDER BY over a boolean-ish expression.
    """
    rows = list(session.scalars(select(Warehouse)))
    return sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))


def add_warehouse(
    session: Session, *, name: str, address: str
) -> tuple[Warehouse | None, dict[str, str]]:
    name = name.strip()
    address = address.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Укажите название склада."
    if errors:
        return None, errors
    warehouse = Warehouse(id=new_id(), name=name, address=address or None)
    session.add(warehouse)
    session.commit()
    return warehouse, {}
```

### Route (`app/routes/warehouses.py`) — delete with warn-but-allow
```python
# Source: pattern verified against app/routes/dictionary.py + app/routes/sales.py
@router.post("/warehouses/{warehouse_id}/delete")
def warehouse_delete(
    request: Request,
    warehouse_id: str,
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    deleted, warning = soft_delete_warehouse(
        session, warehouse_id, confirm=confirm == "1"
    )
    context = {
        "warehouses": list_warehouses(session),
        "errors": {},
        "form": {},
        "warning_id": warehouse_id if warning else None,
    }
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
```

### Template row-level branching (`partials/warehouse_rows.html`) — inline warning
```html
{# Source: pattern verified against partials/dictionary_rows.html's
   error_entry_id branching + partials/sale_price_warning.html's confirm=1
   button. #}
{% for w in warehouses %}
<tr{% if w.deleted_at %} class="muted"{% endif %}>
  <td>{{ w.name }}</td>
  <td>
    {% if w.deleted_at %}
    <button type="button" class="secondary"
            hx-post="/warehouses/{{ w.id }}/restore"
            hx-target="#warehouse-rows" hx-swap="outerHTML">Восстановить</button>
    {% else %}
    <button type="button" class="danger"
            hx-post="/warehouses/{{ w.id }}/delete"
            hx-confirm="Удалить склад «{{ w.name }}»?"
            hx-target="#warehouse-rows" hx-swap="outerHTML">Удалить</button>
    {% endif %}
  </td>
</tr>
{% if warning_id == w.id %}
<tr><td colspan="2">
  <div class="error-block">
    <p>Это последний активный склад. Удалить всё равно?</p>
    <button type="button" class="danger"
            hx-post="/warehouses/{{ w.id }}/delete" hx-vals='{"confirm": "1"}'
            hx-target="#warehouse-rows" hx-swap="outerHTML">Удалить всё равно</button>
  </div>
</td></tr>
{% endif %}
{% endfor %}
```

### Migration test (`tests/test_warehouses.py`) — verifies the seed row
```python
# Source: pattern verified against tests/test_catalog.py's
# test_migration_0006_adds_min_sale_cents_column
def test_migration_0007_creates_and_seeds_default_warehouse(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0006")
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(warehouses)")}
        assert {"id", "name", "address", "created_at", "updated_at", "deleted_at"} <= cols

        rows = conn.execute("SELECT name, deleted_at FROM warehouses").fetchall()
        assert rows == [("Склад по умолчанию", None)]
```

## State of the Art

Not applicable — no external technology choice is being made or revisited in this phase; every pattern used here already ships in the current codebase (verified by direct file reads, not training-data recall).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact frozen `DEFAULT_WAREHOUSE_ID` value (`...000010`) and RU seed name (`"Склад по умолчанию"`) are illustrative — no existing project document pins a specific UUID/name for this row. | Code Examples > Migration; Pitfall 5 | Low — any concrete stable value works as long as it's frozen and documented for Phase 9 to consume; only a problem if the planner leaves it undocumented for Phase 9 to guess at. |

**All other claims in this research were verified directly against the repository's source files** (models, routes, services, templates, migrations, tests, config) via Read/Grep in this session — no web search was performed or needed, since the phase introduces no new package, API, or external service.

## Open Questions

1. **Column name: `address` vs `note`?**
   - What we know: D-04 leaves this to the planner; both read naturally for a physical warehouse.
   - What's unclear: no strong signal either way in CONTEXT.md or existing precedent (Customer's optional fields are `surname`/`consultant_number`, domain-specific, not directly analogous).
   - Recommendation: use `address` (used in the Code Examples above) — slightly more specific to "a physical warehouse" than the generic `note`, but this is a one-line rename if the planner disagrees.

2. **Should Phase 8 expose an `active_warehouses(session)` helper now, even though nothing calls it yet?**
   - What we know: D-07 explicitly says Phase 9 must defensively handle "zero active warehouses" on its own; D-01 says no FK/wiring happens in Phase 8.
   - What's unclear: whether pre-building this trivial helper in Phase 8 is in-scope "future-proofing" or unnecessary speculative code for a phase whose success criteria don't require it.
   - Recommendation: skip it in Phase 8 — `Warehouse.deleted_at.is_(None)` is a one-line filter Phase 9 can write directly when it needs it; adding an unused helper function now has no test to justify its existence and risks going stale before Phase 9 defines its actual query shape.

3. **Exact frozen seed UUID/name for the default warehouse (D-03's cross-phase contract).**
   - What we know: it must be frozen inside `0007_warehouses.py` and documented for Phase 9.
   - What's unclear: no user-specified value exists yet.
   - Recommendation: the planner picks any concrete frozen value (see Assumptions Log A1) and records it plainly in this phase's PLAN.md so Phase 9's research/planning can grep for it directly rather than re-deriving it.

## Environment Availability

Skipped — this phase has no external dependencies beyond the project's own already-installed stack (FastAPI/SQLAlchemy/Alembic/Jinja2/htmx/pytest, all confirmed present via `pyproject.toml` and a passing `uv run pytest -q` baseline of 247 tests in this session).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (`[VERIFIED: codebase]` pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Quick run command | `uv run pytest -q -k warehouse` |
| Full suite command | `uv run pytest -q` (baseline: 247 passed, ~32s, verified this session) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WH-01 | Create warehouse (name required, address optional) | unit | `pytest tests/test_warehouses.py::test_add_warehouse_creates_row -x` | ❌ Wave 0 |
| WH-01 | Edit warehouse in place | unit | `pytest tests/test_warehouses.py::test_update_warehouse_edits_fields -x` | ❌ Wave 0 |
| WH-01 | Soft-delete + restore round trip | unit | `pytest tests/test_warehouses.py::test_soft_delete_and_restore_roundtrip -x` | ❌ Wave 0 |
| WH-01 | Deleting the LAST active warehouse warns, does not write, until confirm=1 | unit | `pytest tests/test_warehouses.py::test_delete_last_active_warehouse_warns_then_allows -x` | ❌ Wave 0 |
| WH-01 | Deleted warehouse stays visible in `/warehouses` list (grayed out + restore button), not hidden (D-09) | web | `pytest tests/test_warehouses.py::test_web_deleted_warehouse_stays_visible_with_restore -x` | ❌ Wave 0 |
| WH-01 (success criterion 2) | Migration seeds exactly one default warehouse row on upgrade, existing data untouched | migration | `pytest tests/test_warehouses.py::test_migration_0007_creates_and_seeds_default_warehouse -x` | ❌ Wave 0 |
| WH-01 | Nav gains a `/warehouses` link | web | `pytest tests/test_warehouses.py::test_web_nav_has_warehouses_link -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -q -k warehouse`
- **Per wave merge:** `uv run pytest -q` (full 247+ suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_warehouses.py` — new file, covers WH-01 (all rows above); no existing test file to extend.
- [ ] No new fixtures needed — `tests/conftest.py`'s `session`/`client`/`engine` fixtures are model-agnostic (schema created via `Base.metadata.create_all`, which auto-includes the new `Warehouse` model once it's added to `app/models.py`).
- [ ] Framework install: none — pytest/httpx are already dev dependencies.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Project has no auth in v1 (single local operator, per `./CLAUDE.md` constraints) — unchanged by this phase. |
| V3 Session Management | No | No sessions/cookies exist or are introduced. |
| V4 Access Control | No | No roles/permissions in v1. |
| V5 Input Validation | Yes | Required `name` field validated server-side (non-blank after strip, mirroring `Dictionary`/`Customer` patterns); Jinja2 autoescaping handles output encoding for the free-text `name`/`address` fields exactly as it already does for `Product.name`/`Customer.name` (T-4-01 convention: untrusted stored input, autoescape only, never `|safe`). |
| V6 Cryptography | No | No secrets/crypto touched by this phase. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Stored XSS via warehouse name/address rendered unescaped | Tampering / Information Disclosure | Jinja2 autoescaping (default, already relied on everywhere else in this codebase) — never wrap `w.name`/`w.address` in `|safe`. |
| SQL injection via raw string concatenation | Tampering | N/A — this phase uses only SQLAlchemy ORM `select()`/`session.get()`, no raw SQL string interpolation with user input (matches every existing service module). |
| CSV-formula injection | Tampering | N/A this phase — warehouse fields are not exported (EXP-V2-01 deferred to v2; existing `app/services/export.py`'s BOM/escape logic is unaffected and untouched). |

## Sources

### Primary (HIGH confidence, `[VERIFIED: codebase]`)
- `app/models.py` — `Product`, `Dictionary`, `Customer` model conventions (read in full this session).
- `app/routes/dictionary.py`, `app/services/dictionary.py`, `app/templates/pages/dictionary.html`, `app/templates/partials/dictionary_rows.html` — single-page inline CRUD precedent.
- `app/routes/products.py`, `app/services/catalog.py` (soft_delete_product/restore_product) — soft-delete/restore convention.
- `app/services/sales.py`, `app/templates/partials/sale_oversell.html`, `app/templates/partials/sale_price_warning.html` — warn-but-allow confirm=1 pattern.
- `alembic/versions/0001_initial_schema.py`, `0002_catalog_dictionary.py`, `0006_product_min_sale_price.py` — migration conventions (bulk_insert seed, native ADD COLUMN/create_table, frozen-values rule WR-06).
- `alembic/env.py` — `render_as_batch=True` confirmed.
- `tests/conftest.py`, `tests/test_dictionary.py`, `tests/test_catalog.py` (including `test_migration_0002_fresh_db_and_backfill`, `test_migration_0006_adds_min_sale_cents_column`, `test_soft_delete_and_restore_roundtrip`, `test_web_delete_hides_and_restore_returns`) — test conventions for service/web/migration layers.
- `app/main.py`, `app/routes/__init__.py` — router registration and shared `templates` instance.
- `app/static/style.css` — confirmed `.danger`, `.secondary`, `.error-block`, `.muted`, `.empty-state`, `.form-actions` classes already exist, no new CSS needed.
- `pyproject.toml`, `alembic.ini` — dependency/version pins and pytest config.
- `uv run pytest -q` — executed this session, 247 passed, confirming the baseline is green before this phase starts.
- `.planning/phases/08-warehouses/08-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json` — phase scope, requirement text, and workflow settings (`nyquist_validation: true`, `security_enforcement: true`, `security_asvs_level: 1`).

### Secondary (MEDIUM confidence)
None — no external documentation was needed for this phase.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; every version confirmed against `pyproject.toml` directly.
- Architecture: HIGH — Patterns 1 and 2 are direct, verified codebase precedents; Pattern 3 (last-warehouse guard) is a synthesis of two verified precedents (sales.py confirm-gate + dictionary_rows.html row-level branching), not itself pre-existing code, so flagged as "recommended" rather than "existing."
- Pitfalls: HIGH — all five pitfalls are grounded in specific, named files/lines read this session, not general knowledge.

**Research date:** 2026-07-11
**Valid until:** No expiry pressure — this research is tied to the current state of the local codebase, not to any external/versioned dependency; re-check only if the codebase's Dictionary/Product/sales.py patterns change before this phase is planned.
