"""WH-01 executable contract: Warehouse model, migration 0007, service layer.

Naming convention (mirrors test_dictionary.py/test_catalog.py): route/e2e
tests are prefixed test_web_, everything else is service/schema level.
"""

import re
import sqlite3
from contextlib import closing

from alembic.config import Config

from alembic import command
from app.config import settings
from app.services.warehouses import (
    NAME_REQUIRED_ERROR,
    WAREHOUSE_NOT_FOUND_ERROR,
    add_warehouse,
    list_warehouses,
    restore_warehouse,
    soft_delete_warehouse,
    update_warehouse,
)


def test_migration_0007_creates_and_seeds_default_warehouse(tmp_path, monkeypatch):
    """Migration 0007: fresh upgrade creates warehouses table + one seed row."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0006")
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(warehouses)")}
        assert cols == {"id", "name", "address", "created_at", "updated_at", "deleted_at"}

        rows = conn.execute(
            "SELECT id, name, address, deleted_at FROM warehouses"
        ).fetchall()
        assert rows == [
            ("00000000-0000-4000-8000-000000000010", "Склад по умолчанию", None, None)
        ]


def test_add_warehouse_creates_row(session):
    warehouse, errors = add_warehouse(
        session, name="  Главный склад  ", address="  ул. Ленина, 1  "
    )

    assert errors == {}
    assert warehouse is not None
    assert warehouse.name == "Главный склад"
    assert warehouse.address == "ул. Ленина, 1"
    assert len(warehouse.id) == 36


def test_add_warehouse_requires_name(session):
    warehouse, errors = add_warehouse(session, name="   ", address="")

    assert warehouse is None
    assert errors["name"] == NAME_REQUIRED_ERROR
    assert list_warehouses(session) == []


def test_add_warehouse_allows_duplicate_names(session):
    first, errors_a = add_warehouse(session, name="Склад №1", address="")
    second, errors_b = add_warehouse(session, name="Склад №1", address="")

    assert errors_a == {}
    assert errors_b == {}
    assert first is not None
    assert second is not None
    assert first.id != second.id


def test_update_warehouse_edits_fields(session):
    warehouse, _ = add_warehouse(session, name="Старое имя", address="Старый адрес")

    updated, errors = update_warehouse(
        session, warehouse.id, name="Новое имя", address="Новый адрес"
    )

    assert errors == {}
    assert updated is not None
    assert updated.name == "Новое имя"
    assert updated.address == "Новый адрес"
    persisted = session.get(type(warehouse), warehouse.id)
    assert persisted.name == "Новое имя"
    assert persisted.address == "Новый адрес"


def test_update_warehouse_unknown_id_returns_error(session):
    updated, errors = update_warehouse(
        session, "00000000-0000-4000-8000-000000000099", name="X", address=""
    )

    assert updated is None
    assert errors == {"warehouse": WAREHOUSE_NOT_FOUND_ERROR}


def test_soft_delete_and_restore_roundtrip(session):
    # Two warehouses so neither is "last active" when one is soft-deleted.
    warehouse_a, _ = add_warehouse(session, name="Склад А", address="")
    add_warehouse(session, name="Склад Б", address="")

    deleted, warning = soft_delete_warehouse(session, warehouse_a.id, confirm=False)

    assert deleted is True
    assert warning == {}
    assert warehouse_a.deleted_at
    # D-09: soft-deleted rows are STILL returned by list_warehouses.
    all_rows = list_warehouses(session)
    assert warehouse_a.id in [w.id for w in all_rows]

    restore_warehouse(session, warehouse_a.id)

    assert warehouse_a.deleted_at is None


def test_delete_last_active_warehouse_warns_then_allows(session):
    only, _ = add_warehouse(session, name="Единственный склад", address="")

    deleted, warning = soft_delete_warehouse(session, only.id, confirm=False)

    assert deleted is False
    assert warning == {"warehouse": only}
    assert only.deleted_at is None  # zero writes on the blocked path

    deleted, warning = soft_delete_warehouse(session, only.id, confirm=True)

    assert deleted is True
    assert warning == {}
    assert only.deleted_at is not None


def test_restore_warehouse_is_idempotent_when_already_active(session):
    warehouse, _ = add_warehouse(session, name="Активный склад", address="")

    restore_warehouse(session, warehouse.id)

    assert warehouse.deleted_at is None


# --- Web slice (routes + templates, Plan 08-02) ---
#
# Note: tests/conftest.py's `engine` fixture builds schema via
# `Base.metadata.create_all` (per 08-VALIDATION.md Wave 0: "No new fixtures
# needed"), which does NOT run the Alembic seed migration. So the `client`
# fixture starts with ZERO warehouses, unlike a real post-migration DB —
# tests below create their own warehouses instead of relying on the
# migration-seeded "Склад по умолчанию" row.


def test_web_warehouses_page_renders(client):
    response = client.get("/warehouses")
    assert response.status_code == 200
    assert "Склады" in response.text
    assert "Добавить склад" in response.text
    # No warehouses exist yet in this test DB (create_all, no seed) -> empty state.
    assert "Складов пока нет" in response.text


def test_web_add_and_edit_rows(client):
    response = client.post(
        "/warehouses", data={"name": "Второй склад", "address": "ул. Мира, 5"}
    )
    assert response.status_code == 200
    assert 'id="warehouse-rows"' in response.text
    assert "Второй склад" in response.text
    assert "<html" not in response.text

    match = re.search(r'id="edit-([0-9a-f-]{36})"', response.text)
    assert match is not None
    warehouse_id = match.group(1)

    response = client.post(
        f"/warehouses/{warehouse_id}",
        data={"name": "Второй склад (переименован)", "address": "ул. Мира, 5"},
    )
    assert response.status_code == 200
    assert 'id="warehouse-rows"' in response.text
    assert "Второй склад (переименован)" in response.text


def test_web_add_invalid_returns_swappable_422_partial(client):
    response = client.post("/warehouses", data={"name": "  ", "address": ""})
    assert response.status_code == 422
    assert 'id="warehouse-rows"' in response.text
    assert "Укажите название склада." in response.text


def test_web_deleted_warehouse_stays_visible_with_restore(client, session):
    # Two active warehouses so the one being deleted is not the last active one.
    add_warehouse(session, name="Склад А", address="")
    target, _ = add_warehouse(session, name="Склад на удаление", address="")

    response = client.post(f"/warehouses/{target.id}/delete")

    assert response.status_code == 200
    assert "HX-Redirect" not in response.headers
    assert "Склад на удаление" in response.text
    assert "Восстановить" in response.text


def test_web_delete_last_active_warehouse_warns_then_confirm_deletes(client, session):
    only, _ = add_warehouse(session, name="Единственный склад", address="")

    response = client.post(f"/warehouses/{only.id}/delete")

    assert response.status_code == 200
    assert "Это последний активный склад" in response.text
    assert "Удалить всё равно" in response.text

    follow_up = client.get("/warehouses")
    assert "Восстановить" not in follow_up.text

    confirm_response = client.post(
        f"/warehouses/{only.id}/delete", data={"confirm": "1"}
    )
    assert confirm_response.status_code == 200
    assert "Восстановить" in confirm_response.text


def test_web_nav_has_warehouses_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/warehouses"' in response.text
    assert "Склады" in response.text
