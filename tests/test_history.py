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

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Operation, Product
from app.services.batches import open_batches
from app.services.ledger import next_seq, record_operation
from app.services.operations import history_view  # noqa: F401


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


def _insert_legacy_op(session, product, *, type_, qty_delta):
    """Insert a pre-Phase-9 (NULL batch_id) stock op directly, bypassing
    record_operation (which after the D-12 flip rejects a batch-less stock op).
    This is the legacy ledger shape /history must attribute at read time (D-15)."""
    op = Operation(
        id=new_id(),
        type=type_,
        product_id=product.id,
        qty_delta=qty_delta,
        batch_id=None,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
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
    """
    _seed_mixed_ops(session, stocked_product)
    # `batch` fixture seeds a batch for `product`; attribute its correction so
    # this seed also survives the D-12 flip.
    record_operation(
        session, type_="correction", product_id=product.id, qty_delta=1, batch_id=batch.id
    )

    type_response = client.get("/history", params={"type": "writeoff"})
    assert type_response.status_code == 200
    assert "<td>Списание</td>" in type_response.text
    assert "<td>Корректировка</td>" not in type_response.text

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
    always-populated filter-bar <select> is present)."""
    _seed_mixed_ops(session, stocked_product)

    response = client.get("/history", params={"type": "writeoff"})
    assert response.status_code == 200
    assert "<html" in response.text
    assert "<nav" in response.text
    assert "<table" in response.text
    assert "<td>Списание</td>" in response.text
    assert "<td>Корректировка</td>" not in response.text


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

    response = client.get(
        "/history", params={"type": "writeoff"}, headers={"HX-Request": "true"}
    )
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
    record_operation(
        session, type_="price_change", product_id=stocked_product.id, qty_delta=0
    )

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
    Phase 14, <thead> holds TWO <tr>s (10 header <th> + 10 filter-row <th>,
    D-04 moves the type/product filters into the header-row shape), so the
    total <th> count is now 20; exactly 2 of the filter-row cells hold a
    <select> (type, product)."""
    response = client.get("/history")
    assert response.status_code == 200
    header_start = response.text.index("<thead>") + len("<thead>")
    header_end = response.text.index("</thead>", header_start)
    assert response.text.count("<th", header_start, header_end) == 20
    assert response.text.count("<select", header_start, header_end) == 2


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
