"""Warehouse service (WH-01): plain CRUD + warn-but-allow last-warehouse guard.

D-08: this backs a single settings-style page (/warehouses), not a full
Products-style list+search+/new+/{id}/edit CRUD scaffold. D-09 (superseded
2026-07-14, LIST-04): the list VIEW now hides deleted rows by default;
status='all'/status='deleted' still reach them — write-path callers
(add/update/delete/restore routes) all use this new default too.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import new_id, utcnow_iso
from app.models import Batch, Warehouse
from app.services.pagination import paginate

NAME_REQUIRED_ERROR = "Укажите название склада."
WAREHOUSE_NOT_FOUND_ERROR = "Склад не найден."


def list_warehouses(
    session: Session,
    *,
    name: str = "",
    address: str = "",
    status: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Filtered/sorted/paginated warehouse list (Phase 14, LIST-01..04).

    `status`: "" or "active" (default) -> active rows only (D-14, the NEW
    default — deleted rows are hidden unless explicitly requested);
    "deleted" -> deleted rows only; "all" -> both.
    `name`/`address`: case-insensitive substring filters.
    `sort`: "name_asc"/"name_desc" -> plain (reverse) alphabetical by name;
    anything else (default) -> the EXISTING D-07 key, unchanged:
    active-first, then by name.

    Returns a dict: warehouses (the page slice), total, total_pages, page,
    plus the echoed name/address/status/sort filter state.
    """
    rows = list(session.scalars(select(Warehouse)))

    if status == "deleted":
        rows = [w for w in rows if w.deleted_at is not None]
    elif status == "all":
        pass
    else:
        rows = [w for w in rows if w.deleted_at is None]

    if name:
        needle = name.strip().lower()
        rows = [w for w in rows if needle in (w.name or "").lower()]
    if address:
        needle = address.strip().lower()
        rows = [w for w in rows if needle in (w.address or "").lower()]

    if sort == "name_asc":
        rows = sorted(rows, key=lambda w: w.name.lower())
    elif sort == "name_desc":
        rows = sorted(rows, key=lambda w: w.name.lower(), reverse=True)
    else:
        rows = sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))

    page_rows, total, total_pages = paginate(rows, page)
    return {
        "warehouses": page_rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "name": name,
        "address": address,
        "status": status,
        "sort": sort,
    }


def add_warehouse(
    session: Session, *, name: str, address: str
) -> tuple[Warehouse | None, dict[str, str]]:
    """Create a warehouse; requires non-blank name. No uniqueness check (D-04)."""
    name = name.strip()
    address = address.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
    if errors:
        return None, errors
    warehouse = Warehouse(id=new_id(), name=name, address=address or None)
    session.add(warehouse)
    session.commit()
    return warehouse, {}


def update_warehouse(
    session: Session, warehouse_id: str, *, name: str, address: str
) -> tuple[Warehouse | None, dict[str, str]]:
    """Edit an existing warehouse in place; unknown id is a distinct error."""
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None:
        return None, {"warehouse": WAREHOUSE_NOT_FOUND_ERROR}
    name = name.strip()
    address = address.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
    if errors:
        return None, errors
    warehouse.name = name
    warehouse.address = address or None
    session.commit()
    return warehouse, {}


def restore_warehouse(session: Session, warehouse_id: str) -> None:
    """Clear deleted_at; idempotent no-op if already active or unknown id."""
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is None:
        return
    warehouse.deleted_at = None
    session.commit()


def soft_delete_warehouse(
    session: Session, warehouse_id: str, *, confirm: bool = False
) -> tuple[bool, dict]:
    """Soft-delete one warehouse; warn-but-allow if it is the last active one.

    Returns (deleted, warning):
      (True, {})                -> deleted (not last-active, or confirm=True)
      (False, {})                -> unknown id or already deleted (no-op)
      (False, {"stock": N})     -> blocked: N units of stock on hand across
                                     this warehouse's batches (D-11, checked
                                     FIRST, non-overridable — confirm=1 has
                                     NO effect on this check — ZERO writes)
      (False, {"warehouse": w})  -> blocked pending confirm=1 re-POST,
                                     only reached once the stock check
                                     above has passed, ZERO writes staged
    """
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is not None:
        return False, {}

    warehouse_stock = session.scalar(
        select(func.coalesce(func.sum(Batch.quantity), 0)).where(
            Batch.warehouse_id == warehouse_id
        )
    )
    if warehouse_stock > 0:
        return False, {"stock": warehouse_stock}

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
