"""BCK-02 executable contract: full-table CSV export (products/sales/customers).

Covers D-06 (dedicated /export page with three static download links, plain
<a href> never hx-get) and D-07 (utf-8-sig BOM-once encoding so Cyrillic
survives an Excel double-click open), RESEARCH Pitfall 4 (";" row delimiter
so a comma-decimal money field like "12,50" is never itself split), and
security T-06-09/T-06-10 (zero client-supplied filename/path params on any
export route; CSV-formula-injection hardening via a leading apostrophe on
any free-text cell starting with =, +, -, or @).

Naming convention: route-level tests are test_web_export_* / test_web_nav_*;
service-level tests (Task 1) must NOT contain those prefixes.
"""

import asyncio
import csv
import io
from datetime import date

from sqlalchemy import select

from app.config import settings
from app.core import local_day_bounds_utc, new_id, utcnow_iso
from app.models import Batch, Customer, Sale, Warehouse
from app.services.export import (
    _csv_rows,
    _csv_safe,
    _encode_once,
    stream_cash_movements_csv,
)
from app.services.finance import record_cash_movement
from app.services.ledger import record_operation

DAY = date(2026, 7, 10)
TZ = "Europe/Moscow"


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

# --- service-level: BOM-once + delimiter correctness (Task 1) ---------------


def test_csv_bom_appears_once():
    chunks = list(
        _encode_once(_csv_rows(["A", "B"], [["1", "2"], ["3", "4"], ["5", "6"]]))
    )
    joined = b"".join(chunks)
    assert joined.startswith(b"\xef\xbb\xbf")
    # The BOM bytes must not appear a second time anywhere later in the stream.
    assert joined.count(b"\xef\xbb\xbf") == 1


def test_money_field_not_split_by_delimiter():
    chunks = list(
        _encode_once(_csv_rows(["Товар", "Цена"], [["Тестовый товар", "12,50"]]))
    )
    text = b"".join(chunks).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Товар", "Цена"]
    # The comma-decimal money value stays ONE field — never split by ";".
    assert rows[1] == ["Тестовый товар", "12,50"]
    assert len(rows[1]) == 2


def test_csv_safe_prefixes_formula_injection_chars():
    for prefix in ("=", "+", "-", "@"):
        assert _csv_safe(f"{prefix}cmd") == f"'{prefix}cmd"


def test_csv_safe_leaves_normal_values_untouched():
    assert _csv_safe("Обычное имя") == "Обычное имя"
    assert _csv_safe("") == ""


# --- service-level: stream_cash_movements_csv (FIN-09, Task 3) -------------


def _stream_body(response):
    """Collect a StreamingResponse's chunks (body_iterator is always async —
    Starlette wraps a sync generator via iterate_in_threadpool)."""

    async def _collect() -> bytes:
        chunks = [chunk async for chunk in response.body_iterator]
        return b"".join(chunks)

    return asyncio.run(_collect())


def test_cash_movements_csv_bom_delimiter_and_header(session):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"

    import app.services.finance as finance_module

    original_utcnow_iso = finance_module.utcnow_iso
    finance_module.utcnow_iso = lambda: mid
    try:
        record_cash_movement(
            session,
            category="withdrawal_supplier",
            amount_cents=-1200,
            note="Оплата",
        )
        record_cash_movement(session, category="sale", amount_cents=3000)
    finally:
        finance_module.utcnow_iso = original_utcnow_iso

    response = stream_cash_movements_csv(session, start_iso, end_iso)
    body = _stream_body(response)
    assert body.count(b"\xef\xbb\xbf") == 1

    text = body.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Когда", "Категория", "Комментарий", "Сумма"]
    assert len(rows) == 3
    # Oldest-first: both rows share the same timestamp, insertion order holds.
    assert rows[1][1] == "Оплата поставщику"
    assert rows[1][2] == "Оплата"
    assert rows[1][3] == "-12,00"
    assert rows[2][1] == "Продажа"
    assert rows[2][2] == ""
    assert rows[2][3] == "30,00"


def test_cash_movements_csv_null_note_renders_empty(session, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    monkeypatch.setattr("app.services.finance.utcnow_iso", lambda: mid)
    record_cash_movement(session, category="sale", amount_cents=1000)

    response = stream_cash_movements_csv(session, start_iso, end_iso)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][2] == ""
    assert "None" not in text


def test_cash_movements_csv_escapes_formula_injection_note(session, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    monkeypatch.setattr("app.services.finance.utcnow_iso", lambda: mid)
    record_cash_movement(
        session,
        category="withdrawal_other",
        amount_cents=-100,
        note="=CMD()",
    )

    response = stream_cash_movements_csv(session, start_iso, end_iso)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][2] == "'=CMD()"


def test_cash_movements_csv_half_open_period_and_order(session):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)

    import app.services.finance as finance_module

    original_utcnow_iso = finance_module.utcnow_iso
    try:
        finance_module.utcnow_iso = lambda: start_iso
        record_cash_movement(session, category="sale", amount_cents=1000)
        finance_module.utcnow_iso = lambda: end_iso
        record_cash_movement(session, category="sale", amount_cents=2000)
    finally:
        finance_module.utcnow_iso = original_utcnow_iso

    response = stream_cash_movements_csv(session, start_iso, end_iso)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    # Only the start_iso row is in-period; the end_iso row is excluded.
    assert len(rows) == 2
    assert rows[1][3] == "10,00"


# --- route-level: /export page + three download routes (Task 2) ------------


def test_web_export_page_has_three_download_links(client):
    response = client.get("/export")
    assert response.status_code == 200
    body = response.text
    assert 'href="/export/products.csv"' in body
    assert 'href="/export/sales.csv"' in body
    assert 'href="/export/customers.csv"' in body
    # UI-SPEC hard rule: plain anchors only — htmx would break the native
    # Content-Disposition download by trying to swap the CSV into the DOM.
    assert 'hx-get="/export' not in body


def test_products_csv_roundtrip(client, product):
    response = client.get("/export/products.csv")
    assert response.status_code == 200
    assert "products.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    # D-01/Pitfall 4 (Phase 18 plan 02): the third (catalog) price column is
    # gone from the export header — PROD-05 collapses pricing to ДЦ/ПЦ only.
    assert rows[0] == [
        "Код",
        "Название",
        "Категория",
        "Закупка",
        "Продажа",
        "Остаток",
        "Удалён",
    ]
    assert "Каталог" not in rows[0]
    # Exactly one seeded product from the `product` fixture.
    assert len(rows) == 2
    assert rows[1][0] == product.code
    assert rows[1][1] == product.name


def test_sales_csv_roundtrip(client, session, product):
    """WR-02: content-level coverage for stream_sales_csv, incl. formula-injection-safe buyer name."""
    customer = Customer(
        id=new_id(),
        name="=cmd",
        surname="Тестова",
        consultant_number="99999",
        search_lc="=cmd тестова 99999",
    )
    session.add(customer)
    header = Sale(
        id=new_id(),
        customer_id=customer.id,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-2,
        unit_cost_cents=1000,
        unit_price_cents=1500,
        sale_id=header.id,
        batch_id=_ensure_batch(session, product),
    )
    session.commit()

    response = client.get("/export/sales.csv")
    assert response.status_code == 200
    assert "sales.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == [
        "Когда",
        "Код",
        "Товар",
        "Кол-во",
        "Цена",
        "Себестоимость",
        "Покупатель",
        "Кто",
    ]
    assert len(rows) == 2
    assert rows[1][1] == product.code
    assert rows[1][2] == product.name
    assert rows[1][3] == "2"
    # Formula-injection-prefixed customer name is escaped with a leading apostrophe.
    assert rows[1][6] == "'=cmd Тестова"
    assert rows[1][7] == settings.operator_name


def test_customers_csv_roundtrip(client, session):
    """WR-02 / CR-01: content-level coverage pinning consultant_number CSV escaping."""
    customer = Customer(
        id=new_id(),
        name="Пётр",
        surname="Сидоров",
        consultant_number="=cmd|'/C calc'!A0",
        search_lc="пётр сидоров",
    )
    session.add(customer)
    session.commit()

    response = client.get("/export/customers.csv")
    assert response.status_code == 200
    assert "customers.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Имя", "Фамилия", "Номер консультанта", "Создан"]
    assert len(rows) == 2
    assert rows[1][0] == "Пётр"
    assert rows[1][1] == "Сидоров"
    # CR-01: consultant_number is now escaped like every other free-text field.
    assert rows[1][2] == "'=cmd|'/C calc'!A0"


def test_web_export_ignores_client_params(client, product):
    baseline = client.get("/export/products.csv").content
    response = client.get("/export/products.csv?path=..%5Cevil&filename=x.csv")
    assert response.status_code == 200
    assert response.content == baseline
    assert "evil" not in response.text


def test_web_nav_has_export_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/export"' in response.text
    assert "Экспорт" in response.text
