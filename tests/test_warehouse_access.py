"""Operator warehouse access (quick 261026-wha).

An administrator assigns warehouses to each operator; an operator moves and
sees stock only in those warehouses, may send a transfer to any warehouse, and
has no access to Финансы / Экспорт / backups. Service-level tests set the
request-scoped allowed set directly (what auth_guard does per request); the
HTTP tests drive the REAL guard through a real login.
"""

import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import date

import pytest
from alembic.config import Config
from sqlalchemy import select

from alembic import command
from app.config import settings
from app.core import business_date_bounds, local_today_iso, new_id
from app.models import Batch, Operation, Product, User, UserWarehouse, Warehouse
from app.services import auth, security
from app.services.batches import active_warehouses, open_batches
from app.services.dashboard import period_metrics
from app.services.ledger import WarehouseAccessError, record_operation
from app.services.operations import history_view
from app.services.reports import sales_profit_report
from app.services.returns import ORIGIN_NOT_FOUND_ERROR, register_return
from app.services.sales import register_sale
from app.services.transfers import register_transfer
from app.services.users import ADMIN_HAS_ALL_WAREHOUSES_ERROR, set_user_warehouses


@contextmanager
def _as_operator(*warehouses):
    """Restrict the current context to `warehouses`, as auth_guard does."""
    token = security._allowed_warehouses.set(frozenset(w.id for w in warehouses))
    try:
        yield
    finally:
        security._allowed_warehouses.reset(token)


@pytest.fixture()
def two_warehouses(session):
    """Warehouses «Мой» and «Чужой», one product with 5 units in a lot in each."""
    mine = Warehouse(id=new_id(), name="Мой")
    other = Warehouse(id=new_id(), name="Чужой")
    product = Product(id=new_id(), code="WH-001", name="Товар двух складов", quantity=0)
    session.add_all([mine, other, product])
    session.commit()
    lots = {}
    for warehouse in (mine, other):
        lot = Batch(
            id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0,
            cost_cents=10000,
        )
        session.add(lot)
        session.commit()
        record_operation(
            session, type_="receipt", product_id=product.id, qty_delta=5,
            unit_cost_cents=10000, batch_id=lot.id,
        )
        lots[warehouse.name] = lot
    return mine, other, product, lots


def _sell(session, product, lot):
    result, errors = register_sale(
        session, customer_id=None, codes=[product.code], qtys=["1"],
        prices=["200,00"], batch_ids=[lot.id],
    )
    return result, errors


# --- pickers and the write path ---------------------------------------------


def test_pickers_offer_only_the_operators_warehouses(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    with _as_operator(mine):
        assert [b.id for b in open_batches(session, product.id)] == [lots["Мой"].id]
        assert [w.id for w in active_warehouses(session)] == [mine.id]
        # A transfer destination may be any warehouse.
        assert {w.id for w in active_warehouses(session, scoped=False)} == {mine.id, other.id}


def test_record_operation_refuses_another_warehouses_lot(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    with _as_operator(mine), pytest.raises(WarehouseAccessError):
        record_operation(
            session, type_="sale", product_id=product.id, qty_delta=-1,
            batch_id=lots["Чужой"].id,
        )


def test_sale_from_another_warehouse_is_refused_before_any_write(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    before = session.scalar(select(Batch.quantity).where(Batch.id == lots["Чужой"].id))
    with _as_operator(mine):
        result, errors = _sell(session, product, lots["Чужой"])
    assert result is None and "batch-0" in errors
    session.expire_all()
    assert session.get(Batch, lots["Чужой"].id).quantity == before


def test_transfer_to_another_warehouse_is_allowed_but_not_from_it(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    with _as_operator(mine):
        result, errors = register_transfer(
            session, code=product.code, name=product.name, batch_id=lots["Мой"].id,
            dest_warehouse_id=other.id, qty_raw="2",
        )
        assert errors == {}, errors
        _, errors = register_transfer(
            session, code=product.code, name=product.name, batch_id=lots["Чужой"].id,
            dest_warehouse_id=mine.id, qty_raw="1",
        )
        assert "batch" in errors


def test_return_of_another_warehouses_sale_is_not_found(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    result, _ = _sell(session, product, lots["Чужой"])  # sold by an unrestricted user
    origin = session.scalars(
        select(Operation).where(Operation.sale_id == result["header"].id, Operation.type == "sale")
    ).one()
    with _as_operator(mine):
        _, errors = register_return(session, origin_op_id=origin.id, qty_raw="1")
    assert errors == {"form": ORIGIN_NOT_FOUND_ERROR}


# --- read surfaces -----------------------------------------------------------


def test_reports_history_and_dashboard_cover_own_warehouses_only(session, two_warehouses):
    mine, other, product, lots = two_warehouses
    _sell(session, product, lots["Мой"])
    _sell(session, product, lots["Чужой"])
    today = date.fromisoformat(local_today_iso(settings.display_tz))
    bounds = business_date_bounds(today, today)

    assert sales_profit_report(session, *bounds)["totals"]["revenue_cents"] == 40000
    with _as_operator(mine):
        assert sales_profit_report(session, *bounds)["totals"]["revenue_cents"] == 20000
        rows = history_view(session)["rows"]
        stock_warehouses = {
            r["warehouse"].id for r in rows if r["op"].type in ("sale", "receipt")
        }
        assert stock_warehouses == {mine.id}
        # Cash is per currency, not per warehouse: no «Расход» for an operator.
        metrics = period_metrics(session, today, today, settings.display_tz)
        assert metrics == {"revenue_cents": 20000, "profit_cents": 10000, "expense_cents": None}


# --- admin tool --------------------------------------------------------------


def _user(session, *, login, role="operator", password="pw"):
    user = User(
        id=new_id(), login=login, display_name=f"Пользователь {login}", role=role,
        password_hash=auth.hash_password(password), is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def test_set_user_warehouses_replaces_and_drops_unknown_ids(session, two_warehouses):
    mine, other, _, _ = two_warehouses
    operator = _user(session, login="op")
    assert set_user_warehouses(session, operator.id, [mine.id, other.id]) == (True, {})
    assert set_user_warehouses(session, operator.id, [other.id, "forged-id"]) == (True, {})
    rows = session.scalars(
        select(UserWarehouse.warehouse_id).where(UserWarehouse.user_id == operator.id)
    ).all()
    assert rows == [other.id]


def test_set_user_warehouses_refuses_an_administrator(session, two_warehouses):
    mine, _, _, _ = two_warehouses
    admin = _user(session, login="boss", role="administrator")
    assert set_user_warehouses(session, admin.id, [mine.id]) == (
        False,
        {"user": ADMIN_HAS_ALL_WAREHOUSES_ERROR},
    )


def test_admin_assigns_warehouses_on_the_users_page(client, session, two_warehouses):
    mine, other, _, _ = two_warehouses
    operator = _user(session, login="op")
    page = client.get("/settings/users").text
    assert "Нет складов" in page and "Изменить склады" in page

    resp = client.post(
        f"/settings/users/{operator.id}/warehouses", data={"warehouse_id": [mine.id]}
    )
    assert resp.status_code == 200
    assert "Склады пользователя сохранены." in resp.text
    assert session.scalars(
        select(UserWarehouse.warehouse_id).where(UserWarehouse.user_id == operator.id)
    ).all() == [mine.id]


# --- real guard, real login -------------------------------------------------


def _csrf(client) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").text)
    assert match
    return match.group(1)


def test_logged_in_operator_sees_own_stock_and_no_finance(
    anon_client, session, login, two_warehouses
):
    mine, other, product, _ = two_warehouses
    operator = _user(session, login="op")
    session.add(UserWarehouse(user_id=operator.id, warehouse_id=mine.id))
    session.commit()
    assert login(anon_client, "op", "pw").status_code == 303

    products = anon_client.get("/products", params={"code": product.code}).text
    # 5 units in «Мой» — not the global 10 across both warehouses.
    assert re.search(r'<td class="num">5</td>', products)
    assert not re.search(r'<td class="num">10</td>', products)
    assert 'href="/finance"' not in products
    assert anon_client.get("/finance", follow_redirects=False).status_code == 403


def test_operator_without_warehouses_is_told_to_ask_the_admin(anon_client, session, login):
    _user(session, login="newbie")
    assert login(anon_client, "newbie", "pw").status_code == 303
    page = anon_client.get("/receipts/new", follow_redirects=False)
    assert "Вам не назначен ни один склад — обратитесь к администратору." in page.text


# --- migration seed ----------------------------------------------------------


def test_migration_0029_gives_existing_operators_every_active_warehouse(tmp_path, monkeypatch):
    db_file = tmp_path / "user_warehouses.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "0028")
    op_id, admin_id, live_wh, gone_wh = new_id(), new_id(), new_id(), new_id()
    with closing(sqlite3.connect(db_file)) as conn:
        seeded = ((op_id, "op", "operator"), (admin_id, "boss", "administrator"))
        for uid, login_value, role in seeded:
            conn.execute(
                "INSERT INTO users (id, login, display_name, role, password_hash, is_active,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, 'x', 1, '2026-01-01', '2026-01-01')",
                (uid, login_value, login_value, role),
            )
        conn.execute(
            "INSERT INTO warehouses (id, name, currency, created_at, updated_at)"
            " VALUES (?, 'Живой', 'RUB', '2026-01-01', '2026-01-01')",
            (live_wh,),
        )
        conn.execute(
            "INSERT INTO warehouses (id, name, currency, created_at, updated_at, deleted_at)"
            " VALUES (?, 'Удалён', 'RUB', '2026-01-01', '2026-01-01', '2026-01-01T00:00:00+00:00')",
            (gone_wh,),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        rows = set(conn.execute("SELECT user_id, warehouse_id FROM user_warehouses"))
    default_wh = "00000000-0000-4000-8000-000000000010"  # migration 0007's seed
    assert rows == {(op_id, live_wh), (op_id, default_wh)}


def test_finance_tab_is_shown_to_an_administrator_only(client):
    """The desktop and mobile «Финансы» links render for the administrator."""
    assert 'href="/finance"' in client.get("/").text
    assert 'href="/m/finance"' in client.get("/m/").text
