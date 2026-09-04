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
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.core import business_date_bounds, local_day_bounds_utc, new_id, utcnow_iso
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


def _local_day_of(iso: str) -> str:
    """tz-correct LOCAL day of a UTC timestamp — mirrors tests/test_reports.py.

    Phase 33 (DATE-03): reproduces exactly what migration 0027 backfills for a
    pre-existing row, so a fixture with a historical `created_at` keeps the
    period it always meant instead of landing in TODAY's bucket (the write
    path stamps today's local day when `business_date` is not given).
    """
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(TZ)).date().isoformat()


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
    start_day, end_day = business_date_bounds(DAY, DAY)
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
            business_date=_local_day_of(mid),
        )
        record_cash_movement(
            session,
            category="sale",
            amount_cents=3000,
            business_date=_local_day_of(mid),
        )
    finally:
        finance_module.utcnow_iso = original_utcnow_iso

    response = stream_cash_movements_csv(session, start_day, end_day)
    body = _stream_body(response)
    assert body.count(b"\xef\xbb\xbf") == 1

    text = body.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Когда", "Категория", "Валюта", "Комментарий", "Сумма", "Внесено"]
    assert len(rows) == 3
    # Oldest-first: both rows share the same timestamp, insertion order holds.
    assert rows[1][1] == "Оплата поставщику"
    assert rows[1][2] == "RUB"
    assert rows[1][3] == "Оплата"
    assert rows[1][4] == "-12,00"
    assert rows[2][1] == "Продажа"
    assert rows[2][2] == "RUB"
    assert rows[2][3] == ""
    assert rows[2][4] == "30,00"


def test_cash_movements_csv_null_note_renders_empty(session, monkeypatch):
    start_day, end_day = business_date_bounds(DAY, DAY)
    mid = "2026-07-10T10:00:00+00:00"
    monkeypatch.setattr("app.services.finance.utcnow_iso", lambda: mid)
    record_cash_movement(
        session, category="sale", amount_cents=1000, business_date=_local_day_of(mid)
    )

    response = stream_cash_movements_csv(session, start_day, end_day)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][3] == ""
    assert "None" not in text


def test_cash_movements_csv_escapes_formula_injection_note(session, monkeypatch):
    start_day, end_day = business_date_bounds(DAY, DAY)
    mid = "2026-07-10T10:00:00+00:00"
    monkeypatch.setattr("app.services.finance.utcnow_iso", lambda: mid)
    record_cash_movement(
        session,
        category="withdrawal_other",
        amount_cents=-100,
        note="=CMD()",
        business_date=_local_day_of(mid),
    )

    response = stream_cash_movements_csv(session, start_day, end_day)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][3] == "'=CMD()"


def test_cash_movements_csv_closed_period_and_order(session):
    """Phase 33 (DATE-03): the row set is the CLOSED business-date range.

    Renamed from *_half_open_period_and_order and re-pointed at the new
    contract. The two seeding INSTANTS are unchanged — `local_day_bounds_utc`
    is still the sanctioned way to build a `created_at` that straddles local
    midnight — but the export now selects on `business_date_expr`, so the
    boundary being exercised is «the last day of the range is INCLUDED, the
    next local day is not», not «the upper timestamp bound is exclusive».

    The two instants are local 2026-07-10 00:00 and local 2026-07-11 00:00, so
    their tz-correct business dates land one inside and one outside the
    single-day period — the same two rows, the same outcome, for the correct
    reason.
    """
    created_in, created_out = local_day_bounds_utc(DAY, DAY, TZ)
    start_day, end_day = business_date_bounds(DAY, DAY)

    import app.services.finance as finance_module

    original_utcnow_iso = finance_module.utcnow_iso
    try:
        finance_module.utcnow_iso = lambda: created_in
        record_cash_movement(
            session,
            category="sale",
            amount_cents=1000,
            business_date=_local_day_of(created_in),
        )
        finance_module.utcnow_iso = lambda: created_out
        record_cash_movement(
            session,
            category="sale",
            amount_cents=2000,
            business_date=_local_day_of(created_out),
        )
    finally:
        finance_module.utcnow_iso = original_utcnow_iso

    # Pin the fixture's own premise, so the assertion below cannot pass for the
    # wrong reason if the tz conversion ever moves.
    assert _local_day_of(created_in) == end_day
    assert _local_day_of(created_out) > end_day

    response = stream_cash_movements_csv(session, start_day, end_day)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    # The row ON the last day of the range is INCLUDED (closed contract); the
    # next local day's row is excluded.
    assert len(rows) == 2
    assert rows[1][4] == "10,00"


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
        "Валюта",
        "Покупатель",
        "Кто",
        "Внесено",
    ]
    assert len(rows) == 2
    assert rows[1][1] == product.code
    assert rows[1][2] == product.name
    assert rows[1][3] == "2"
    # CUR-02: the sold batch's warehouse currency (default RUB via _ensure_batch).
    assert rows[1][6] == "RUB"
    # Formula-injection-prefixed customer name is escaped with a leading apostrophe.
    assert rows[1][7] == "'=cmd Тестова"
    assert rows[1][8] == settings.operator_name


def test_sales_csv_labels_non_default_currency(client, session, product):
    """CUR-02: a sale whose batch lives in a non-RUB warehouse is labelled correctly."""
    eur_wh = Warehouse(id=new_id(), name="Склад EUR", currency="EUR")
    session.add(eur_wh)
    session.flush()
    eur_batch = Batch(id=new_id(), product_id=product.id, warehouse_id=eur_wh.id, quantity=0)
    session.add(eur_batch)
    header = Sale(
        id=new_id(), customer_id=None, created_at=utcnow_iso(), created_by=settings.operator_name
    )
    session.add(header)
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_cost_cents=500,
        unit_price_cents=800,
        sale_id=header.id,
        batch_id=eur_batch.id,
    )
    session.commit()

    response = client.get("/export/sales.csv")
    text = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][6] == "EUR"


def test_cash_movements_csv_labels_non_default_currency(session):
    """CUR-02: a cash movement recorded with currency=EUR is labelled correctly."""
    start_day, end_day = business_date_bounds(DAY, DAY)
    mid = "2026-07-10T10:00:00+00:00"
    import app.services.finance as finance_module

    original_utcnow_iso = finance_module.utcnow_iso
    finance_module.utcnow_iso = lambda: mid
    try:
        record_cash_movement(
            session,
            category="sale",
            amount_cents=1000,
            currency="EUR",
            business_date=_local_day_of(mid),
        )
    finally:
        finance_module.utcnow_iso = original_utcnow_iso

    response = stream_cash_movements_csv(session, start_day, end_day)
    text = _stream_body(response).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[1][2] == "EUR"


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


def test_web_export_links_embedded_in_backup_page(client):
    response = client.get("/backup")
    assert response.status_code == 200
    assert 'href="/export/products.csv"' in response.text
    assert "Экспорт" in response.text
