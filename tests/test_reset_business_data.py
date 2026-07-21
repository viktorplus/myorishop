"""Executable contract for scripts/reset_business_data.py (quick task 260721-fu0).

wipe_business_data(session, engine) is the importable core the module's
interactive main() wraps. It must:
  - empty ONLY the business/transactional tables (_WIPE_ORDER)
  - leave warehouses/dictionary/users/device_tokens/catalog_prices/sync_state
    byte-for-byte untouched
  - bypass the append-only triggers on operations/cash_movements ONLY for the
    duration of the wipe, then fully restore them
  - be idempotent on an already-empty database
main()'s non-tty abort path is exercised via subprocess so it never hangs
waiting on real stdin and never touches the real data/myorishop.db file.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core import new_id
from app.db import APPEND_ONLY_TRIGGERS, build_engine
from app.models import (
    Base,
    CashMovement,
    CustomerContact,
    Dictionary,
    Operation,
    Product,
    Sale,
    Warehouse,
)
from app.services.ledger import next_seq, record_operation
from scripts.reset_business_data import _WIPE_ORDER, wipe_business_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _seed_business_rows(session, product, warehouse, batch, customer):
    """Seed one row in every _WIPE_ORDER table, linked realistically."""
    contact = CustomerContact(
        id=new_id(), customer_id=customer.id, kind="phone", value="+7 900 000-00-00"
    )
    session.add(contact)

    sale = Sale(
        id=new_id(),
        customer_id=customer.id,
        created_at="2026-07-01T00:00:00Z",
        created_by="operator",
        device_id="device-01",
    )
    session.add(sale)
    session.flush()  # PRAGMA foreign_keys=ON: Sale must exist before Operation

    op = Operation(
        id=new_id(),
        type="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_price_cents=1000,
        sale_id=sale.id,
        batch_id=batch.id,
        device_id="device-01",
        seq=next_seq(session, "device-01"),
        created_at="2026-07-01T00:00:00Z",
        created_by="operator",
    )
    session.add(op)

    cash = CashMovement(
        id=new_id(),
        category="sale",
        amount_cents=1000,
        sale_id=sale.id,
        device_id="device-01",
        seq=1,
        created_at="2026-07-01T00:00:00Z",
        created_by="operator",
    )
    session.add(cash)
    session.commit()
    return sale, op, cash, contact


def _build_scratch_db(tmp_path, name: str = "scratch.db"):
    """A fully-schema'd + triggered SQLite file, isolated from the real DB."""
    scratch_path = tmp_path / name
    scratch_engine = build_engine(str(scratch_path))
    Base.metadata.create_all(scratch_engine)
    with scratch_engine.connect() as connection:
        for statement in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(statement)
        connection.commit()
    return scratch_path, scratch_engine


def test_wipe_empties_only_business_tables_preserves_the_rest(
    session, engine, product, warehouse, batch, customer
):
    dictionary_row = Dictionary(id=new_id(), code="99999", name="Тестовая запись")
    session.add(dictionary_row)
    session.commit()

    _seed_business_rows(session, product, warehouse, batch, customer)

    warehouse_snapshot = (warehouse.id, warehouse.name, warehouse.address)
    dictionary_snapshot = (dictionary_row.id, dictionary_row.code, dictionary_row.name)

    counts = wipe_business_data(session, engine)

    assert counts["products"] == 1
    assert counts["customers"] == 1
    assert counts["customer_contacts"] == 1
    assert counts["sales"] == 1
    assert counts["batches"] == 1
    assert counts["operations"] == 1
    assert counts["cash_movements"] == 1

    for model in _WIPE_ORDER:
        remaining = session.scalar(select(func.count()).select_from(model.__table__))
        assert remaining == 0, f"{model.__tablename__} not fully wiped"

    # Preserved tables: byte-for-byte unchanged, not just "still has a row".
    remaining_warehouse = session.get(Warehouse, warehouse.id)
    assert remaining_warehouse is not None
    assert (
        remaining_warehouse.id,
        remaining_warehouse.name,
        remaining_warehouse.address,
    ) == warehouse_snapshot

    remaining_dict = session.get(Dictionary, dictionary_row.id)
    assert remaining_dict is not None
    assert (
        remaining_dict.id,
        remaining_dict.code,
        remaining_dict.name,
    ) == dictionary_snapshot


def test_wipe_is_idempotent_on_an_already_empty_database(session, engine):
    """No products/customers/etc. seeded — must be a clean no-op, no error."""
    counts = wipe_business_data(session, engine)
    assert all(n == 0 for n in counts.values())
    # Calling it again changes nothing and still doesn't error.
    counts_again = wipe_business_data(session, engine)
    assert all(n == 0 for n in counts_again.values())


def test_wipe_restores_append_only_enforcement_afterward(
    session, engine, product, warehouse, batch, customer
):
    """After wipe_business_data returns, a fresh INSERT works but UPDATE/DELETE
    on operations still raises — the append-only guarantee is provably intact,
    not just assumed."""
    _seed_business_rows(session, product, warehouse, batch, customer)
    wipe_business_data(session, engine)

    # products/batches were wiped too — a batch-less audit op only needs a
    # fresh product (product_created/product_edited/price_change never carry
    # a batch_id, per the ledger's STOCK_AFFECTING_TYPES guard).
    fresh_product = Product(id=new_id(), code="FRESH-1", name="Свежий товар", quantity=0)
    session.add(fresh_product)
    session.commit()

    op = record_operation(
        session,
        type_="product_created",
        product_id=fresh_product.id,
        qty_delta=0,
        payload={"code": fresh_product.code, "name": fresh_product.name},
    )

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE operations SET qty_delta = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM operations"))
    assert "append-only" in str(exc_info.value)
    session.rollback()

    # Sanity: the row from the fresh INSERT is still exactly there.
    assert session.get(Operation, op.id) is not None


def test_main_aborts_without_a_tty_and_never_wipes(tmp_path):
    """subprocess with closed/empty stdin is non-interactive by construction
    (never a tty) — main() must abort BEFORE calling wipe_business_data,
    exit nonzero, and never hang. Uses a throwaway scratch SQLite file via
    env override — NEVER the real data/myorishop.db."""
    scratch_path, scratch_engine = _build_scratch_db(tmp_path)

    from sqlalchemy.orm import sessionmaker

    ScratchSession = sessionmaker(bind=scratch_engine)
    with ScratchSession() as seed_session:
        seed_session.add(Product(id=new_id(), code="KEEP-1", name="Не трогать", quantity=0))
        seed_session.commit()

    env = {**os.environ}
    scratch_url_path = str(scratch_path).replace("\\", "/")
    env["DATABASE_URL"] = f"sqlite:///{scratch_url_path}"
    env["DB_PATH"] = str(scratch_path)

    result = subprocess.run(
        [sys.executable, "scripts/reset_business_data.py"],
        cwd=str(PROJECT_ROOT),
        env=env,
        input=b"",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0, (
        f"expected nonzero exit; stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    with ScratchSession() as check_session:
        remaining = check_session.scalar(select(func.count()).select_from(Product.__table__))
        assert remaining == 1, "main() must abort BEFORE wiping when stdin is not a tty"
