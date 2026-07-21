"""Executable contract for scripts/load_test_data.py (quick task 260721-fu0).

load_test_data(session) is the importable core the module's thin main()
wraps. Against a freshly-reset (or fresh) database it must create exactly
10 customers and exactly 10 Operation rows for EACH of the 9
OPERATION_TYPES values (90 total) — via service-layer calls only, never a
raw Operation()/CashMovement() ORM construction. It must refuse cleanly
(zero writes) when any Product already exists.
"""

from pathlib import Path

from sqlalchemy import func, select

import scripts.load_test_data as load_test_data_module
from app.models import OPERATION_TYPES, Customer, Operation
from scripts.load_test_data import load_test_data


def test_guard_refuses_when_a_product_already_exists(session, product):
    """`product` fixture seeds one Product — the DB is "not freshly reset"."""
    result = load_test_data(session)

    assert result.get("error")
    assert session.scalars(select(Customer)).all() == []
    assert session.scalars(select(Operation)).all() == []


def test_load_test_data_creates_ten_customers_and_ten_ops_per_type(session):
    result = load_test_data(session)

    assert not result.get("error")

    customers = session.scalars(select(Customer)).all()
    assert len(customers) == 10

    rows = session.execute(select(Operation.type, func.count()).group_by(Operation.type)).all()
    counts = dict(rows)

    assert set(counts) == set(OPERATION_TYPES), (
        f"unexpected operation types present: {set(counts) - set(OPERATION_TYPES)}, "
        f"missing: {set(OPERATION_TYPES) - set(counts)}"
    )
    for op_type in OPERATION_TYPES:
        assert counts[op_type] == 10, f"{op_type}: expected 10, got {counts[op_type]}"

    total = session.scalar(select(func.count()).select_from(Operation.__table__))
    assert total == 90


def test_transfer_rows_total_exactly_ten_not_twenty(session):
    """register_transfer writes TWO rows/call — must be called 5x, not 10x."""
    load_test_data(session)

    transfer_count = session.scalar(
        select(func.count()).select_from(Operation.__table__).where(Operation.type == "transfer")
    )
    assert transfer_count == 10


def test_update_product_emits_price_change_and_product_edited_separately(session):
    """update_product changes a price field AND a non-price field per call —
    must land as one price_change row AND one product_edited row (10 + 10),
    not e.g. 20 of one type or a collapsed 10 total."""
    load_test_data(session)

    price_change_count = session.scalar(
        select(func.count())
        .select_from(Operation.__table__)
        .where(Operation.type == "price_change")
    )
    product_edited_count = session.scalar(
        select(func.count())
        .select_from(Operation.__table__)
        .where(Operation.type == "product_edited")
    )
    assert price_change_count == 10
    assert product_edited_count == 10


def test_load_test_data_never_constructs_ledger_rows_directly():
    """Every ledger row must be reachable ONLY through the documented service
    functions — grep the implementation to confirm no Operation()/
    CashMovement() ORM construction appears directly in this script."""
    source = Path(load_test_data_module.__file__).read_text(encoding="utf-8")
    assert "Operation(" not in source
    assert "CashMovement(" not in source
