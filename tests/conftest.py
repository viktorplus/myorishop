"""Shared fixtures for the Wave-0 test suite.

Contract note: app.db / app.models / app.core arrive in Plan 01-02,
app.main arrives in Plan 01-03. Until then the whole suite is RED by design.
Pitfall 7: use a file-based tmp_path SQLite database, never an in-memory
one (per-connection memory DBs break with pooled sessions).
"""

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import new_id
from app.db import APPEND_ONLY_TRIGGERS, build_engine
from app.models import Base, Product


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
