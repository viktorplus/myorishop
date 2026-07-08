"""FND-01/02/03 executable contract for the append-only operations ledger.

Interface contract for Plans 01-02 (db/models/config/core) and 01-03
(services/ledger). Module paths and signatures below are fixed — implement
against them, do not rename.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy import String, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Base, Operation, Product  # noqa: F401  (Product: contract symbol)
from app.services.ledger import compute_stock, next_seq, rebuild_stock, record_operation


def test_record_operation_appends_and_updates_projection(session, product):
    """FND-01 / D-09: ledger append updates the cached stock projection."""
    record_operation(session, type_="correction", product_id=product.id, qty_delta=5)
    record_operation(session, type_="correction", product_id=product.id, qty_delta=-2)

    session.expire_all()
    assert product.quantity == 3
    assert compute_stock(session, product.id) == 3
    count = session.scalar(text("SELECT COUNT(*) FROM operations"))
    assert count == 2


def test_operations_update_is_rejected(session, product):
    """FND-01 / D-08: UPDATE on operations is blocked at the database level."""
    record_operation(session, type_="correction", product_id=product.id, qty_delta=5)

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE operations SET qty_delta = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_operations_delete_is_rejected(session, product):
    """FND-01 / D-08: DELETE on operations is blocked at the database level."""
    record_operation(session, type_="correction", product_id=product.id, qty_delta=5)

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM operations"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_rebuild_stock_repairs_tampered_cache(session, product):
    """FND-01 / D-09: cached quantity is always recomputable from the ledger."""
    record_operation(session, type_="correction", product_id=product.id, qty_delta=5)
    record_operation(session, type_="correction", product_id=product.id, qty_delta=-2)

    product.quantity = 999  # tamper with the cached projection
    session.commit()

    rebuild_stock(session)
    session.expire_all()
    assert product.quantity == compute_stock(session, product.id)


def test_conventions_uuid_cents_utc(session, product):
    """FND-02 / D-05/D-06/D-07: UUID4 TEXT PKs, integer cents, UTC ISO-8601 TEXT."""
    op = record_operation(session, type_="correction", product_id=product.id, qty_delta=1)

    # D-05: UUID4 string primary key
    assert len(op.id) == 36
    assert uuid.UUID(op.id).version == 4

    # D-07: created_at is UTC ISO-8601 text
    assert datetime.fromisoformat(op.created_at).utcoffset() == timedelta(0)

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
        # D-05: every table's PK is a 36-char String UUID
        for pk_column in table.primary_key.columns:
            assert isinstance(pk_column.type, String)
            assert pk_column.type.length == 36


def test_audit_trail(session, product):
    """FND-03 / D-17: every operation records who and when; seq increments."""
    op1 = record_operation(session, type_="correction", product_id=product.id, qty_delta=1)
    op2 = record_operation(session, type_="correction", product_id=product.id, qty_delta=1)

    assert op1.created_by == settings.operator_name
    assert isinstance(op1.created_at, str) and op1.created_at

    assert op1.seq == 1
    assert op2.seq == 2
    assert next_seq(session, settings.device_id) == 3


def test_seq_unique_per_device(session, product):
    """D-08 / Pitfall 6: (device_id, seq) is UNIQUE — duplicates fail loudly."""
    existing = record_operation(session, type_="correction", product_id=product.id, qty_delta=1)

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
