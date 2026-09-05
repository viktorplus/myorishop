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
and app/routes/backup.py), WITH ONE BOUNDED EXCEPTION: stream_cash_movements_csv
(FIN-09/D-03b) accepts a VALIDATED calendar start_day/end_day range, clamped
upstream by _resolve_period before this module ever sees it, and consumes it
ONLY as an ORM `.where(business_date_expr(CashMovement) ...)` bound — never as
a filename, path, or arbitrary string. This is a documented, bounded
relaxation for period-scoped export, not a general "exports may take
arbitrary params" policy. T-06-10: _csv_safe prefixes any free-text value
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
from app.core import DEFAULT_CURRENCY, format_cents, format_ru_date, iso_to_local
from app.models import (
    CASH_CATEGORIES,
    Batch,
    CashMovement,
    Customer,
    Operation,
    Product,
    Sale,
    Warehouse,
)
from app.services.reports import business_date_expr

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
    # D-01/Pitfall 4 (Phase 18 plan 02): the third (catalog) price column is
    # dropped from this export — PROD-05 collapses product pricing to ДЦ/ПЦ
    # only (T-18-CSV: this REDUCES the exported surface; every remaining cell
    # stays _csv_safe-wrapped).
    header = [
        "Код",
        "Название",
        "Категория",
        "Закупка",
        "Продажа",
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
        select(Operation, Product, Sale, Customer, Warehouse.currency)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .outerjoin(Batch, Operation.batch_id == Batch.id)
        .outerjoin(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Operation.type == "sale")
        # D-23: column 1 «Когда» carries the BUSINESS date, so the dump must be
        # ordered by it — otherwise it reads as unsorted by its own first column.
        # created_at and seq are deterministic tie-breakers within one day.
        .order_by(business_date_expr(Operation), Operation.created_at, Operation.seq)
    )
    # D-23: «Когда» reads as «когда это случилось», so column 1 carries the
    # BUSINESS date and the entry timestamp is appended LAST as «Внесено».
    # ACCEPTED COST, stated so nobody "fixes" it later: column 1's value TYPE
    # narrows from "dd.mm.yyyy HH:MM" to "dd.mm.yyyy" — the HH:MM reappears
    # verbatim in «Внесено». Positions 1..N do NOT shift (the new header is
    # LAST), so an existing spreadsheet formula over Код / Цена / Сумма keeps
    # working.
    header = [
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
    rows = []
    for op, product, sale, customer, row_currency in session.execute(query).all():
        buyer = ""
        # Sale row may itself be None for very old/malformed data.
        if sale and customer:
            buyer = _csv_safe(f"{customer.name} {customer.surname or ''}".strip())
        rows.append(
            [
                # DATE-08: the NULL fallback is the UTC prefix DELIBERATELY —
                # it matches the func.coalesce(business_date,
                # substr(created_at, 1, 10)) this row set was selected and
                # ordered by, so column 1 can never contradict the file's own
                # period. A backfilled row is unaffected (its business date is
                # the tz-correct local day).
                #
                # WR-04 (33-REVIEW): wrapped in `_csv_safe` because this cell is
                # no longer a guaranteed `dd.mm.yyyy`. Before Phase 33 column 1
                # was `iso_to_local(...)`, which could only ever produce a
                # timestamp — genuinely not free text. Both date filters now
                # return the STORED value verbatim on anything they do not
                # recognise (the CR-01 «display never raises» rule), so both are
                # pass-throughs of stored bytes and belong under the same
                # T-06-10 wrapper as every other free-text cell in this file.
                # A well-formed date never starts with =/+/-/@, so not one byte
                # of existing output changes.
                _csv_safe(format_ru_date(op.business_date or op.created_at[:10])),
                _csv_safe(product.code or ""),
                _csv_safe(product.name),
                -op.qty_delta,
                format_cents(op.unit_price_cents) if op.unit_price_cents is not None else "",
                format_cents(op.unit_cost_cents) if op.unit_cost_cents is not None else "",
                # CUR-02/LOCKED: a NULL-batch legacy row is RUB, same fallback
                # rule as app.services.reports.operation_currency_clause.
                row_currency or DEFAULT_CURRENCY,
                buyer,
                op.created_by,
                # WR-04, same rule: `iso_to_local` is a pass-through too now.
                _csv_safe(iso_to_local(op.created_at, settings.display_tz)),
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
            # WR-04, same rule: `iso_to_local` is a pass-through too now.
            _csv_safe(iso_to_local(customer.created_at, settings.display_tz)),
        ]
        for customer in customers
    ]
    return StreamingResponse(
        _encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


def stream_cash_movements_csv(
    session: Session, start_day: str, end_day: str
) -> StreamingResponse:
    """Period-scoped cash-movement dump, oldest-first (FIN-09/D-03).

    D-03b: the ONLY export in this module accepting a filter — start_day/
    end_day are a VALIDATED calendar range clamped upstream by
    _resolve_period, consumed ONLY as an ORM
    `.where(business_date_expr(CashMovement) ...)` bound.
    Every existing export convention stays intact (D-03a): reuses
    _encode_once/_csv_rows/_csv_safe verbatim (one UTF-8 BOM, ";" delimiter,
    formula-injection escape on every free-text cell).

    Phase 33 (DATE-03/DATE-05): the row set is chosen by the BUSINESS date,
    not the entry timestamp — so the file's headline «Когда» column can never
    contradict the period the file was selected for. The bounds are therefore
    DATE-ONLY ISO strings from `core.business_date_bounds` (yyyy-mm-dd) over
    its CLOSED contract (`>= start_day` AND `<= end_day`, never `<`), NOT the
    UTC timestamp bounds `local_day_bounds_utc` produces. Both callers
    (app/routes/finance.py, app/routes/mobile_finance.py) flipped to
    `business_date_bounds` in the same commit as this predicate — handing this
    a timestamp bound is the T-33-20 half-switch, which "works" at
    Europe/Moscow by lexicographic accident and drops every row at UTC and any
    negative offset.
    """
    business_day = business_date_expr(CashMovement)
    movements = session.scalars(
        select(CashMovement)
        .where(
            business_day >= start_day,
            business_day <= end_day,
        )
        # D-23 / CD-9: the twin of stream_sales_csv's ORDER BY — column 1 is
        # the business date, so the dump must be ordered by it or it reads as
        # unsorted by its own first column.
        .order_by(business_day, CashMovement.created_at, CashMovement.seq)
    ).all()
    # D-23, identical rule and identical accepted cost as stream_sales_csv
    # above: column 1 becomes the BUSINESS date, the entry timestamp is
    # appended LAST as «Внесено», and positions 1..N do not shift.
    header = ["Когда", "Категория", "Валюта", "Комментарий", "Сумма", "Внесено"]
    rows = [
        [
            # DATE-08: same deliberate UTC-prefix fallback as stream_sales_csv
            # — it mirrors the COALESCE this row set was selected by.
            # WR-04 (33-REVIEW): `_csv_safe` for the same reason as the twin in
            # stream_sales_csv above — `format_ru_date` is a pass-through of the
            # stored value on anything it does not recognise.
            _csv_safe(format_ru_date(movement.business_date or movement.created_at[:10])),
            _csv_safe(CASH_CATEGORIES.get(movement.category, movement.category)),
            movement.currency,
            _csv_safe(movement.note or ""),
            format_cents(movement.amount_cents),
            # WR-04, same rule: `iso_to_local` is a pass-through too now.
            _csv_safe(iso_to_local(movement.created_at, settings.display_tz)),
        ]
        for movement in movements
    ]
    return StreamingResponse(
        _encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cash_movements.csv"},
    )
