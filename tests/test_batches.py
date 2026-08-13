"""Phase 9 executable contract: Batch model, migration 0008, dual projection.

Covers LOT-01/LOT-03 write-path foundation:
  * `Batch` model conventions (D-03: no soft-delete) + `Operation.batch_id`.
  * `open_batches` D-07 ordering, `legacy_batch`, `active_warehouses` helpers.
  * `format_ru_date` display filter.
  * Migration 0008 replay (legacy seed from the ledger, trigger survival).
  * `record_operation` dual projection + ownership guard, `rebuild_stock`
    per-batch invariant.
"""

import re
import sqlite3
from contextlib import closing

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.config import settings
from app.core import format_ru_date, new_id, utcnow_iso
from app.models import Batch, Operation, Product, Warehouse
from app.routes import batch_identity_label
from app.services.batches import (
    BATCH_NOT_FOUND_ERROR,
    COMMENT_TOO_LONG_ERROR,
    EXPIRY_ERROR,
    LOCATION_TOO_LONG_ERROR,
    NAME_TOO_LONG_ERROR,
    active_warehouses,
    batches_for_products,
    expiring_batches,
    legacy_batch,
    open_batches,
    update_batch,
)
from app.services.catalog import PRICE_ERROR
from app.services.ledger import next_seq, rebuild_stock, record_operation
from app.services.receipts import register_receipt


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


def test_batches_for_products_empty_list_returns_empty_dict(session):
    """No product_ids -> {} with no query issued."""
    assert batches_for_products(session, []) == {}


def test_batches_for_products_groups_by_product_excludes_zero_quantity(session, product):
    """Grouped by product_id; a quantity-0 batch never appears in any list."""
    warehouse = _make_warehouse(session)
    other = Product(id=new_id(), code="TEST-002", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()

    p1_live = _make_batch(
        session, product_id=product.id, warehouse_id=warehouse.id, expiry="2026-01-01", quantity=3
    )
    _make_batch(
        session, product_id=product.id, warehouse_id=warehouse.id, expiry="2026-02-01", quantity=0
    )
    p2_live = _make_batch(
        session, product_id=other.id, warehouse_id=warehouse.id, expiry="2026-03-01", quantity=5
    )

    grouped = batches_for_products(session, [product.id, other.id])
    assert [b.id for b in grouped[product.id]] == [p1_live.id]
    assert [b.id for b in grouped[other.id]] == [p2_live.id]


def test_batches_for_products_ordering_matches_open_batches(session, product):
    """Ordering within each product's list matches open_batches: earliest expiry
    first, NULL expiry last, tie-broken by oldest created_at."""
    warehouse = _make_warehouse(session)
    _make_batch(
        session, product_id=product.id, warehouse_id=warehouse.id, expiry="2026-01-01", quantity=3
    )
    _make_batch(
        session, product_id=product.id, warehouse_id=warehouse.id, expiry=None, quantity=4
    )
    _make_batch(
        session, product_id=product.id, warehouse_id=warehouse.id, expiry="2025-06-01", quantity=2
    )

    grouped = batches_for_products(session, [product.id])
    assert [b.expiry for b in grouped[product.id]] == ["2025-06-01", "2026-01-01", None]


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


def test_expiring_batches_filter_and_order(session, product):
    """LOT-06/D-07: earliest expiry first; zero-quantity and NULL-expiry excluded."""
    warehouse = _make_warehouse(session)
    batch_a = _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-09-01",
        quantity=5,
    )
    batch_b = _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-07-01",
        quantity=3,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2026-08-01",
        quantity=0,
    )
    _make_batch(
        session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry=None,
        quantity=4,
    )

    rows = expiring_batches(session)
    assert [row["batch"].id for row in rows] == [batch_b.id, batch_a.id]
    for row in rows:
        assert row["product"].id == product.id
        assert row["warehouse"].id == warehouse.id


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


def test_batch_identity_label_prefers_name_then_derives_then_falls_back():
    """Task 1 (quick-260813-l0y): stored name wins; else derive; else bare product name."""

    class _P:
        name = "Крем для рук"

    class _B:
        name = None
        expiry = None

    product = _P()

    named = _B()
    named.name = "Партия А"
    named.expiry = "2026-01-01"
    assert batch_identity_label(named, product) == "Партия А"

    dated = _B()
    dated.expiry = "2026-08-13"
    assert batch_identity_label(dated, product) == "Крем для рук — 13.08.2026"

    bare = _B()
    assert batch_identity_label(bare, product) == "Крем для рук"


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
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
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

        # (d) an UPDATE that CHANGES an immutable column still ABORTs (ledger
        # immutable). RAISE(ABORT) surfaces as IntegrityError through the raw
        # sqlite3 driver.
        #
        # Phase 28 (migration 0018) made these triggers column-scoped and
        # VALUE-based, so the former probe here — `SET qty_delta = qty_delta` —
        # is now a permitted no-op self-assignment and no longer fires. The
        # probe therefore writes a genuinely different value; the invariant
        # under test (an immutable ledger column cannot be changed) is
        # unchanged. Full coverage of the relaxed guard, including the
        # synced_at stamp and mixed-column rejection, lives in
        # tests/test_append_only_cursor.py.
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute("UPDATE operations SET qty_delta = qty_delta + 1")
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
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
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


# --- Task 3: record_operation dual projection + rebuild_stock invariant ----


def test_record_operation_dual_projection(session, product, batch):
    """D-11: a batched receipt bumps BOTH product.quantity and batch.quantity."""
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        batch_id=batch.id,
    )
    session.expire_all()
    assert product.quantity == 5
    assert batch.quantity == 5


def test_record_operation_rejects_foreign_batch(session, product, batch):
    """D-12 ownership backstop: a batch of another product is rejected (T-09)."""
    other = Product(id=new_id(), code="OTHER-1", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()
    with pytest.raises(ValueError, match="does not belong"):
        record_operation(
            session,
            type_="sale",
            product_id=other.id,
            qty_delta=-1,
            batch_id=batch.id,
        )
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_record_operation_unknown_batch_raises(session, product):
    """An unresolvable batch id raises before any write."""
    with pytest.raises(ValueError, match="unknown batch"):
        record_operation(
            session,
            type_="sale",
            product_id=product.id,
            qty_delta=-1,
            batch_id="no-such-batch",
        )
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_record_operation_batch_guard_is_mandatory(session, product):
    """Plan 09-05 D-12 flip (supersedes Plan 01's optional-batch behavior): a
    batch-less STOCK op now raises; an audit op still writes batch-less."""
    with pytest.raises(ValueError, match="batch_id is required"):
        record_operation(session, type_="correction", product_id=product.id, qty_delta=3)
    session.rollback()

    audit = record_operation(
        session, type_="product_created", product_id=product.id, qty_delta=0
    )
    assert audit.batch_id is None


def test_rebuild_stock_invariant_holds_for_legacy_null_bucket(
    session, product, warehouse
):
    """rebuild_stock: a legacy batch absorbs the NULL bucket; caches stay consistent."""
    legacy = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
        is_legacy=1,
    )
    session.add(legacy)
    session.commit()
    # NULL-bucket op (pre-Phase-9 style, no batch_id): inserted directly since
    # the mandatory D-12 guard now rejects a batch-less stock op via the write
    # path. A batched op on the legacy batch then goes through record_operation.
    session.add(
        Operation(
            id=new_id(),
            type="receipt",
            product_id=product.id,
            qty_delta=4,
            batch_id=None,
            device_id=settings.device_id,
            seq=next_seq(session, settings.device_id),
            created_at=utcnow_iso(),
            created_by=settings.operator_name,
        )
    )
    product.quantity = Product.quantity + 4
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=2,
        batch_id=legacy.id,
    )
    rebuild_stock(session)
    session.expire_all()
    assert product.quantity == 6
    assert legacy.quantity == 6  # 2 direct + 4 absorbed NULL bucket


def test_rebuild_stock_raises_on_corrupted_ledger(session, product, warehouse):
    """A cross-product ledger row breaks the per-product invariant (D-11)."""
    other = Product(id=new_id(), code="OTH-2", name="Чужой", quantity=0)
    session.add(other)
    b = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
    )
    session.add(b)
    session.commit()
    # Inject a cross-product row directly (bypassing record_operation's guard):
    # batch b belongs to `product`, but the op is attributed to `other`.
    session.add(
        Operation(
            id=new_id(),
            type="receipt",
            product_id=other.id,
            qty_delta=5,
            batch_id=b.id,
            device_id="corrupt",
            seq=1,
            created_at=utcnow_iso(),
            created_by="test",
        )
    )
    session.commit()
    with pytest.raises(ValueError, match="invariant"):
        rebuild_stock(session)
    session.rollback()


# --- Plan 09-09: batches.name column, migration 0009, auto-name, chooser ---


def test_batch_model_has_name_column(session):
    """UAT test 1 symptom 3: Batch exposes a nullable `name` label column."""
    columns = {c.name for c in inspect(Batch).columns}
    assert "name" in columns
    assert inspect(Batch).columns["name"].nullable is True


def test_migration_0009_adds_batch_name_column(tmp_path, monkeypatch):
    """Migration 0009 adds a nullable batches.name via a NATIVE add-column.

    Asserts the two append-only `operations_no_%` triggers survive (proving no
    move-and-copy rebuild touched the ledger) and that downgrade drops the
    column cleanly, back to the 0008 schema.
    """
    db_file = tmp_path / "migrate_0009.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0008")
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        batch_cols = {row[1] for row in conn.execute("PRAGMA table_info(batches)")}
        assert "name" in batch_cols
        # Native add-column must NOT have rebuilt/dropped the ledger triggers.
        trigger_count = conn.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type = 'trigger' AND name LIKE 'operations_no_%'"
        ).fetchone()[0]
        assert trigger_count == 2

    command.downgrade(cfg, "0008")
    with closing(sqlite3.connect(db_file)) as conn:
        batch_cols = {row[1] for row in conn.execute("PRAGMA table_info(batches)")}
        assert "name" not in batch_cols


def test_register_receipt_autogenerates_batch_name(session):
    """A new batch gets «{product.name} — dd.mm.yyyy»; a top-up never rewrites it."""
    warehouse = _make_warehouse(session)
    product_name = "Крем для рук «Молоко»"

    result, errors = register_receipt(
        session,
        code="AUTO-NAME-1",
        name=product_name,
        qty_raw="5",
        cost_raw="",
        sale_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    batch = result["batch"]
    assert re.fullmatch(
        rf"{re.escape(product_name)} — \d{{2}}\.\d{{2}}\.\d{{4}}", batch.name
    )
    original_name = batch.name

    # A top-up on the same batch leaves its stored name untouched.
    topup_result, topup_errors = register_receipt(
        session,
        code="AUTO-NAME-1",
        name=product_name,
        qty_raw="3",
        cost_raw="",
        sale_raw="",
        warehouse_id=warehouse.id,
        batch_choice=batch.id,
    )
    assert topup_errors == {}
    assert topup_result["batch"].id == batch.id
    session.expire_all()
    assert session.get(Batch, batch.id).name == original_name


def _update_batch_kwargs(**overrides):
    """Default no-op update_batch kwargs (all six fields blank); override per test."""
    kwargs = {
        "name_raw": "",
        "expiry_raw": "",
        "location_raw": "",
        "comment_raw": "",
        "price_raw": "",
        "cost_raw": "",
    }
    kwargs.update(overrides)
    return kwargs


def test_update_batch_unknown_id_returns_error_and_writes_nothing(session):
    result, errors = update_batch(session, "no-such-batch", **_update_batch_kwargs())
    assert result is None
    assert errors == {"batch": BATCH_NOT_FOUND_ERROR}


def test_update_batch_invalid_price_and_cost_rejected(session, batch):
    result, errors = update_batch(
        session, batch.id, **_update_batch_kwargs(price_raw="abc", cost_raw="xyz")
    )
    assert result is None
    assert errors == {"price": PRICE_ERROR, "cost": PRICE_ERROR}


def test_update_batch_invalid_expiry_rejected(session, batch):
    result, errors = update_batch(
        session, batch.id, **_update_batch_kwargs(expiry_raw="not-a-date")
    )
    assert result is None
    assert errors == {"expiry": EXPIRY_ERROR}


def test_update_batch_too_long_fields_all_reported_together(session, batch):
    result, errors = update_batch(
        session,
        batch.id,
        **_update_batch_kwargs(
            name_raw="A" * 221, location_raw="B" * 101, comment_raw="C" * 201
        ),
    )
    assert result is None
    assert errors == {
        "name": NAME_TOO_LONG_ERROR,
        "location": LOCATION_TOO_LONG_ERROR,
        "comment": COMMENT_TOO_LONG_ERROR,
    }


def test_update_batch_clears_all_six_fields_to_null(session, product, warehouse):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        name="Партия А",
        expiry="2026-01-01",
        location="Полка 3",
        comment="Комментарий",
        price_cents=1000,
        cost_cents=500,
        quantity=0,
    )
    session.add(seeded)
    session.commit()

    result, errors = update_batch(session, seeded.id, **_update_batch_kwargs())
    assert errors == {}
    session.refresh(result)
    assert result.name is None
    assert result.expiry is None
    assert result.location is None
    assert result.comment is None
    assert result.price_cents is None
    assert result.cost_cents is None


def test_update_batch_successful_edit_never_touches_locked_fields(session, product, warehouse):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=7,
        is_legacy=0,
    )
    session.add(seeded)
    session.commit()
    orig_quantity = seeded.quantity
    orig_warehouse_id = seeded.warehouse_id
    orig_product_id = seeded.product_id
    orig_is_legacy = seeded.is_legacy

    result, errors = update_batch(
        session,
        seeded.id,
        **_update_batch_kwargs(name_raw="Новая партия", price_raw="12,50"),
    )
    assert errors == {}
    assert result.quantity == orig_quantity
    assert result.warehouse_id == orig_warehouse_id
    assert result.product_id == orig_product_id
    assert result.is_legacy == orig_is_legacy


def test_update_batch_noop_resubmit_leaves_updated_at_unchanged_then_real_edit_advances_it(
    session, product, warehouse
):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        name="Партия",
        expiry="2026-01-01",
        location="Полка 1",
        comment="Заметка",
        price_cents=1000,
        cost_cents=500,
        quantity=0,
    )
    session.add(seeded)
    session.commit()
    forced_old = "2020-01-01T00:00:00+00:00"
    seeded.updated_at = forced_old
    session.commit()

    # Genuine no-op: resubmit the batch's own current values.
    result, errors = update_batch(
        session,
        seeded.id,
        name_raw=seeded.name,
        expiry_raw=seeded.expiry,
        location_raw=seeded.location,
        comment_raw=seeded.comment,
        price_raw="10,00",
        cost_raw="5,00",
    )
    assert errors == {}
    session.refresh(result)
    assert result.updated_at == forced_old

    # A real change advances updated_at.
    result2, errors2 = update_batch(
        session,
        seeded.id,
        name_raw="Изменённая партия",
        expiry_raw=seeded.expiry,
        location_raw=seeded.location,
        comment_raw=seeded.comment,
        price_raw="10,00",
        cost_raw="5,00",
    )
    assert errors2 == {}
    session.refresh(result2)
    assert result2.updated_at != forced_old
    assert result2.updated_at > forced_old


# --- desktop /batches routes ---


def test_web_batch_edit_shows_readonly_rows_with_links(client, session, product, warehouse):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=5,
    )
    session.add(seeded)
    session.commit()

    response = client.get(f"/batches/{seeded.id}/edit")
    assert response.status_code == 200
    assert f"/writeoff?code={product.code}" in response.text
    assert f"/transfers?code={product.code}" in response.text


def test_web_batch_update_saves_changes_and_redirects(client, session, product, warehouse):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=5,
    )
    session.add(seeded)
    session.commit()

    response = client.post(
        f"/batches/{seeded.id}",
        data={
            "name": "Новая партия",
            "expiry": "",
            "location": "",
            "comment": "",
            "price": "12,50",
            "cost": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/products/{product.id}/edit"
    session.expire_all()
    updated = session.get(Batch, seeded.id)
    assert updated.name == "Новая партия"
    assert updated.price_cents == 1250


def test_web_batch_update_invalid_price_rerenders_422_unchanged(client, session, product, warehouse):
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=5,
    )
    session.add(seeded)
    session.commit()

    response = client.post(
        f"/batches/{seeded.id}",
        data={
            "name": "",
            "expiry": "",
            "location": "",
            "comment": "",
            "price": "abc",
            "cost": "",
        },
    )
    assert response.status_code == 422
    assert PRICE_ERROR in response.text
    session.expire_all()
    unchanged = session.get(Batch, seeded.id)
    assert unchanged.price_cents is None


def test_web_batch_edit_unknown_id_404s(client):
    response = client.get("/batches/no-such-batch/edit")
    assert response.status_code == 404


def test_web_batch_update_unknown_id_404s(client):
    response = client.post(
        "/batches/no-such-batch",
        data={"name": "", "expiry": "", "location": "", "comment": "", "price": "", "cost": ""},
    )
    assert response.status_code == 404


def test_web_batch_edit_shows_breadcrumbs_and_identity_line(client, session, product, warehouse):
    """Task 2 (quick-260813-l0y): breadcrumb trail + identity line above the h1."""
    seeded = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        name="Партия А",
        quantity=5,
    )
    session.add(seeded)
    session.commit()

    response = client.get(f"/batches/{seeded.id}/edit")
    assert response.status_code == 200
    body = response.text
    assert '<a href="/">Главная</a>' in body
    assert '<a href="/products">Товары</a>' in body
    assert f'<a href="/products/{product.id}/edit">{product.name} ({product.code})</a>' in body
    assert '<span aria-current="page">Партия</span>' in body
    assert f'«{seeded.name}», {warehouse.name}, {seeded.quantity} шт.' in body


def test_web_batch_edit_breadcrumb_escapes_html_in_product_name(client, session, warehouse):
    """T-quick-260813-l0y-01: an HTML-metacharacter product name is escaped, never |safe."""
    product = Product(
        id=new_id(), code="XSS-001", name="<script>alert(1)</script>", quantity=0
    )
    session.add(product)
    seeded = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=1)
    session.add(seeded)
    session.commit()

    response = client.get(f"/batches/{seeded.id}/edit")
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_web_chooser_shows_batch_name_in_topup_label(client, session, product):
    """The chooser top-up label surfaces batch.name when the batch has one."""
    warehouse = _make_warehouse(session)
    batch_name = "Тестовый товар — 01.02.2026"
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        name=batch_name,
        quantity=5,
    )
    session.add(batch)
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": product.code, "warehouse_id": warehouse.id},
    )
    assert response.status_code == 200
    assert batch_name in response.text
