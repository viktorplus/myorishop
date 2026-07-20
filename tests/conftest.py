"""Shared fixtures for the Wave-0 test suite.

Contract note: app.db / app.models / app.core arrive in Plan 01-02,
app.main arrives in Plan 01-03. Until then the whole suite is RED by design.
Pitfall 7: use a file-based tmp_path SQLite database, never an in-memory
one (per-connection memory DBs break with pooled sessions).
"""

import pytest
from fastapi import Request
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id
from app.db import APPEND_ONLY_TRIGGERS, build_engine
from app.models import Base, Batch, Customer, Operation, Product, Sale, User, Warehouse
from app.services import security
from app.services.auth import hash_password
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
    """Authenticated TestClient — the legacy suite stays green under the guard.

    Phase 25 (AUTH-01): app/main now installs an app-level `auth_guard` in front
    of every route. So the ~45 pre-existing test files would all 303→/login
    unless the client is authenticated. This fixture:
      - seeds ONE administrator so first-run (`count_users==0`) does not fire;
      - overrides `auth_guard` with a no-op that attaches that admin to
        `request.state.user` + the `_current_user` contextvar. Overriding the
        whole guard (not just current_user) also bypasses CSRF for the legacy
        POST tests, which carry no token.

    app.main is imported lazily INSIDE this fixture (module-level import would
    break collection of pure-unit test modules).

    RESEARCH Pitfall 1: `with TestClient(app)` RUNS lifespan, so the startup
    backup must be disabled here or every client test would VACUUM the
    developer's real data/myorishop.db into backups/.
    """
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.db import get_session
    from app.main import app
    from app.services.security import auth_guard

    monkeypatch.setattr(settings, "backup_on_startup", False)

    admin = User(
        id=new_id(),
        login="test-admin",
        display_name="Тест Админ",
        role="administrator",
        password_hash=hash_password("test-admin-pw"),
        is_active=1,
    )
    session.add(admin)
    session.commit()

    def override_get_session():
        yield session

    def override_auth_guard(request: Request):
        # Attach the seeded admin so request.state.user / current_user /
        # author_fields() resolve, and bypass the real guard's CSRF check.
        request.state.user = admin
        security._current_user.set(admin)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[auth_guard] = override_auth_guard
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(engine, session, monkeypatch):
    """Unauthenticated TestClient with the REAL app-level guard active.

    For the auth/roles integration tests (Plan 04 Task 3): no `auth_guard`
    override, so the guard runs for real — anonymous requests 303→/login (or
    →/setup on a zero-user DB), CSRF is enforced on unsafe methods, and a real
    `POST /login` is required to obtain a session. Only `get_session` +
    `backup_on_startup` are overridden. Deliberately does NOT seed a user so
    each test controls the user count (first-run vs seeded).
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
def device_client(engine, session, monkeypatch):
    """TestClient with the REAL guard active PLUS a minted device token (SYNC-09).

    Built on the SAME body as `anon_client` — the real `auth_guard` runs, only
    `get_session` + `backup_on_startup` are overridden (the backup monkeypatch is
    mandatory: `with TestClient(app)` runs the real lifespan, which would VACUUM
    the developer's DB). It additionally mints ONE active device token via
    `devices.mint_token` and yields a `(client, token)` pair so a test can send
    `Authorization: Bearer <token.plaintext>` against the `/api/sync/` tree while
    still exercising the genuine bypass. Does NOT touch `client` / `anon_client`.
    """
    from collections import namedtuple

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.db import get_session
    from app.main import app
    from app.services import devices

    monkeypatch.setattr(settings, "backup_on_startup", False)

    result, errors = devices.mint_token(
        session, device_id=new_id(), label="Тест устройство"
    )
    assert errors == {}
    row, plaintext = result

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    DeviceClient = namedtuple("DeviceClient", ["client", "plaintext", "prefix"])
    try:
        with TestClient(app) as test_client:
            yield DeviceClient(test_client, plaintext, row.token_prefix)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sync_driver_pair(engine, session, tmp_path, monkeypatch):
    """`(client, server_session, plaintext)` for the Plan-03 network driver tests.

    The LOCAL client DB is the standard `session`/`engine`. A SEPARATE server DB
    (its own engine + append-only triggers) backs the in-process app, reached over
    an `httpx.ASGITransport`-bridged SYNC `httpx.Client` — so a push genuinely
    transmits rows across the client→server boundary and the D-13 FK closure is
    really exercised (the server starts empty; a missing parent would FK-fail).

    A blocking portal drives the async ASGITransport from the driver's synchronous
    `httpx.Client` (D-04 sync-Session rule): the sub-transport is `ASGITransport`,
    wrapped so the sync client's `handle_request` runs it and buffers the response.
    `settings.sync_token` / `settings.sync_server_url` are monkeypatched so the
    driver targets the in-process app; the device token is minted in the SERVER DB
    (require_device validates against the server's own `get_session`).
    """
    from collections import namedtuple

    import anyio.from_thread
    import httpx
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.db import APPEND_ONLY_TRIGGERS, build_engine, get_session
    from app.main import app
    from app.models import Base
    from app.services import devices

    monkeypatch.setattr(settings, "backup_on_startup", False)

    # A SEPARATE server database so a push crosses a real boundary.
    server_engine = build_engine(str(tmp_path / "server.db"))
    Base.metadata.create_all(server_engine)
    with server_engine.connect() as connection:
        for statement in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(statement)
        connection.commit()
    ServerSession = sessionmaker(bind=server_engine)
    server_session = ServerSession()

    # The Bearer token lives in the SERVER DB (require_device checks it there).
    result, errors = devices.mint_token(
        server_session, device_id=new_id(), label="Драйвер"
    )
    assert errors == {}
    _, plaintext = result

    monkeypatch.setattr(settings, "sync_token", plaintext)
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")

    def override_get_session():
        yield server_session

    app.dependency_overrides[get_session] = override_get_session

    class _SyncASGITransport(httpx.BaseTransport):
        """Sync transport bridging to an async `httpx.ASGITransport` via a portal."""

        def __init__(self, asgi_app, portal):
            self._transport = httpx.ASGITransport(app=asgi_app)
            self._portal = portal

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            async def _run():
                response = await self._transport.handle_async_request(request)
                body = await response.aread()
                await response.aclose()
                return response.status_code, response.headers, body

            status_code, headers, body = self._portal.call(_run)
            return httpx.Response(
                status_code=status_code, headers=headers, content=body, request=request
            )

    Pair = namedtuple("SyncDriverPair", ["client", "server_session", "plaintext"])
    try:
        with anyio.from_thread.start_blocking_portal() as portal:
            with httpx.Client(
                transport=_SyncASGITransport(app, portal), base_url="http://sync"
            ) as driver_client:
                yield Pair(driver_client, server_session, plaintext)
    finally:
        app.dependency_overrides.clear()
        server_session.close()


@pytest.fixture()
def login():
    """Helper: POST /login on a test client, returning the response.

    Usage: `login(anon_client, "admin", "pw")`. Does not follow redirects so the
    caller can assert on the 303/204 status and Location/HX-Redirect headers.
    """

    def _login(test_client, login_value, password):
        return test_client.post(
            "/login",
            data={"login": login_value, "password": password},
            follow_redirects=False,
        )

    return _login


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
