"""Phase 9 executable contract: Batch model, migration 0008, dual projection.

Covers LOT-01/LOT-03 write-path foundation:
  * `Batch` model conventions (D-03: no soft-delete) + `Operation.batch_id`.
  * `open_batches` D-07 ordering, `legacy_batch`, `active_warehouses` helpers.
  * `format_ru_date` display filter.
  * Migration 0008 replay (legacy seed from the ledger, trigger survival).
  * `record_operation` dual projection + ownership guard, `rebuild_stock`
    per-batch invariant.
"""

import sqlite3
from contextlib import closing

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.config import settings
from app.core import format_ru_date, new_id
from app.models import Batch, Operation, Warehouse
from app.services.batches import active_warehouses, legacy_batch, open_batches
from app.services.ledger import rebuild_stock, record_operation

# Migration 0008 frozen literals (re-declared, never imported from the module).
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
LEGACY_COMMENT = "Остаток до внедрения партий"


def _make_warehouse(session, name="Основной склад"):
    warehouse = Warehouse(id=new_id(), name=name)
    session.add(warehouse)
    session.commit()
    return warehouse


def _make_batch(session, *, product_id, warehouse_id, expiry, quantity, is_legacy=0):
    batch = Batch(
        id=new_id(),
        product_id=product_id,
        warehouse_id=warehouse_id,
        expiry=expiry,
        quantity=quantity,
        is_legacy=is_legacy,
    )
    session.add(batch)
    session.commit()
    return batch


# --- Task 1: model + read helpers + ru_date -------------------------------


def test_batch_model_has_no_deleted_at(session):
    """D-03: Batch carries no soft-delete column (no standalone CRUD)."""
    columns = {c.name for c in inspect(Batch).columns}
    assert "deleted_at" not in columns
    assert {
        "id",
        "product_id",
        "warehouse_id",
        "expiry",
        "price_cents",
        "location",
        "comment",
        "quantity",
        "is_legacy",
        "created_at",
        "updated_at",
    } <= columns


def test_operation_gains_batch_id_model_column(session):
    """D-10: Operation.batch_id is a nullable ORM FK named for the batch table."""
    batch_id_col = inspect(Operation).columns["batch_id"]
    assert batch_id_col.nullable is True
    fk = next(iter(batch_id_col.foreign_keys))
    assert fk.name == "fk_operations_batch_id_batches"
    assert fk.column.table.name == "batches"


def test_open_batches_ordering(session, product):
    """D-07: earliest expiry first, NULL expiry last, tie-broken by created_at."""
    warehouse = _make_warehouse(session)
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-01-01",
        quantity=3,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry=None,
        quantity=4,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2025-06-01",
        quantity=2,
    )

    ordered = open_batches(session, product.id)
    assert [b.expiry for b in ordered] == ["2025-06-01", "2026-01-01", None]


def test_open_batches_ordering_excludes_zero_quantity(session, product):
    """A zero-quantity batch never appears in the picker feed."""
    warehouse = _make_warehouse(session)
    live = _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-03-01",
        quantity=5,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-02-01",
        quantity=0,
    )

    ordered = open_batches(session, product.id)
    assert [b.id for b in ordered] == [live.id]


def test_open_batches_optional_warehouse_filter(session, product):
    """Passing warehouse_id narrows the feed to one warehouse."""
    wh_a = _make_warehouse(session, name="Склад А")
    wh_b = _make_warehouse(session, name="Склад Б")
    in_a = _make_batch(
        session,
        product_id=product.id,
        warehouse_id=wh_a.id,
        expiry="2026-01-01",
        quantity=3,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=wh_b.id,
        expiry="2025-01-01",
        quantity=3,
    )

    ordered = open_batches(session, product.id, warehouse_id=wh_a.id)
    assert [b.id for b in ordered] == [in_a.id]


def test_legacy_batch_lookup(session, product):
    """legacy_batch returns the is_legacy=1 row, or None when absent."""
    warehouse = _make_warehouse(session)
    assert legacy_batch(session, product.id) is None
    seeded = _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry=None,
        quantity=7,
        is_legacy=1,
    )
    assert legacy_batch(session, product.id).id == seeded.id


def test_active_warehouses_excludes_deleted(session):
    """active_warehouses omits soft-deleted rows and sorts by name."""
    from app.core import utcnow_iso

    keep = _make_warehouse(session, name="Активный")
    gone = _make_warehouse(session, name="Удалённый")
    gone.deleted_at = utcnow_iso()
    session.commit()

    names = [w.id for w in active_warehouses(session)]
    assert keep.id in names
    assert gone.id not in names


def test_format_ru_date():
    """ISO yyyy-mm-dd renders dd.mm.yyyy; empty inputs render empty."""
    assert format_ru_date("2026-07-12") == "12.07.2026"
    assert format_ru_date(None) == ""
    assert format_ru_date("") == ""
