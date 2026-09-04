"""OPS-04 executable contract for the /history browsing slice.

Interface contract for the Wave 5 history read service/route. Module path
and signature below are fixed — implement against them, do not rename.

This file is RED by design until app.services.operations lands: the module
import fails collection entirely (mirrors tests/test_sales.py from Phase 4).
Do NOT stub the service here.

Naming convention (used by -k filters, per 05-VALIDATION.md's
Requirements -> Test Map): route/e2e tests are prefixed test_web_;
everything else is service level. Selectors: rows, filters, pagination.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.core import business_date_bounds, local_today_iso, new_id, utcnow_iso
from app.models import Batch, Customer, Operation, Product, Sale, Warehouse
from app.services.batches import open_batches
from app.services.dashboard import recent_operations
from app.services.ledger import ledger_view, next_seq, record_operation
from app.services.operations import (  # noqa: F401
    _DEFAULT_ORDER,
    _SORT_MAP,
    HISTORY_TYPE_COLUMNS,
    history_view,
)
from app.services.transfers import register_transfer
from app.services.writeoffs import recent_writeoffs


def _batch_id(session, product):
    """First open batch id for a product (Phase 9 stock ops are batch-attributed)."""
    batches = open_batches(session, product.id)
    return batches[0].id if batches else None


def _seed_mixed_ops(session, product):
    """Seed a mix of batched op types on one product (writeoff/correction).

    Phase 9: stock ops carry a batch_id (the product's open batch) so these seeds
    survive the mandatory D-12 flip (Plan 09-05 Task 3)."""
    batch_id = _batch_id(session, product)
    record_operation(
        session, type_="writeoff", product_id=product.id, qty_delta=-1, batch_id=batch_id
    )
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=2, batch_id=batch_id
    )


def _insert_legacy_op(
    session,
    product,
    *,
    type_,
    qty_delta,
    created_at: str | None = None,
    business_date: str | None = None,
):
    """Insert a pre-Phase-9 (NULL batch_id) stock op directly, bypassing
    record_operation (which after the D-12 flip rejects a batch-less stock op).
    This is the legacy ledger shape /history must attribute at read time (D-15).

    Phase 33: two optional kwargs, both defaulting to today's exact behaviour
    (`created_at=utcnow_iso()`, `business_date` left NULL) — extended in place
    rather than duplicated, the same call 33-08 made for `conftest.past_sale`.
    `record_operation` can supply NEITHER: it always stamps
    `created_at=utcnow_iso()` and always substitutes today's local day for a
    missing business date, and the `operations_no_update` trigger ABORTs any
    later UPDATE. So a genuine DATE-08 NULL row and a row whose entry timestamp
    straddles the UTC/local day boundary can only be built by INSERT.
    The NULL batch_id is orthogonal noise for the date assertions — /history
    outerjoins Batch, so such a row is never dropped.
    """
    op = Operation(
        id=new_id(),
        type=type_,
        product_id=product.id,
        qty_delta=qty_delta,
        batch_id=None,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=created_at or utcnow_iso(),
        business_date=business_date,
        created_by=settings.operator_name,
    )
    session.add(op)
    product.quantity = Product.quantity + qty_delta
    session.commit()
    return op


# --- Service level ---


def test_history_pagination(session, stocked_product):
    """OPS-04/D-02: history_view returns <= page_size rows plus a real
    total/total_pages count — a bounded page, never the whole ledger, and
    never a `has_next` sentinel."""
    batch_id = _batch_id(session, stocked_product)
    for _ in range(5):
        record_operation(
            session,
            type_="correction",
            product_id=stocked_product.id,
            qty_delta=1,
            batch_id=batch_id,
        )
    # stocked_product already carries 1 receipt op from its fixture -> 6 rows total.

    first_page = history_view(session, page=0, page_size=3)
    assert len(first_page["rows"]) == 3
    assert first_page["total"] == 6
    assert first_page["total_pages"] == 2
    assert "has_next" not in first_page

    last_page = history_view(session, page=1, page_size=3)
    assert len(last_page["rows"]) == 3
    assert last_page["total"] == 6
    assert last_page["total_pages"] == 2
    assert "has_next" not in last_page


def test_history_view_sort_oldest_first(session, stocked_product):
    """D-06/D-07: sort="oldest" orders created_at asc, seq asc; the default
    (sort="") stays created_at desc, seq desc (unchanged)."""
    batch_id = _batch_id(session, stocked_product)
    for _ in range(3):
        record_operation(
            session,
            type_="correction",
            product_id=stocked_product.id,
            qty_delta=1,
            batch_id=batch_id,
        )

    default_result = history_view(session)
    oldest_result = history_view(session, sort="oldest")

    default_seqs = [r["op"].seq for r in default_result["rows"]]
    oldest_seqs = [r["op"].seq for r in oldest_result["rows"]]
    assert default_seqs == sorted(default_seqs, reverse=True)
    assert oldest_seqs == sorted(oldest_seqs)
    assert default_seqs == list(reversed(oldest_seqs))


# --- Web slice (routes + templates) ---


def test_web_history_rows(client, session, stocked_product):
    """OPS-04: GET /history returns all ops newest-first with product
    name/code, signed qty, reason, who, when, and RU type labels."""
    _seed_mixed_ops(session, stocked_product)

    response = client.get("/history")
    assert response.status_code == 200
    assert stocked_product.name in response.text
    assert stocked_product.code in response.text
    assert "Списание" in response.text  # OPERATION_TYPE_LABELS["writeoff"]
    assert "Корректировка" in response.text  # OPERATION_TYPE_LABELS["correction"]
    assert settings.operator_name in response.text


def test_web_history_filters(client, session, stocked_product, product, batch):
    """OPS-04/D-14: the type filter and the product filter each narrow
    results (portable ORM, no raw SQL).

    CR-01: since the fix, a filtered non-HX request renders the full page,
    whose filter-bar <select> unconditionally lists every RU type label /
    every active product as <option> text regardless of the active filter
    (that's normal <select> behavior, not a row match). So assertions must
    be scoped to the row markup (a `<td>`-prefixed occurrence) rather than a
    bare substring check, which would otherwise false-positive on the dropdown
    text. Since 09-07 the product code lives in its OWN «Код» column, so the
    «Товар» cell is now just `<td>{name}` (the muted D-15 batch second line
    still sits between the name and the closing tag; the code is no longer
    inlined here).

    Phase 23 (HIST-01/D-03): `type=writeoff` now renders the NARROWED
    per-type view (writeoff is a STOCK_AFFECTING_TYPES member), which drops
    the «Тип» column entirely — so the old Тип-label-based narrowing check
    is replaced by a «Код» cell count: exactly ONE row (the seeded writeoff)
    should carry `stocked_product`'s code, versus TWO before filtering
    (writeoff + correction, both narrowed types, both on the same product).
    """
    _seed_mixed_ops(session, stocked_product)
    # `batch` fixture seeds a batch for `product`; attribute its correction so
    # this seed also survives the D-12 flip.
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )

    unfiltered_response = client.get("/history")
    unfiltered_code_count = unfiltered_response.text.count(f"<td>{stocked_product.code}</td>")

    type_response = client.get("/history", params={"type": "writeoff"})
    assert type_response.status_code == 200
    assert type_response.text.count(f"<td>{stocked_product.code}</td>") == 1
    assert unfiltered_code_count > 1

    product_response = client.get("/history", params={"product": stocked_product.id})
    assert product_response.status_code == 200
    assert f"<td>{stocked_product.name}" in product_response.text
    assert f"<td>{product.name}" not in product_response.text


def test_web_history_filtered_reload_returns_full_chrome(client, session, stocked_product):
    """CR-01/OPS-04: a plain (non-htmx) top-level GET to /history that
    carries a type filter must render the full page chrome — not the
    chrome-less rows-only partial a real browser would drop per HTML5
    parsing rules — while filtering still narrows the displayed rows
    correctly (scoped to <td> row markup — see test_web_history_filters
    docstring for why a bare substring check is insufficient once the
    always-populated filter-bar <select> is present; Phase 23 HIST-01/D-03:
    `type=writeoff` is a narrowed per-type view with no «Тип» column, so
    narrowing is verified via the «Код» cell count instead)."""
    _seed_mixed_ops(session, stocked_product)

    response = client.get("/history", params={"type": "writeoff"})
    assert response.status_code == 200
    assert "<html" in response.text
    assert "<nav" in response.text
    assert "<table" in response.text
    assert response.text.count(f"<td>{stocked_product.code}</td>") == 1


def test_web_history_pagination_bar_reflects_filtered_total(client, session, stocked_product):
    """D-01/D-02/D-03: /history's "Показать ещё" load-more is retired in
    favor of page-number pagination — a filtered (>20-row) result set shows
    a numbered pagination bar whose "Страница X из Y" reflects the FILTERED
    total, not the whole ledger."""
    batch_id = _batch_id(session, stocked_product)
    for _ in range(25):
        record_operation(
            session,
            type_="writeoff",
            product_id=stocked_product.id,
            qty_delta=-1,
            batch_id=batch_id,
        )

    response = client.get("/history", params={"type": "writeoff"}, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert 'class="pagination"' in response.text
    assert "Страница 1 из 2" in response.text


# --- Batch attribution at read time (D-15) ---


def test_history_view_includes_batch(session, stocked_product):
    """D-15: history_view outer-joins Batch and every row dict carries a "batch"
    key — resolved for a batched op, None for a pre-Phase-9 (NULL batch_id) op."""
    _insert_legacy_op(session, stocked_product, type_="correction", qty_delta=1)

    result = history_view(session)
    rows = result["rows"]
    assert rows
    assert all("batch" in r for r in rows)

    # the fixture receipt is batched; the legacy correction is not.
    batched = [r for r in rows if r["op"].batch_id is not None]
    legacy = [r for r in rows if r["op"].batch_id is None]
    assert batched and batched[0]["batch"] is not None
    assert legacy and legacy[0]["batch"] is None


def test_web_history_null_batch_renders_legacy_label(client, session, stocked_product):
    """D-15: a stock op with NULL batch_id renders «До внедрения партий» at read
    time — the append-only ledger is never rewritten (no UPDATE issued)."""
    _insert_legacy_op(session, stocked_product, type_="writeoff", qty_delta=-1)

    response = client.get("/history")
    assert response.status_code == 200
    assert "До внедрения партий" in response.text


def test_web_history_batched_op_renders_batch_line(client, session, stocked_product):
    """D-15: a batched op renders «Партия: {expiry|без срока}{ — comment}» as a
    muted second line (the fixture receipt batch has no expiry -> «без срока»)."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "Партия:" in response.text
    assert "без срока" in response.text


def test_web_history_audit_op_has_no_batch_line(client, session, stocked_product):
    """D-15: an audit op (price_change) renders NO batch second line — neither a
    «Партия:» line nor the legacy label."""
    record_operation(session, type_="price_change", product_id=stocked_product.id, qty_delta=0)

    response = client.get("/history", params={"type": "price_change"})
    assert response.status_code == 200
    assert "<td>Изменение цены</td>" in response.text
    assert "Партия:" not in response.text
    assert "До внедрения партий" not in response.text


def test_web_history_table_has_10_columns(client, session, stocked_product):
    """09-07/Phase 14 D-04: /history has exactly 10 data columns — «Код» and
    «Действие» were added (Когда, Тип, Код, Товар, Кол-во, Цена,
    Себестоимость, Причина, Кто, Действие). The D-15 batch annotation is
    still a second line inside the «Товар» cell, not its own column. Since
    Phase 14, <thead> holds TWO <tr>s (10 header <th> + 10 filter-row <th>),
    so the total <th> count is 20.

    Phase 23 (HIST-01/D-03): the «Тип» select relocated OUT of the header
    filter-row into the top filter-bar (above <thead>, Interaction 7), so
    only ONE <select> (product) remains inside <thead> — the type select is
    verified separately via `id="type"` outside <thead>.
    """
    response = client.get("/history")
    assert response.status_code == 200
    assert 'id="type"' in response.text
    header_start = response.text.index("<thead>") + len("<thead>")
    header_end = response.text.index("</thead>", header_start)
    assert response.text.count("<th", header_start, header_end) == 20
    assert response.text.count("<select", header_start, header_end) == 1


def test_web_history_has_code_column_and_return_link(client, session, stocked_product):
    """09-07: /history exposes the product code in its own «Код» cell and every
    sale row carries a «Вернуть» link (same /returns?… shape as recent_sales.html)
    targeting the #return-slot — so a legacy sale is reachable and returnable from
    /history (the only view not capped at 10 recent sales)."""
    _seed_mixed_ops(session, stocked_product)
    # a sale op is what the «Вернуть» link renders for; seed one on the product.
    record_operation(
        session,
        type_="sale",
        product_id=stocked_product.id,
        qty_delta=-1,
        batch_id=_batch_id(session, stocked_product),
    )

    response = client.get("/history")
    assert response.status_code == 200
    # code renders in its own dedicated cell
    assert f"<td>{stocked_product.code}</td>" in response.text
    # sale-row return link + slot
    assert "/returns?sale_id=" in response.text
    assert "origin_op_id=" in response.text
    assert ">Вернуть<" in response.text
    assert 'id="return-slot"' in response.text


# --- HIST-02: customer/category/date-range filters (Plan 02 Task 1) ---


def test_history_category_filter_matches_cyrillic_substring(session, stocked_product):
    """D-27 mirror: a case-insensitive Cyrillic substring match against
    category_options() narrows rows to that category only."""
    stocked_product.category = "Уход за лицом"
    session.commit()

    other_warehouse = Warehouse(id=new_id(), name="Склад 2")
    session.add(other_warehouse)
    session.commit()
    other_product = Product(
        id=new_id(), code="OTH-001", name="Другой товар", category="Волосы", quantity=0
    )
    session.add(other_product)
    session.commit()
    other_batch = Batch(
        id=new_id(), product_id=other_product.id, warehouse_id=other_warehouse.id, quantity=0
    )
    session.add(other_batch)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=other_product.id, qty_delta=3, batch_id=other_batch.id
    )

    result = history_view(session, category="ЛИЦОМ")
    rows = result["rows"]
    assert rows
    assert all(r["product"].id == stocked_product.id for r in rows)


def test_history_customer_filter_noop_when_type_not_sale_or_return(
    session, stocked_product, customer, past_sale
):
    """D-05: a customer filter is IGNORED (not applied) for any type other
    than sale/return, even when a customer string is supplied."""
    past_sale(customer, stocked_product, created_at=utcnow_iso())
    batch_id = _batch_id(session, stocked_product)
    record_operation(
        session, type_="correction", product_id=stocked_product.id, qty_delta=1, batch_id=batch_id
    )

    unfiltered = history_view(session, type_filter="correction")
    with_customer = history_view(
        session, type_filter="correction", customer="совершенно-неизвестный-покупатель"
    )
    assert len(with_customer["rows"]) == len(unfiltered["rows"])
    assert len(unfiltered["rows"]) > 0


def test_history_customer_filter_narrows_sale_type(session, stocked_product, customer, past_sale):
    """D-05: for type_filter="sale", a customer filter narrows rows to that
    customer's sale ops only."""
    other_customer = Customer(id=new_id(), name="Борис", surname="Петров", search_lc="борис петров")
    session.add(other_customer)
    session.commit()

    past_sale(customer, stocked_product, created_at=utcnow_iso())
    past_sale(other_customer, stocked_product, created_at=utcnow_iso())

    result = history_view(session, type_filter="sale", customer="Иванова")
    rows = result["rows"]
    assert rows
    for row in rows:
        sale_id = row["op"].sale_id
        assert sale_id is not None
        sale_customer_id = session.execute(
            select(Sale.customer_id).where(Sale.id == sale_id)
        ).scalar_one()
        assert sale_customer_id == customer.id


def test_history_date_range_uses_closed_business_date_bounds(session, stocked_product):
    """Phase 33/DATE-03: the period filter is a CLOSED business-date range.

    Renamed from `test_history_date_range_excludes_outside_half_open_window`
    and re-pointed at the new contract (the same shape 33-07 applied to
    `test_expense_total_half_open_bounds`): the seeding instants and the
    outcome are unchanged — the 07-10 row is IN, the 07-11 row is OUT — but
    now for the correct reason. Both rows are inserted directly, so their
    `business_date` is NULL and `business_date_expr`'s COALESCE buckets them
    by `substr(created_at, 1, 10)` (DATE-08); the bounds are date-only days
    from `business_date_bounds`, not UTC timestamps.
    """
    batch_id = _batch_id(session, stocked_product)
    start_iso = "2026-07-10T00:00:00+00:00"
    end_iso = "2026-07-11T00:00:00+00:00"

    op_at_start = Operation(
        id=new_id(),
        type="correction",
        product_id=stocked_product.id,
        qty_delta=1,
        batch_id=batch_id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=start_iso,
        created_by=settings.operator_name,
    )
    session.add(op_at_start)
    op_at_end = Operation(
        id=new_id(),
        type="correction",
        product_id=stocked_product.id,
        qty_delta=1,
        batch_id=batch_id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=end_iso,
        created_by=settings.operator_name,
    )
    session.add(op_at_end)
    session.commit()

    day_start, day_end = business_date_bounds(date(2026, 7, 10), date(2026, 7, 10))
    result = history_view(session, start_iso=day_start, end_iso=day_end)
    ids = {r["op"].id for r in result["rows"]}
    assert op_at_start.id in ids
    assert op_at_end.id not in ids

    # Pitfall D (the closed contract): widening the range to 07-11 must PULL IN
    # the last day, not stop one short of it. A predicate that kept `<` passes
    # the assertions above and fails here.
    wide_start, wide_end = business_date_bounds(date(2026, 7, 10), date(2026, 7, 11))
    wide = history_view(session, start_iso=wide_start, end_iso=wide_end)
    wide_ids = {r["op"].id for r in wide["rows"]}
    assert op_at_start.id in wide_ids
    assert op_at_end.id in wide_ids


# --- HIST-01: HISTORY_TYPE_COLUMNS + Warehouse join + columns key (Plan 02 Task 2) ---


def test_history_view_columns_key_for_sale_type(session, stocked_product):
    """HIST-01: the "columns" key exposes the per-type column tuple for a
    STOCK_AFFECTING_TYPES member."""
    result = history_view(session, type_filter="sale")
    assert result["columns"] == HISTORY_TYPE_COLUMNS["sale"]


def test_history_view_columns_key_none_for_no_type_and_audit_type(session, stocked_product):
    """D-04/Pitfall 5: "columns" is None for no type filter AND for any of
    the 3 audit types (they fall back to the generic view)."""
    assert history_view(session)["columns"] is None
    assert history_view(session, type_filter="price_change")["columns"] is None


def test_history_view_rows_carry_warehouse_key(session, stocked_product):
    """Every row dict gains a "warehouse" key (present, possibly None)."""
    result = history_view(session)
    rows = result["rows"]
    assert rows
    assert all("warehouse" in r for r in rows)


def test_history_view_transfer_rows_carry_own_warehouse(session, product, batch, warehouse):
    """Pitfall 6 regression: a transfer's two sibling rows are NEVER merged
    into one "from -> to" record — each row independently carries its OWN
    batch/warehouse (the side it belongs to)."""
    dest_warehouse = Warehouse(id=new_id(), name="Склад назначения")
    session.add(dest_warehouse)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=5, batch_id=batch.id
    )

    result, errors = register_transfer(
        session,
        code=product.code,
        name=product.name,
        qty_raw="3",
        batch_id=batch.id,
        dest_warehouse_id=dest_warehouse.id,
    )
    assert errors == {}
    assert result is not None

    view = history_view(session, type_filter="transfer")
    rows = view["rows"]
    assert len(rows) == 2
    for row in rows:
        assert row["batch"] is not None
        assert row["warehouse"] is not None
        assert row["warehouse"].id == row["batch"].warehouse_id


# --- Phase 33 (DATE-03/DATE-04, D-22/D-24): the business-date period filter ---


def _backdated_correction(session, product, *, business_date: str, qty_delta: int = 1):
    """One correction op entered NOW but attributed to `business_date`.

    Goes through the single write path (`record_operation`), so `created_at`
    is genuinely today's timestamp while `business_date` is the operator's
    chosen day — exactly the shape DATE-03 is about.
    """
    return record_operation(
        session,
        type_="correction",
        product_id=product.id,
        qty_delta=qty_delta,
        batch_id=_batch_id(session, product),
        business_date=business_date,
    )


def test_history_period_filter_uses_business_date_not_entry_date(session, stocked_product):
    """VA-13/DATE-03: a row entered TODAY but back-dated is filtered by the day
    the goods moved, and is absent from its own entry day's period."""
    op = _backdated_correction(session, stocked_product, business_date="2026-07-10")

    in_start, in_end = business_date_bounds(date(2026, 7, 10), date(2026, 7, 10))
    in_ids = {r["op"].id for r in history_view(session, start_iso=in_start, end_iso=in_end)["rows"]}
    assert op.id in in_ids

    today = date.fromisoformat(local_today_iso(settings.display_tz))
    out_start, out_end = business_date_bounds(today, today)
    out_ids = {
        r["op"].id for r in history_view(session, start_iso=out_start, end_iso=out_end)["rows"]
    }
    assert op.id not in out_ids


def test_history_period_count_agrees_with_its_own_rows(session, stocked_product):
    """T-33-22: `history_view` carries the period predicate TWICE — once on
    `stmt` and once on `count_stmt`. Switching only one makes the pager's total
    disagree with the rows it paginates, and nothing but this assertion catches
    it (every other history test reads `rows` or `total`, never both)."""
    for _ in range(3):
        _backdated_correction(session, stocked_product, business_date="2026-07-10")
    # Noise strictly outside the period, on both sides.
    _backdated_correction(session, stocked_product, business_date="2026-07-09")
    _backdated_correction(session, stocked_product, business_date="2026-07-11")

    start, end = business_date_bounds(date(2026, 7, 10), date(2026, 7, 10))
    result = history_view(session, start_iso=start, end_iso=end)

    assert result["total"] == 3
    assert len(result["rows"]) == result["total"]
    assert result["total_pages"] == 1


def test_recent_feeds_still_order_by_created_at(session, stocked_product):
    """VA-17 (D-22/DATE-04): display ORDER did NOT move to the business date.

    The «recent N» feeds answer «что я только что ввёл?» — they are how the
    operator confirms an entry landed. A row entered now but back-dated a year
    must therefore still be FIRST in them; bucketing them by the business date
    would make a just-entered back-dated row silently vanish from the very list
    used to verify it was saved (T-33-23).

    Covers app/services/ledger.py::ledger_view (the actual recent-N feed —
    33-CONTEXT cites `ledger.py:234`, which is a `.limit(1)`; the feed is the
    `.order_by(created_at desc, seq desc).limit(50)` below it), plus
    app/services/dashboard.py::recent_operations and
    app/services/writeoffs.py::recent_writeoffs.
    """
    batch_id = _batch_id(session, stocked_product)
    on_time = record_operation(
        session,
        type_="writeoff",
        product_id=stocked_product.id,
        qty_delta=-1,
        batch_id=batch_id,
    )
    # Entered LAST, back-dated furthest into the past.
    backdated = record_operation(
        session,
        type_="writeoff",
        product_id=stocked_product.id,
        qty_delta=-1,
        batch_id=batch_id,
        business_date="2020-01-01",
    )
    assert backdated.business_date < on_time.business_date

    assert ledger_view(session)["operations"][0].id == backdated.id
    assert recent_operations(session)[0]["op"].id == backdated.id
    assert recent_writeoffs(session)[0]["op"].id == backdated.id

    # The sort allow-list itself is unchanged at its HEAD values (D-22): no
    # business-date sort option was added, and neither tuple was re-keyed.
    assert set(_SORT_MAP) == {"oldest"}
    assert [str(c) for c in _SORT_MAP["oldest"]] == [
        "operations.created_at ASC",
        "operations.seq ASC",
    ]
    assert [str(c) for c in _DEFAULT_ORDER] == [
        "operations.created_at DESC",
        "operations.seq DESC",
    ]


def test_history_default_order_is_unchanged_by_a_backdated_row(session, stocked_product):
    """D-22, at the /history read itself: the newest-ENTERED row leads the
    default view even when it is back-dated behind every other row."""
    _backdated_correction(session, stocked_product, business_date="2026-07-10")
    today = date.fromisoformat(local_today_iso(settings.display_tz))
    newest = _backdated_correction(
        session,
        stocked_product,
        business_date=(today - timedelta(days=900)).isoformat(),
    )

    assert history_view(session)["rows"][0]["op"].id == newest.id


def test_web_history_period_filter_selects_by_the_business_date(client, session, stocked_product):
    """DATE-03 through the REAL route: `?from=&to=` reaches the switched
    predicate with date-only bounds.

    The service-level tests call `history_view` with bounds a test built. Only
    this one proves the ROUTE hands it `business_date_bounds` output and not the
    old UTC-timestamp pair — a mismatch there silently returns an empty page at
    UTC and at any negative offset, with a 200 and no error anywhere.

    CR-01 (same trap `test_web_history_filters` documents): the «Товар» filter
    <select> lists EVERY active product's code as option text regardless of the
    active filter, so assertions must be scoped to the row markup
    (`<td>{code}</td>`), never a bare substring.
    """
    _backdated_correction(session, stocked_product, business_date="2026-07-10", qty_delta=7)
    cell = f"<td>{stocked_product.code}</td>"

    hit = client.get("/history?from=2026-07-10&to=2026-07-10")
    assert hit.status_code == 200
    assert hit.text.count(cell) == 1

    miss = client.get("/history?from=2026-08-01&to=2026-08-31")
    assert miss.status_code == 200
    assert miss.text.count(cell) == 0


# --- Phase 33 (DATE-05/DATE-06, D-18..D-21): the «задним числом» marker + filter ---


def _same_day_correction(session, product, qty_delta: int = 1):
    """One correction entered NOW and attributed to today — the unmarked shape."""
    return record_operation(
        session,
        type_="correction",
        product_id=product.id,
        qty_delta=qty_delta,
        batch_id=_batch_id(session, product),
    )


def test_history_rows_carry_business_day_and_is_backdated(session, stocked_product):
    """DATE-05/DATE-06: the two row-dict keys BOTH surfaces consume."""
    marked = _backdated_correction(session, stocked_product, business_date="2026-07-10")
    plain = _same_day_correction(session, stocked_product)
    by_id = {r["op"].id: r for r in history_view(session)["rows"]}

    assert by_id[marked.id]["business_day"] == "2026-07-10"
    assert by_id[marked.id]["is_backdated"] is True

    assert by_id[plain.id]["business_day"] == local_today_iso(settings.display_tz)
    assert by_id[plain.id]["is_backdated"] is False


def test_history_null_business_date_row_is_never_marked(session, stocked_product):
    """DATE-08: a row pushed by a pre-0027 client has business_date NULL. It was
    not back-dated — it simply predates the column — so it must carry NO marker
    and render byte-identically to today."""
    legacy = _insert_legacy_op(session, stocked_product, type_="correction", qty_delta=1)

    row = next(r for r in history_view(session)["rows"] if r["op"].id == legacy.id)
    assert row["op"].business_date is None
    assert row["business_day"] is None
    assert row["is_backdated"] is False


def test_history_dated_backdated_returns_only_backdated_rows(session, stocked_product):
    """DATE-06: «Только задним числом». T-33-22 — the predicate lands on BOTH
    `stmt` and `count_stmt`, and only `len(rows) == total` can catch a half-switch."""
    marked = _backdated_correction(session, stocked_product, business_date="2026-07-10")
    _same_day_correction(session, stocked_product)
    _insert_legacy_op(session, stocked_product, type_="correction", qty_delta=1)

    result = history_view(session, dated="backdated")

    assert {r["op"].id for r in result["rows"]} == {marked.id}
    assert result["total"] == 1
    assert len(result["rows"]) == result["total"]


def test_history_dated_same_day_returns_only_same_day_rows(session, stocked_product):
    """DATE-06: «Только в день операции» — the exact negation, back-dated rows out."""
    marked = _backdated_correction(session, stocked_product, business_date="2026-07-10")
    plain = _same_day_correction(session, stocked_product)

    result = history_view(session, dated="same_day")
    ids = {r["op"].id for r in result["rows"]}

    assert plain.id in ids
    assert marked.id not in ids
    assert len(result["rows"]) == result["total"]
    assert all(r["is_backdated"] is False for r in result["rows"])


def test_history_dated_null_business_date_counts_as_same_day(session, stocked_product):
    """DATE-08 inside the filter: `NULL != x` is NULL in SQL, so a naive negation
    would VANISH every pre-0027 row from both halves of the filter. It belongs to
    «Только в день операции» — it was not back-dated."""
    legacy = _insert_legacy_op(session, stocked_product, type_="correction", qty_delta=1)

    same_day = history_view(session, dated="same_day")
    assert legacy.id in {r["op"].id for r in same_day["rows"]}
    assert len(same_day["rows"]) == same_day["total"]

    backdated = history_view(session, dated="backdated")
    assert legacy.id not in {r["op"].id for r in backdated["rows"]}
    assert len(backdated["rows"]) == backdated["total"]


def test_history_dated_unknown_value_behaves_as_all(session, stocked_product):
    """T-33-35: the allow-list discipline of `_SORT_MAP.get(sort, default)`. An
    unknown or tampered value selects NO predicate — it is never interpolated
    into a query — and is echoed back normalised so the <select> shows «Все»."""
    _backdated_correction(session, stocked_product, business_date="2026-07-10")
    _same_day_correction(session, stocked_product)

    unfiltered = history_view(session)
    tampered = history_view(session, dated="'; DROP TABLE operations; --")

    assert {r["op"].id for r in tampered["rows"]} == {r["op"].id for r in unfiltered["rows"]}
    assert tampered["total"] == unfiltered["total"]
    assert tampered["dated"] == ""
    # The table is still there — the string never reached SQL.
    assert session.scalar(select(Operation.id).limit(1)) is not None


def test_history_view_echoes_the_dated_filter(session, stocked_product):
    """D-20: without `"dated"` in the result dict the fourth <select> cannot
    re-select itself after an htmx outerHTML swap."""
    assert history_view(session, dated="backdated")["dated"] == "backdated"
    assert history_view(session, dated="same_day")["dated"] == "same_day"
    assert history_view(session)["dated"] == ""


def test_web_history_dated_filter_survives_pagination(client, session, stocked_product):
    """HIST-02 through the REAL route: `qs_parts` must carry `dated` onto every
    pagination link, or clicking page 2 silently drops the filter and shows the
    unfiltered page — a 200 with quietly wrong rows and no error anywhere."""
    # LIST_PAGE_SIZE is 20. 21 back-dated + 20 same-day + the fixture's own
    # receipt = 42 rows unfiltered (3 pages) vs 21 filtered (2 pages), so BOTH
    # the page count and the last page's row count catch a dropped filter.
    for _ in range(21):
        _backdated_correction(session, stocked_product, business_date="2026-07-10")
    for _ in range(20):
        _same_day_correction(session, stocked_product)
    cell = f"<td>{stocked_product.code}</td>"

    page_one = client.get("/history?dated=backdated")
    assert page_one.status_code == 200
    assert "dated=backdated" in page_one.text  # re-serialised onto the pagination links
    assert page_one.text.count(cell) == 20
    assert "Страница 1 из 2" in page_one.text

    page_two = client.get("/history?dated=backdated&page=1", headers={"HX-Request": "true"})
    assert page_two.status_code == 200
    # Page 2 holds exactly the 21st back-dated row. With the filter dropped it
    # would hold 20 rows and read «Страница 2 из 3».
    assert page_two.text.count(cell) == 1
    assert "Страница 2 из 2" in page_two.text


def test_backdated_filter_and_marker_diverge_only_on_utc_straddle(
    session, stocked_product, monkeypatch
):
    """The ONE accepted disagreement between the marker and the filter — CHOSEN,
    not overlooked (33-14 locked decision §2, `33-UI-SPEC.md` § Interaction
    Contract §6).

    The marker compares `business_date` against the LOCAL calendar day of
    `created_at`; the SQL filter compares it against `substr(created_at, 1, 10)`,
    the UTC day, because a local day is not expressible in portable ORM
    (`datetime(created_at, '+3 hours')` on SQLite, `created_at::date` on
    PostgreSQL — both banned by CLAUDE.md PC-2), and a stored marker column is
    out (append-only ledger, only four columns land this phase).

    Consequence, in ONE direction only: a row entered in the window where the
    local day and the UTC day differ IS returned by «Только задним числом» and
    is NOT marked. The marker is the correct one there. The converse never
    happens — no marked row is ever lost by the filter — and THAT is why this is
    the smaller of the two errors: a filter showing a few extra rows is subtler
    than a marker contradicting the date printed beside it. Computing the marker
    in Python after the page was fetched would make `total` disagree with the
    rows and break pagination.
    """
    monkeypatch.setattr(settings, "display_tz", "Europe/Moscow")
    # 22:00 UTC on 2026-07-10 is 01:00 LOCAL on 2026-07-11 at Europe/Moscow
    # (UTC+3): the operator entered this on their own 11th, and attributed it to
    # the 11th. UTC day 2026-07-10, local day 2026-07-11.
    straddler = _insert_legacy_op(
        session,
        stocked_product,
        type_="correction",
        qty_delta=1,
        created_at="2026-07-10T22:00:00+00:00",
        business_date="2026-07-11",
    )
    marked = _backdated_correction(session, stocked_product, business_date="2026-07-10")

    unfiltered = {r["op"].id: r for r in history_view(session)["rows"]}
    # The marker is right: entered on its own local day, so NOT back-dated.
    assert unfiltered[straddler.id]["is_backdated"] is False
    assert unfiltered[marked.id]["is_backdated"] is True

    result = history_view(session, dated="backdated")
    returned = {r["op"].id: r for r in result["rows"]}
    assert len(result["rows"]) == result["total"]

    # The filter over-includes the straddler — the documented, accepted edge.
    assert straddler.id in returned
    assert returned[straddler.id]["is_backdated"] is False

    # The converse never happens: EVERY marked row is inside «Только задним числом».
    assert {op_id for op_id, r in unfiltered.items() if r["is_backdated"]} <= set(returned)
