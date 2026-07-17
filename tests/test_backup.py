"""BCK-01 executable contract: VACUUM INTO backups + verified restore path.

Covers D-08 (VACUUM INTO timestamped standalone copy), D-09 (startup backup
gated on flag / DB exists / DB has data), D-10 (retention keeps newest 30),
D-11 (restore verified by an automated roundtrip that also proves the
append-only triggers survive — closes RESEARCH Assumption A2), PD-11
(same-second collision suffix + mtime ordering), PD-12 (POST /backup gets
its engine from session.get_bind()), PD-13 (skip conditions live inside
startup_backup; lifespan calls it module-qualified), and security V12
(/backup never accepts a client-supplied filename or path).

Naming convention: route-level tests are test_web_backup_* / test_web_nav_*;
everything else must NOT contain "web_backup" or "nav" (task selectors).
"""

import os
import re
import shutil

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id
from app.db import build_engine
from app.models import Batch, Product, Warehouse
from app.services.backup import (
    create_backup,
    prune_backups,
    startup_backup,
)
from app.services.ledger import compute_stock, record_operation

BACKUP_NAME_RE = re.compile(r"myorishop-\d{8}-\d{6}.*\.db$")
BACKUP_ERROR = "Не удалось создать резервную копию"
EMPTY_LIST_TEXT = "Резервных копий пока нет"


def _ensure_batch(session, product):
    """A valid batch id for a product — the mandatory D-12 write-path guard
    (Plan 09-05) requires every stock op to name a batch."""
    batch = session.scalars(
        select(Batch).where(Batch.product_id == product.id)
    ).first()
    if batch is None:
        warehouse = session.scalars(select(Warehouse)).first()
        if warehouse is None:
            warehouse = Warehouse(id=new_id(), name="Склад")
            session.add(warehouse)
            session.flush()
        batch = Batch(
            id=new_id(),
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity=0,
        )
        session.add(batch)
        session.flush()
    return batch.id


def _seed_receipt(session, product, qty=5):
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=qty,
        unit_cost_cents=1000,
        batch_id=_ensure_batch(session, product),
    )


def _make_dummy_backups(backup_dir, count, start_age=1000):
    """Create dummy myorishop-*.db files with staggered PAST mtimes."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    files = []
    now = os.stat(backup_dir).st_mtime
    for i in range(count):
        f = backup_dir / f"myorishop-2020010{i + 1}-000000.db"
        f.write_bytes(b"dummy")
        stamp = now - start_age + i
        os.utime(f, (stamp, stamp))
        files.append(f)
    return files


# --- create_backup (D-08, PD-11, Pitfall 4) ---------------------------------


def test_create_backup_produces_openable_snapshot(engine, session, product, tmp_path):
    _seed_receipt(session, product)
    path = create_backup(engine, tmp_path / "backups")
    assert path.exists()
    assert BACKUP_NAME_RE.search(path.name)
    assert path.stat().st_size > 0
    snapshot_engine = build_engine(str(path))
    with sessionmaker(bind=snapshot_engine)() as snap_session:
        restored = snap_session.get(Product, product.id)
        assert restored is not None
        assert restored.code == "TEST-001"


def test_create_backup_same_second_names_do_not_collide(engine, session, product, tmp_path):
    _seed_receipt(session, product)
    first = create_backup(engine, tmp_path / "backups")
    second = create_backup(engine, tmp_path / "backups")
    assert first != second
    assert first.exists() and second.exists()


def test_create_backup_failure_removes_partial_target(engine, tmp_path, monkeypatch):
    import sqlalchemy.engine

    def boom(self, statement, parameters=None, execution_options=None):
        raise RuntimeError("simulated VACUUM failure")

    monkeypatch.setattr(sqlalchemy.engine.Connection, "exec_driver_sql", boom)
    backup_dir = tmp_path / "backups"
    with pytest.raises(RuntimeError):
        create_backup(engine, backup_dir)
    assert list(backup_dir.glob("*.db")) == []


def test_prune_backups_keeps_newest_by_mtime(tmp_path):
    backup_dir = tmp_path / "backups"
    files = _make_dummy_backups(backup_dir, 5)
    prune_backups(backup_dir, keep=3)
    remaining = sorted(p.name for p in backup_dir.glob("myorishop-*.db"))
    expected = sorted(p.name for p in files[-3:])
    assert remaining == expected


# --- restore roundtrip (D-11, Assumption A2) --------------------------------


def test_backup_and_restore_roundtrip_preserves_data_and_triggers(
    engine, session, product, tmp_path
):
    _seed_receipt(session, product, qty=5)
    backup_file = create_backup(engine, tmp_path / "backups")
    restored_path = tmp_path / "restored.db"
    # Simulates the copy step of restore.bat (D-11).
    shutil.copyfile(backup_file, restored_path)
    restored_engine = build_engine(str(restored_path))
    with sessionmaker(bind=restored_engine)() as restored_session:
        restored = restored_session.get(Product, product.id)
        assert restored.quantity == 5
        assert compute_stock(restored_session, product.id) == 5
    # A2: append-only triggers must survive VACUUM INTO.
    with restored_engine.connect() as conn:
        with pytest.raises((OperationalError, IntegrityError)) as exc_info:
            conn.exec_driver_sql("UPDATE operations SET qty_delta = 99")
        assert "append-only" in str(exc_info.value)


# --- startup_backup gate (D-09, PD-13) ---------------------------------------


def test_startup_backup_skips_when_disabled(engine, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(settings, "backup_on_startup", False)
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    assert startup_backup(engine=engine) is None
    assert not backup_dir.exists() or list(backup_dir.glob("*.db")) == []


def test_startup_backup_skips_when_db_missing_or_empty(engine, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(settings, "backup_on_startup", True)
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    # DB file missing.
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "nope.db"))
    assert startup_backup(engine=engine) is None
    # DB file exists (the engine fixture file) but holds no rows.
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    assert startup_backup(engine=engine) is None
    assert not backup_dir.exists() or list(backup_dir.glob("*.db")) == []


def test_startup_backup_creates_and_prunes_when_enabled(
    engine, session, product, tmp_path, monkeypatch
):
    backup_dir = tmp_path / "backups"
    _make_dummy_backups(backup_dir, 2)
    monkeypatch.setattr(settings, "backup_on_startup", True)
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "backup_keep", 2)
    path = startup_backup(engine=engine)
    assert path is not None
    remaining = sorted(backup_dir.glob("myorishop-*.db"), key=lambda p: p.stat().st_mtime)
    assert len(remaining) == 2
    assert remaining[-1].name == path.name


def test_web_lifespan_invokes_startup_backup(monkeypatch):
    from fastapi.testclient import TestClient

    import app.services.backup as backup_service
    from app.main import app

    calls = []
    monkeypatch.setattr(backup_service, "startup_backup", lambda: calls.append(1))
    with TestClient(app):
        pass
    assert calls == [1]


# --- /backup routes (V12, PD-12) — green after Task 3 ------------------------


def test_web_backup_page_lists_and_instructs(client, tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty-backups"
    empty_dir.mkdir()
    monkeypatch.setattr(settings, "backup_dir", str(empty_dir))
    response = client.get("/backup")
    assert response.status_code == 200
    body = response.text
    assert "Резервные копии" in body
    assert "Создать резервную копию" in body
    assert "Восстановление из копии" in body
    assert "restore.bat" in body
    assert "Хранятся последние 30 копий" in body
    assert EMPTY_LIST_TEXT in body


def test_web_backup_now_creates_and_lists(client, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    response = client.post("/backup")
    assert response.status_code == 200
    files = list(backup_dir.glob("myorishop-*.db"))
    assert len(files) == 1
    assert "Резервная копия создана" in response.text
    assert files[0].name in response.text


def test_web_backup_now_error_block(client, tmp_path, monkeypatch):
    import app.services.backup as backup_service

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))

    def boom(engine, target_dir):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(backup_service, "create_backup", boom)
    response = client.post("/backup")
    assert response.status_code == 200
    assert BACKUP_ERROR in response.text
    assert not backup_dir.exists() or list(backup_dir.glob("*.db")) == []


def test_web_backup_ignores_client_params(client, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    response = client.post("/backup?path=..%5Cevil&filename=x.db")
    assert response.status_code == 200
    files = list(backup_dir.glob("*.db"))
    assert len(files) == 1
    assert BACKUP_NAME_RE.search(files[0].name)
    assert "evil" not in response.text


def test_web_nav_has_backup_link(client):
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'href="/backup"' in response.text
    assert "Резервные копии" in response.text
