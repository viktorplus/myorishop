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
from sqlalchemy import inspect

from alembic import command
from app.config import settings
from app.core import format_ru_date, new_id
from app.models import Batch, Operation, Warehouse
from app.services.batches import active_warehouses, legacy_batch, open_batches


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


# --- Task 2: migration 0008 replay ----------------------------------------

_MIG_NOW = "2026-07-11T00:00:00+00:00"
PRODUCT_POS_ID = "00000000-0000-4000-8000-000000000091"  # ledger SUM > 0
PRODUCT_NONPOS_ID = "00000000-0000-4000-8000-000000000092"  # ledger SUM <= 0


def _seed_pre_batch_operations(conn):
    """Two products: one with positive ledger stock, one with non-positive."""
    for pid, code, name in (
        (PRODUCT_POS_ID, "POS-001", "Товар с остатком"),
        (PRODUCT_NONPOS_ID, "NEG-001", "Товар без остатка"),
    ):
        conn.execute(
            "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, code, name, 0, _MIG_NOW, _MIG_NOW),
        )
    # POS product: +10 receipt, -3 sale => SUM 7 (> 0, gets a legacy batch).
    # NEG product: +4 receipt, -5 sale => SUM -1 (<= 0, gets NO legacy batch).
    ops = [
        (PRODUCT_POS_ID, "receipt", 10, 1),
        (PRODUCT_POS_ID, "sale", -3, 2),
        (PRODUCT_NONPOS_ID, "receipt", 4, 3),
        (PRODUCT_NONPOS_ID, "sale", -5, 4),
    ]
    for pid, op_type, qty, seq in ops:
        conn.execute(
            "INSERT INTO operations "
            "(id, type, product_id, qty_delta, device_id, seq, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id(), op_type, pid, qty, "seed-device", seq, _MIG_NOW, "seed"),
        )
    conn.commit()


def test_migration_0008_seeds_legacy_batches_and_preserves_triggers(
    tmp_path, monkeypatch
):
    """Migration 0008: legacy seed from the ledger SUM, triggers intact (D-13/D-10)."""
    db_file = tmp_path / "migrate.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    # Upgrade to just before batches, then seed pre-batch data.
    command.upgrade(cfg, "0007")
    with closing(sqlite3.connect(db_file)) as conn:
        _seed_pre_batch_operations(conn)

    # Run migration 0008.
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        # (a) exactly one legacy batch for the SUM>0 product, quantity == ledger SUM.
        pos_rows = conn.execute(
            "SELECT quantity, is_legacy, warehouse_id, comment, expiry, price_cents "
            "FROM batches WHERE product_id = ? AND is_legacy = 1",
            (PRODUCT_POS_ID,),
        ).fetchall()
        assert len(pos_rows) == 1
        qty, is_legacy, warehouse_id, comment, expiry, price_cents = pos_rows[0]
        assert qty == 7  # ledger SUM, not the (zeroed) products.quantity cache
        assert is_legacy == 1
        assert warehouse_id == "00000000-0000-4000-8000-000000000010"
        assert comment == "Остаток до внедрения партий"
        assert expiry is None
        assert price_cents is None

        # (b) NO legacy batch for the non-positive product.
        neg_count = conn.execute(
            "SELECT count(*) FROM batches WHERE product_id = ?",
            (PRODUCT_NONPOS_ID,),
        ).fetchone()[0]
        assert neg_count == 0

        # (c) both append-only triggers survive the migration.
        trigger_count = conn.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type = 'trigger' AND name LIKE 'operations_no_%'"
        ).fetchone()[0]
        assert trigger_count == 2

        # (d) an UPDATE on operations still ABORTs (ledger immutable).
        with pytest.raises(sqlite3.OperationalError) as exc:
            conn.execute("UPDATE operations SET qty_delta = qty_delta")
        assert "append-only" in str(exc.value)

        # operations.batch_id column exists and is indexed.
        op_cols = {row[1] for row in conn.execute("PRAGMA table_info(operations)")}
        assert "batch_id" in op_cols
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert "ix_operations_batch_id" in indexes
        assert "ix_batches_product_id" in indexes


def test_migration_0008_downgrade_reverses_cleanly(tmp_path, monkeypatch):
    """downgrade() drops batches + operations.batch_id, leaving 0007 schema."""
    db_file = tmp_path / "downgrade.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0007")
    with closing(sqlite3.connect(db_file)) as conn:
        _seed_pre_batch_operations(conn)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0007")

    with closing(sqlite3.connect(db_file)) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "batches" not in tables
        op_cols = {row[1] for row in conn.execute("PRAGMA table_info(operations)")}
        assert "batch_id" not in op_cols
        # Triggers survive a full round-trip.
        trigger_count = conn.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type = 'trigger' AND name LIKE 'operations_no_%'"
        ).fetchone()[0]
        assert trigger_count == 2
