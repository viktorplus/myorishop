"""FND-01/02/03 executable contract for the append-only operations ledger.

Interface contract for Plans 01-02 (db/models/config/core) and 01-03
(services/ledger). Module paths and signatures below are fixed — implement
against them, do not rename.

Phase 9 (D-12): stock-affecting ops (receipt/sale/writeoff/return/correction)
now REQUIRE a batch_id; audit ops (price_change/product_created/product_edited)
must stay batch-less. The mechanics tests below attribute their stock ops to
the `batch` fixture so they exercise the same batched write path production uses.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy import String, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Base, Operation, Product, Sale  # noqa: F401  (Product: contract symbol)
from app.services.ledger import (
    STOCK_AFFECTING_TYPES,
    compute_stock,
    next_seq,
    rebuild_stock,
    record_operation,
)


def test_record_operation_appends_and_updates_projection(session, product, batch):
    """FND-01 / D-09: ledger append updates the cached stock projection."""
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=5, batch_id=batch.id
    )
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=-2, batch_id=batch.id
    )

    session.expire_all()
    assert product.quantity == 3
    assert compute_stock(session, product.id) == 3
    count = session.scalar(text("SELECT COUNT(*) FROM operations"))
    assert count == 2


def test_record_operation_unknown_product_raises_value_error(session, product):
    """WR-01: unknown product fails with ValueError BEFORE any row is staged."""
    with pytest.raises(ValueError, match="unknown product"):
        record_operation(session, type_="correction", product_id="no-such-id", qty_delta=1)
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_operations_update_is_rejected(session, product, batch):
    """FND-01 / D-08: UPDATE on operations is blocked at the database level."""
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=5, batch_id=batch.id
    )

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE operations SET qty_delta = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_operations_delete_is_rejected(session, product, batch):
    """FND-01 / D-08: DELETE on operations is blocked at the database level."""
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=5, batch_id=batch.id
    )

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM operations"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_rebuild_stock_repairs_tampered_cache(session, product, batch):
    """FND-01 / D-09: cached quantity is always recomputable from the ledger."""
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=5, batch_id=batch.id
    )
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=-2, batch_id=batch.id
    )

    product.quantity = 999  # tamper with the cached projection
    session.commit()

    rebuild_stock(session)
    session.expire_all()
    assert product.quantity == compute_stock(session, product.id)


def test_conventions_uuid_cents_utc(session, product, batch):
    """FND-02 / D-05/D-06/D-07: UUID4 TEXT PKs, integer cents, UTC ISO-8601 TEXT."""
    op = record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )

    # D-05: UUID4 string primary key
    assert len(op.id) == 36
    assert uuid.UUID(op.id).version == 4

    # D-07: created_at is UTC ISO-8601 text
    assert datetime.fromisoformat(op.created_at).utcoffset() == timedelta(0)

    # The UUID-PK convention (D-05) targets SYNCED business entities whose
    # integer autoincrement IDs would collide across devices (CLAUDE.md). The
    # Phase 29 `sync_state` table is a LOCAL-only singleton (always id=1, never
    # pushed/pulled), so it deliberately uses an Integer PK — exempt it from the
    # 36-char-String-UUID PK check below (it is still guarded for money/float).
    _local_singleton_tables = {"sync_state"}

    # D-06 / Pitfall 3 guard: no Numeric/Float anywhere; *_cents are Integer
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert not isinstance(
                column.type, (sqlalchemy.Numeric, sqlalchemy.Float)
            ), f"{table.name}.{column.name} uses a float-ish type"
            if column.name.endswith("_cents"):
                assert isinstance(
                    column.type, sqlalchemy.Integer
                ), f"{table.name}.{column.name} must be Integer cents"
        if table.name in _local_singleton_tables:
            continue
        # D-05: every table's PK is a 36-char String UUID
        for pk_column in table.primary_key.columns:
            assert isinstance(pk_column.type, String)
            assert pk_column.type.length == 36


def test_audit_trail(session, product, batch):
    """FND-03 / D-17: every operation records who and when; seq increments."""
    op1 = record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )
    op2 = record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )

    assert op1.created_by == settings.operator_name
    assert isinstance(op1.created_at, str) and op1.created_at

    assert op1.seq == 1
    assert op2.seq == 2
    assert next_seq(session, settings.device_id) == 3


def test_record_operation_sets_sale_id(session, product, batch):
    """D-03: record_operation(..., sale_id=...) stores the link at INSERT time,
    and the ledger stays append-only afterwards (T-4-03b)."""
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    op = record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        sale_id=header.id,
        batch_id=batch.id,
    )
    assert op.sale_id == header.id

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE operations SET qty_delta = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


# --- D-12 mandatory batch guard (Plan 09-05 Task 3) ---


@pytest.mark.parametrize("type_", sorted(STOCK_AFFECTING_TYPES))
def test_stock_affecting_op_requires_batch(session, product, type_):
    """D-12: every stock-affecting type raises ValueError when no batch_id is
    supplied — the single-write-path enforcement backstop for LOT-05."""
    qty_delta = -1 if type_ in ("sale", "writeoff") else 1
    with pytest.raises(ValueError, match="batch_id is required"):
        record_operation(session, type_=type_, product_id=product.id, qty_delta=qty_delta)
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_audit_op_rejects_batch(session, product, batch):
    """D-12: an audit type given a batch_id raises ValueError (audit ops are
    batch-less — they carry no stock and must not touch a batch cache)."""
    with pytest.raises(ValueError, match="batch-less"):
        record_operation(
            session,
            type_="price_change",
            product_id=product.id,
            qty_delta=0,
            batch_id=batch.id,
        )
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_audit_ops_succeed_without_batch(session, product):
    """D-12: the qty_delta==0 audit types still write with batch_id=None."""
    for type_ in ("product_created", "price_change", "product_edited"):
        op = record_operation(session, type_=type_, product_id=product.id, qty_delta=0)
        assert op.batch_id is None


def test_append_only_preserved_for_return_and_correction(session, product, batch):
    """Phase 5 invariant: `return`/`correction` ops are NEW rows (never a
    mutation) and UPDATE/DELETE on operations still ABORT afterwards."""
    before = session.scalar(text("SELECT COUNT(*) FROM operations"))

    return_op = record_operation(
        session, type_="return", product_id=product.id, qty_delta=1, batch_id=batch.id
    )
    correction_op = record_operation(
        session, type_="correction", product_id=product.id, qty_delta=-1, batch_id=batch.id
    )

    after = session.scalar(text("SELECT COUNT(*) FROM operations"))
    assert after == before + 2
    assert return_op.id != correction_op.id  # two distinct NEW rows, not a mutation

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE operations SET qty_delta = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM operations"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_migration_0004_preserves_append_only_triggers(tmp_path, monkeypatch):
    """RESEARCH A1: alembic upgrade head must NOT rebuild `operations`
    (no `_alembic_tmp_operations` table) and the append-only triggers must
    still ABORT writes on a freshly migrated database."""
    from alembic.config import Config

    from alembic import command
    from app.db import build_engine

    db_path = str(tmp_path / "mig.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = build_engine(db_path)
    with engine.connect() as conn:
        tables = (
            conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
        )
        assert not any(name.startswith("_alembic_tmp") for name in tables)

        triggers = (
            conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'"))
            .scalars()
            .all()
        )
        assert "operations_no_update" in triggers
        assert "operations_no_delete" in triggers

        # Insert our own product — the DB now ships with ZERO seeded products
        # (migration 0022 removed the demo placeholder), so this test must not
        # rely on a pre-existing row.
        product_id = new_id()
        conn.execute(
            text(
                "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
                "VALUES (:id, 'TEST-1', 'Тест', 0, "
                "'2026-07-09T00:00:00+00:00', '2026-07-09T00:00:00+00:00')"
            ),
            {"id": product_id},
        )
        conn.execute(
            text(
                "INSERT INTO operations "
                "(id, type, product_id, qty_delta, device_id, seq, created_at, created_by) "
                "VALUES (:id, 'correction', :pid, 1, 'device-01', 1, "
                "'2026-07-09T00:00:00+00:00', 'tester')"
            ),
            {"id": new_id(), "pid": product_id},
        )
        conn.commit()

        with pytest.raises((OperationalError, IntegrityError)) as exc_info:
            conn.execute(text("UPDATE operations SET qty_delta = 99"))
        assert "append-only" in str(exc_info.value)


def test_seq_unique_per_device(session, product, batch):
    """D-08 / Pitfall 6: (device_id, seq) is UNIQUE — duplicates fail loudly."""
    existing = record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )

    duplicate = Operation(
        id=new_id(),
        type="correction",
        product_id=product.id,
        qty_delta=1,
        device_id=existing.device_id,
        seq=existing.seq,  # duplicate (device_id, seq)
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
