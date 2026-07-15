# Phase 15: Cash Ledger Foundation - Pattern Map

**Mapped:** 2026-07-14
**Files analyzed:** 13 (7 new, 6 modified)
**Analogs found:** 13 / 13 (all analogs verified in-repo by direct read)

> Every symbol/line cited below was confirmed by reading the source file. This phase is a *clone of a proven shape* (`Operation`/`ledger.py`/append-only triggers) into a parallel `cash_movements` ledger — no new pattern is invented.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/models.py` → `CashMovement` + `CASH_CATEGORIES` | model | event-log (append-only) | `Operation` class + `WRITEOFF_REASONS` (`app/models.py:240-275`, `:49-56`) | exact |
| `app/services/finance.py` (NEW) | service | event-driven / CRUD-append + aggregate read | `app/services/ledger.py` (`next_seq`, `record_operation`, `compute_stock`) | exact |
| `alembic/versions/0013_cash_movements.py` (NEW) | migration | schema DDL | `alembic/versions/0001_initial_schema.py` (create_table + trigger loop) | exact |
| `app/db.py` → `APPEND_ONLY_TRIGGERS` | config | DDL constant | same file, `operations_no_update`/`_no_delete` (`app/db.py:22-33`) | exact (extend in place) |
| `app/services/sales.py` §`register_sale` | service | request-response (write) | self — insert one call at `sales.py:266-269` | exact (additive edit) |
| `app/services/returns.py` §`register_return` | service | request-response (write) | self — flip commit at `returns.py:151-162` | exact (additive edit) |
| `app/routes/finance.py` (NEW) | route | request-response (read) | `app/routes/writeoffs.py` §`writeoff_page` (`:25-33`) | exact |
| `app/routes/mobile_finance.py` (NEW) | route | request-response (read) | `app/routes/mobile_reports.py` (`:17-23`, `/m/` prefix) | exact |
| `app/templates/pages/finance.html` (NEW) | template | render | any `pages/*.html` + `cents` filter usage | role-match |
| `app/templates/mobile_pages/finance.html` (NEW) | template | render | `mobile_pages/reports_expiry.html` | role-match |
| `app/templates/base.html` (nav) | template | render | self — nav links `:33-38` | exact (additive edit) |
| `app/templates/mobile_pages/home.html` (tile) | template | render | self — tile grid `:5-14` | exact (additive edit) |
| `app/main.py` (router registration) | config | wiring | self — `include_router` list `:53-79` | exact (additive edit) |

Test files (`tests/test_finance.py` NEW, plus assertions added to `tests/test_sales.py` / `tests/test_returns.py`) mirror `tests/test_ledger.py` and are planned per RESEARCH.md §Wave 0 Gaps — not re-detailed here.

## Pattern Assignments

### `app/models.py` → `CashMovement` (model, append-only event-log)

**Analog:** `Operation` class, `app/models.py:240-275`. Drop the stock-specific columns (`product_id` NOT-NULL FK, `qty_delta`, `unit_cost_cents`, `batch_id`); keep the sync-ready audit shape verbatim.

**Shape to copy** (`app/models.py:243-275`, verified):
```python
class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ...
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_operations_sale_id_sales"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)          # per-device
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    synced_at: Mapped[str | None] = mapped_column(String(32))          # v2 sync cursor
```
- FK `name=` is REQUIRED and follows the precedent — new table's FK becomes `fk_cash_movements_sale_id_sales` (the `NAMING_CONVENTION` at `app/models.py:24-30` auto-names PK/UQ/IX; only the FK carries an explicit `name=`, exactly as `Operation.sale_id` at `:259-261`).
- `amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)` — SIGNED, Integer cents (never Float; frozen conventions test `test_ledger.py:110-120` asserts all `*_cents` are Integer).
- Sale header FK target `sales.id` exists (`Sale`, `app/models.py:299-315`).

**Category dict to copy** — mirror `WRITEOFF_REASONS` (`app/models.py:49-56`), placed near the other label dicts:
```python
WRITEOFF_REASONS = {          # existing precedent, models.py:49
    "damaged": "Брак", ...
}
```
New: `CASH_CATEGORIES = {"sale": "Продажа", "return": "Возврат"}` (A1 — distinct `"return"` key recommended; Claude's discretion per CONTEXT).

---

### `app/services/finance.py` (service, append-write + aggregate read) — NEW

**Analog:** `app/services/ledger.py` — the SINGLE-write-path triad. Clone `next_seq`, `record_operation`, `compute_stock`; drop the product/batch guards (cash has neither).

**`next_seq` to copy** (`app/services/ledger.py:23-33`, verified):
```python
def next_seq(session: Session, device_id: str) -> int:
    current = session.scalar(
        select(func.max(Operation.seq)).where(Operation.device_id == device_id)
    )
    return (current or 0) + 1
```
→ swap `Operation` for `CashMovement`.

**`record_operation` write core to copy** (`ledger.py:104-129`, verified). Keep the type allow-list guard (`:74-75`) and audit stamping; DELETE the `Product`/`Batch` guards (`:79-102`) and the cached-quantity increment (`:122-126`) — cash has no projection to update:
```python
    if type_ not in OPERATION_TYPES:            # → if category not in CASH_CATEGORIES: raise ValueError
        raise ValueError(...)
    op = Operation(
        id=new_id(), type=type_, ...,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(op)
    if commit:
        session.commit()
    return op
```
- Imports mirror `ledger.py:8-13`: `from sqlalchemy import func, select` / `from app.config import settings` / `from app.core import new_id, utcnow_iso` / `from app.models import CASH_CATEGORIES, CashMovement`. (Verified: `settings.device_id`/`settings.operator_name` used at `ledger.py:114-117`; `new_id`/`utcnow_iso` at `app/core.py`.)
- `commit: bool = True` flag is the WR-03 staging contract — callers pass `commit=False` and issue one trailing `session.commit()`.

**`compute_balance` to copy from `compute_stock`** (`ledger.py:132-138`, verified):
```python
def compute_stock(session, product_id):
    return session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(...)
    )
```
→ `compute_balance(session)` = `select(func.coalesce(func.sum(CashMovement.amount_cents), 0))` (no WHERE — whole-till live SUM; no cache, D-00b).

---

### `app/services/sales.py` §`register_sale` (service, additive edit)

**Analog:** self. The insertion point is fully verified (`app/services/sales.py:245-272`):
```python
    total_cents = 0
    try:
        for line in resolved:
            ...
            record_operation(session, type_="sale", ..., commit=False)  # :255-265
            total_cents += qty * price_cents                            # :266
        # >>> NEW: stage the credit here, same transaction, same total_cents
        session.commit()                                                # :269 unchanged
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"basket": SAVE_ROLLBACK}
```
- Insert `finance.record_cash_movement(session, category="sale", amount_cents=total_cents, sale_id=header.id, commit=False)` between `:266` and `:269`.
- `header.id` is the `Sale` PK already in scope (passed as `sale_id=header.id` at `:262`).
- Existing `except (IntegrityError, ValueError): session.rollback()` (`:270-272`) already covers the new call — a rolled-back sale writes ZERO cash rows.
- Empty/zero basket cannot reach here (rejected upstream; per RESEARCH `sales.py:108`/`:129`).

---

### `app/services/returns.py` §`register_return` (service, additive edit) — commit-flag flip

**Analog:** self. Verified (`app/services/returns.py:147-170`). Current code commits the return op on its own (`commit=True` at `:161`); flip to staged so cash + stock commit atomically (Pitfall 2):
```python
    try:
        batch_id = _resolve_or_create_return_batch_id(session, origin)   # :150
        op = record_operation(
            session, type_="return", product_id=origin.product_id, qty_delta=qty,
            unit_price_cents=origin.unit_price_cents,   # :156 D-07 frozen copy
            unit_cost_cents=origin.unit_cost_cents,     # :157
            sale_id=origin.sale_id, batch_id=batch_id,
            payload={"origin_op_id": origin.id},
            commit=True,                                # :161  → CHANGE to commit=False
        )
        # >>> NEW: debit computed FRESH (D-00d / Pitfall 3), never matched to the credit row
        debit = qty * (origin.unit_price_cents or 0)
        if debit:
            finance.record_cash_movement(session, category="return",
                amount_cents=-debit, sale_id=origin.sale_id, commit=False)
        session.commit()                                # >>> NEW single close
    except ValueError:                                  # :163 existing
        session.rollback()
        return None, {"form": PRODUCT_UNAVAILABLE_ERROR}
    except IntegrityError:                              # :168 existing
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}
```
- `qty` is validated positive at `:135-137`; capped by `returnable_qty` at `:141-145` before any write.
- `(origin.unit_price_cents or 0)` guard: defensive against a NULL-priced legacy origin.
- Both existing `except` arms already `session.rollback()` — atomicity preserved.
- ONE `register_return` call = one origin line = one debit row (D-03).

---

### `app/routes/finance.py` (route, request-response read) — NEW

**Analog:** `app/routes/writeoffs.py` §`writeoff_page` (`:25-33`, verified) for the desktop GET-page shape; imports pattern (`:1-17`):
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db import get_session
from app.routes import templates          # shared env (routes/__init__.py:9)
router = APIRouter()

@router.get("/writeoff")
def writeoff_page(request, session: Session = Depends(get_session)):
    context = {...}
    return templates.TemplateResponse(request, "pages/writeoff_form.html", context)
```
→ new: `@router.get("/finance")` returning `pages/finance.html` with `{"balance_cents": compute_balance(session)}`. Import `from app.services.finance import compute_balance`.

---

### `app/routes/mobile_finance.py` (route, request-response read) — NEW

**Analog:** `app/routes/mobile_reports.py` (`:17-23`, verified) — the `/m/` prefix convention:
```python
@router.get("/m/reports/expiry")
def mobile_reports_expiry(request, session: Session = Depends(get_session)):
    context = {...}
    return templates.TemplateResponse(request, "mobile_pages/reports_expiry.html", context)
```
→ new: `@router.get("/m/finance")` returning `mobile_pages/finance.html`, same `compute_balance(session)` context.

---

### Templates (render)

**`pages/finance.html` / `mobile_pages/finance.html`** — mirror `mobile_pages/reports_expiry.html` extends structure; render money via the registered `cents` filter (`app/routes/__init__.py:12` verified — `templates.env.filters["cents"] = format_cents`):
```html
<h1>Баланс кассы</h1>                    <!-- D-04 heading, verbatim -->
<p class="cash-balance">{{ balance_cents | cents }}</p>
```
`format_cents` (`app/core.py:49-53`, verified): `0 → "0,00"`, `12500 → "125,00"`, sign-aware, NO currency glyph (D-04). Planner may share a `partials/cash_balance.html` fragment between the two pages (Open Q2 — low stakes).

**`base.html` nav** (desktop) — add after Отчёты/Экспорт (`app/templates/base.html:37-38`, verified pattern):
```html
<a href="/finance"{% if request.url.path.startswith("/finance") %} class="active"{% endif %}>Финансы</a>
```

**`mobile_pages/home.html` tile** — add to the grid (`:5-14`, verified `<a class="mobile-tile">` pattern):
```html
<a class="mobile-tile" href="/m/finance">Финансы</a>
```

---

## Shared Patterns

### Append-only immutability (DB triggers)
**Source:** `app/db.py:22-33` `APPEND_ONLY_TRIGGERS` (LIVE, used by test fixtures) + `alembic/versions/0001_initial_schema.py` (frozen copy).
**Apply to:** `cash_movements` — add TWO triggers to BOTH places (WR-06: migrations never import app code, so duplicate the DDL).
```python
APPEND_ONLY_TRIGGERS: tuple[str, str] = (          # → retype to tuple[str, ...]
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END""",
    """CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
       BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END""",
)
```
→ append `cash_movements_no_update` / `cash_movements_no_delete`.
**CRITICAL (Pitfall 1):** `tests/conftest.py:24-27` loops over `APPEND_ONLY_TRIGGERS` to install triggers on the fixture DB (schema built via `Base.metadata.create_all`, NOT Alembic). If the cash triggers live only in migration 0013, cash append-only tests silently pass. The constant's type annotation `tuple[str, str]` (`db.py:22`) must widen to `tuple[str, ...]`.

### Audit-field stamping
**Source:** `app/services/ledger.py:114-117` — `device_id=settings.device_id`, `seq=next_seq(...)`, `created_at=utcnow_iso()`, `created_by=settings.operator_name`.
**Apply to:** every `CashMovement` insert (only through `finance.record_cash_movement`).

### Money as Integer cents + `cents` display filter
**Source:** `app/core.py:49-53` `format_cents`; registered filter `app/routes/__init__.py:12`.
**Apply to:** `CashMovement.amount_cents` column (Integer, signed) and every balance render. Never Float/Decimal.

### Category allow-list guard
**Source:** `record_operation` type guard `ledger.py:74-75`; `WRITEOFF_REASONS` allow-list precedent (writeoffs validate against it).
**Apply to:** `record_cash_movement` — `if category not in CASH_CATEGORIES: raise ValueError`.

### Router registration
**Source:** `app/main.py:53-79` `include_router` list.
**Apply to:** add `app.include_router(finance.router)` and `app.include_router(mobile_finance.router)` (+ their imports in the `main.py` import block).

### Migration chain
**Source:** `alembic/versions/0012_dictionary_name_lc.py` is current head (verified — highest numbered file).
**Apply to:** `0013_cash_movements.py` with `revision = "0013"`, `down_revision = "0012"`. Plain `op.create_table` (fresh CREATE — no batch mode; batch is only for ALTER, per 0001 precedent).

## No Analog Found

None. Every new file has a direct, verified in-repo analog. This phase is a structural clone.

## Metadata

**Analog search scope:** `app/models.py`, `app/services/{ledger,sales,returns,writeoffs}.py`, `app/db.py`, `app/core.py`, `app/routes/{__init__,writeoffs,mobile_reports}.py`, `app/main.py`, `app/templates/{base.html,mobile_pages/home.html}`, `tests/conftest.py`, `alembic/versions/`.
**Files scanned:** 15 (all read directly; every cited symbol confirmed present).
**Pattern extraction date:** 2026-07-14
