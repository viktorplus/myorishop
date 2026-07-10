"""Export service (BCK-02, D-06/D-07): full-table CSV dumps, streamed.

D-07: each of the three streams is a StreamingResponse whose byte stream
carries EXACTLY ONE UTF-8 BOM (b"\\xef\\xbb\\xbf") at the very start —
encoding every chunk with utf-8-sig (rather than utf-8) would repeat the
BOM per chunk and corrupt the file; _encode_once is the BOM-once seam.
RESEARCH Pitfall 4: rows use ";" as the csv delimiter (never ","), because
this app already formats money with a comma decimal separator ("12,50")
which would otherwise collide with a comma row delimiter and split Excel's
RU-locale auto-import into the wrong columns.

Security T-06-09: no function here accepts a filename, path, or any other
externally-supplied parameter — every export is a full, unfiltered table
dump (matches the V12 pattern already established by app/services/backup.py
and app/routes/backup.py). T-06-10: _csv_safe prefixes any free-text value
starting with =, +, -, or @ with a leading apostrophe so Excel never
interprets it as a formula on open (CSV/formula-injection hardening).
"""

import csv
import io
from collections.abc import Generator

from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import format_cents, iso_to_local
from app.models import Customer, Operation, Product, Sale

_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _csv_safe(value: str) -> str:
    """T-06-10: prefix a leading formula-injection character with an apostrophe."""
    if value and value[0] in _INJECTION_PREFIXES:
        return "'" + value
    return value


def _csv_rows(header: list[str], rows: list[list]) -> Generator[str]:
    """Yield one CSV text chunk per row (header first), delimiter ";" (Pitfall 4)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def _encode_once(text_chunks) -> Generator[bytes]:
    """D-07: encode the FIRST chunk with utf-8-sig, every later chunk with utf-8.

    Encoding every chunk with utf-8-sig would repeat the BOM once per chunk
    and corrupt the file when reassembled by the browser/Excel.
    """
    first = True
    for chunk in text_chunks:
        if first:
            yield chunk.encode("utf-8-sig")
            first = False
        else:
            yield chunk.encode("utf-8")


def stream_products_csv(session: Session) -> StreamingResponse:
    """Full product catalog dump, including soft-deleted (BCK-02 full dump)."""
    products = session.scalars(select(Product).order_by(Product.name_lc)).all()
    header = [
        "Код",
        "Название",
        "Категория",
        "Закупка",
        "Продажа",
        "Каталог",
        "Остаток",
        "Удалён",
    ]
    rows = [
        [
            _csv_safe(product.code or ""),
            _csv_safe(product.name),
            _csv_safe(product.category or ""),
            format_cents(product.cost_cents) if product.cost_cents is not None else "",
            format_cents(product.sale_cents) if product.sale_cents is not None else "",
            format_cents(product.catalog_cents) if product.catalog_cents is not None else "",
            product.quantity,
            "Да" if product.deleted_at else "",
        ]
        for product in products
    ]
    return StreamingResponse(
        _encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


def stream_sales_csv(session: Session) -> StreamingResponse:
    """Full sale-operation dump, oldest-first (a data dump reads best chronologically —

    diverges from the newest-first UI listings elsewhere in this app).
    """
    query = (
        select(Operation, Product, Sale, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at)
    )
    header = ["Когда", "Код", "Товар", "Кол-во", "Цена", "Себестоимость", "Покупатель", "Кто"]
    rows = []
    for op, product, sale, customer in session.execute(query).all():
        buyer = ""
        # Sale row may itself be None for very old/malformed data.
        if sale and customer:
            buyer = _csv_safe(f"{customer.name} {customer.surname or ''}".strip())
        rows.append(
            [
                iso_to_local(op.created_at, settings.display_tz),
                _csv_safe(product.code or ""),
                _csv_safe(product.name),
                -op.qty_delta,
                format_cents(op.unit_price_cents) if op.unit_price_cents is not None else "",
                format_cents(op.unit_cost_cents) if op.unit_cost_cents is not None else "",
                buyer,
                op.created_by,
            ]
        )
    return StreamingResponse(
        _encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales.csv"},
    )


def stream_customers_csv(session: Session) -> StreamingResponse:
    """Full customer profile dump."""
    customers = session.scalars(select(Customer).order_by(Customer.search_lc)).all()
    header = ["Имя", "Фамилия", "Номер консультанта", "Создан"]
    rows = [
        [
            _csv_safe(customer.name),
            _csv_safe(customer.surname or ""),
            _csv_safe(customer.consultant_number or ""),
            iso_to_local(customer.created_at, settings.display_tz),
        ]
        for customer in customers
    ]
    return StreamingResponse(
        _encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )
