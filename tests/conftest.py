"""Shared fixtures for the Wave-0 test suite.

Contract note: app.db / app.models / app.core arrive in Plan 01-02,
app.main arrives in Plan 01-03. Until then the whole suite is RED by design.
Pitfall 7: use a file-based tmp_path SQLite database, never an in-memory
one (per-connection memory DBs break with pooled sessions).
"""

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id
from app.db import APPEND_ONLY_TRIGGERS, build_engine
from app.models import Base, Batch, Customer, Operation, Product, Sale, Warehouse
from app.services.ledger import next_seq, record_operation


@pytest.fixture()
def engine(tmp_path):
    """File-based SQLite engine with PRAGMA listener and append-only triggers."""
    engine = build_engine(str(tmp_path / "test.db"))
    # Test-fixture-only exception to the Alembic rule: create schema directly.
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        for statement in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(statement)
        connection.commit()
    return engine


@pytest.fixture()
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


@pytest.fixture()
def product(session):
    """Seed one demo product with zero stock."""
    product = Product(
        id=new_id(),
        code="TEST-001",
        name="Тестовый товар",
        quantity=0,
    )
    session.add(product)
    session.commit()
    return product


@pytest.fixture()
def warehouse(session):
    """Seed one active warehouse (Phase 9: batch receipt/picker tests)."""
    warehouse = Warehouse(id=new_id(), name="Тестовый склад")
    session.add(warehouse)
    session.commit()
    return warehouse


@pytest.fixture()
def batch(session, product, warehouse):
    """Seed one empty batch for `product` in `warehouse` (quantity grows via ops)."""
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
    )
    session.add(batch)
    session.commit()
    return batch


@pytest.fixture()
def stocked_product(session):
    """Seed a product with real ledger-backed stock (Phase 4: sale/oversell tests).

    Phase 9: the receipt is attributed to a batch so the product and batch
    quantity projections agree (D-11). batch_id is still optional, so batch-less
    call sites keep working — this fixture just exercises the batched path.
    """
    product = Product(
        id=new_id(),
        code="STK-001",
        name="Товар со склада",
        quantity=0,
    )
    session.add(product)
    warehouse = Warehouse(id=new_id(), name="Склад для остатка")
    session.add(warehouse)
    session.commit()
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
    )
    session.add(batch)
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=8,
        unit_cost_cents=1000,
        unit_price_cents=1500,
        batch_id=batch.id,
    )
    return product


@pytest.fixture()
def customer(session):
    """Seed one demo customer (Phase 4: sale/customer link tests)."""
    customer = Customer(
        id=new_id(),
        name="Анна",
        surname="Иванова",
        consultant_number="12345",
        search_lc="анна иванова 12345",
    )
    session.add(customer)
    session.commit()
    return customer


@pytest.fixture()
def client(engine, session, product, monkeypatch):
    """TestClient with the app's get_session dependency overridden.

    app.main is imported lazily INSIDE this fixture: it only exists after
    Plan 01-03, and a module-level import would break collection of
    test_ledger / test_pragmas during Wave 2.

    RESEARCH Pitfall 1: `with TestClient(app)` RUNS lifespan, so the startup
    backup must be disabled here or every client test would VACUUM the
    developer's real data/myorishop.db into backups/.
    """
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.db import get_session
    from app.main import app

    monkeypatch.setattr(settings, "backup_on_startup", False)

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def past_sale(session):
    """Factory fixture: seed a Sale + Operation pair at a controlled past UTC date.

    21-VALIDATION.md Wave 0 gap: every CUST-07 spend-window test needs a sale
    placed at an explicit past date (e.g. 2 months ago must fall outside the
    month window but inside the year window), and no existing fixture does
    that. This bypasses record_operation on purpose: record_operation always
    stamps created_at with the current-UTC helper and the operations_no_update
    trigger ABORTs any later UPDATE, so backdating is only possible at INSERT time.
    The append-only triggers guard UPDATE/DELETE, never INSERT — a direct
    INSERT with an explicit created_at is therefore safe and does not touch
    the ledger's immutability guarantee.

    LIMITATION, stated loudly: this helper does NOT update the
    Product.quantity / Batch.quantity projections, because it does not go
    through the single write path (record_operation). It is for
    READ-ONLY INSIGHT TESTS (CUST-06/07/08) only. Never combine it with
    rebuild_stock or any stock-invariant assertion, and never use it to
    test stock.
    """

    def _make(
        customer,
        product,
        *,
        created_at: str,
        qty: int = 1,
        unit_price_cents: int | None = 1000,
        type_: str = "sale",
        sale: Sale | None = None,
        batch_id: str | None = None,
    ) -> tuple[Sale, Operation]:
        if sale is None:
            sale = Sale(
                id=new_id(),
                customer_id=customer.id,
                created_at=created_at,
                created_by=settings.operator_name,
                device_id=settings.device_id,
            )
            session.add(sale)
            # PRAGMA foreign_keys=ON is active — the Sale header must exist
            # (be flushed) before the Operation referencing it is added.
            session.flush()

        qty_delta = -qty if type_ == "sale" else qty
        op = Operation(
            id=new_id(),
            type=type_,
            product_id=product.id,
            qty_delta=qty_delta,
            unit_cost_cents=None,
            unit_price_cents=unit_price_cents,
            sale_id=sale.id,
            batch_id=batch_id,
            device_id=settings.device_id,
            seq=next_seq(session, settings.device_id),
            created_at=created_at,
            created_by=settings.operator_name,
        )
        session.add(op)
        session.commit()
        return sale, op

    return _make


@pytest.fixture()
def mobile_client_factory(session):
    """Factory fixture: build an isolated TestClient for a mobile router.

    Phase 11 foundation (Plan 01): every later mobile feature plan (02-08)
    builds and tests its own new APIRouter completely in isolation, without
    editing app/main.py or tests/conftest.py again, and without needing the
    router registered in the real app (real registration happens once, in
    Plan 09). Deliberately binds to a FRESH FastAPI() instance, NOT
    app.main.app — a bare instance has no lifespan, so it never triggers the
    startup backup and needs no `backup_on_startup` monkeypatch (contrast
    with the `client` fixture above).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.db import get_session

    def _make(*routers):
        mobile_app = FastAPI()
        for router in routers:
            mobile_app.include_router(router)

        def override_get_session():
            yield session

        mobile_app.dependency_overrides[get_session] = override_get_session
        return TestClient(mobile_app)

    return _make
