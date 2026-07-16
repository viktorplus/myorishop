"""OPS-01 executable contract for the write-off slice.

Interface contract for the Wave 2 write-off service/route. Module path and
signatures below are fixed — implement against them, do not rename.

This file is RED by design until app.services.writeoffs lands: the module
import fails collection entirely (mirrors tests/test_sales.py from Phase 4).
Do NOT stub the service here — the whole point of Wave 0 is a failing
contract that a later wave turns green.

Naming convention (used by -k filters, per 05-VALIDATION.md's
Requirements -> Test Map): route/e2e tests are prefixed test_web_;
everything else is service level. Selectors: stock_and_reason,
reason_allowlist, form, oversell.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import WRITEOFF_REASONS, Batch, Operation, Product, Warehouse
from app.services.batches import open_batches
from app.services.ledger import compute_stock, record_operation
from app.services.writeoffs import register_writeoff  # noqa: F401


def _writeoff_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "writeoff")).all()


def _only_batch(session, product):
    """The single open batch of a fixture product (LOT-05: write-off needs one)."""
    return open_batches(session, product.id)[0]


def _two_batch_product(session):
    """A product with batch A (qty 2) and batch B (qty 10); total 12.

    The picked batch's remaining (2) is deliberately far below the product
    total (12) so a per-batch over-removal warning cannot be faked by a
    product-scoped check (criterion 4 is batch-scoped, D-09)."""
    product = Product(id=new_id(), code="MB-001", name="Многопартийный", quantity=0)
    session.add(product)
    warehouse = Warehouse(id=new_id(), name="Склад МБ")
    session.add(warehouse)
    session.commit()
    batch_a = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    batch_b = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add_all([batch_a, batch_b])
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=2, batch_id=batch_a.id
    )
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=10, batch_id=batch_b.id
    )
    session.expire_all()
    return product, batch_a, batch_b


# --- Service level ---


def test_stock_and_reason(session, stocked_product):
    """OPS-01: a write-off writes a `writeoff` op (qty_delta<0); Product.quantity
    AND compute_stock() both drop by qty; the reason is persisted in payload
    as exactly {reason_code, note}. LOT-05: the picked Batch.quantity drops too."""
    batch = _only_batch(session, stocked_product)
    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="3",
        reason_code="expired",
        note="",
        batch_id=batch.id,
    )
    assert errors == {}
    assert result

    ops = _writeoff_ops(session)
    assert len(ops) == 1
    op = ops[0]
    assert op.qty_delta == -3
    assert op.batch_id == batch.id
    assert op.payload == {"reason_code": "expired", "note": ""}

    session.expire_all()
    assert stocked_product.quantity == 8 - 3
    assert compute_stock(session, stocked_product.id) == 8 - 3
    assert batch.quantity == 8 - 3  # the picked batch decremented (LOT-05)


def test_reason_allowlist(session, stocked_product):
    """OPS-01: a reason_code NOT in WRITEOFF_REASONS is rejected server-side
    (the authoritative allow-list — never trust the <select>); 0 writes."""
    assert "not-a-real-reason" not in WRITEOFF_REASONS

    batch = _only_batch(session, stocked_product)
    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="1",
        reason_code="not-a-real-reason",
        note="",
        batch_id=batch.id,
    )
    assert result is None
    assert errors
    assert _writeoff_ops(session) == []


def test_writeoff_requires_batch(session, stocked_product):
    """LOT-05: a write-off with no resolvable batch is rejected with
    «Выберите партию.» and writes nothing."""
    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="1",
        reason_code="expired",
        note="",
        batch_id="",
    )
    assert result is None
    assert errors == {"batch": "Выберите партию."}
    assert _writeoff_ops(session) == []


def test_writeoff_foreign_batch_rejected(session, stocked_product):
    """LOT-05/T-09-12: a batch that belongs to another product is rejected
    (never trust the client id); 0 writes."""
    _other, foreign_a, _foreign_b = _two_batch_product(session)
    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="1",
        reason_code="expired",
        note="",
        batch_id=foreign_a.id,
    )
    assert result is None
    assert errors == {"batch": "Выберите партию."}
    assert _writeoff_ops(session) == []


def test_writeoff_per_batch_over_removal(session):
    """criterion 4/D-09: writing off 5 from a batch with only 2 remaining warns
    (available == the batch's 2, NOT the product total 12) with zero writes;
    confirm=1 overrides and decrements the picked batch."""
    _product, batch_a, batch_b = _two_batch_product(session)

    result, errors = register_writeoff(
        session,
        code="MB-001",
        name="",
        qty_raw="5",
        reason_code="expired",
        note="",
        batch_id=batch_a.id,
    )
    assert errors == {}
    assert result and result.get("oversell")
    assert result["oversell"]["available"] == 2  # batch-scoped, not 12
    assert result["oversell"]["requested"] == 5
    assert _writeoff_ops(session) == []

    confirmed, confirm_errors = register_writeoff(
        session,
        code="MB-001",
        name="",
        qty_raw="5",
        reason_code="expired",
        note="",
        batch_id=batch_a.id,
        confirm="1",
    )
    assert confirm_errors == {}
    assert confirmed and confirmed.get("operation")
    session.expire_all()
    assert batch_a.quantity == 2 - 5  # batch may go negative on confirm
    assert batch_b.quantity == 10  # sibling batch untouched


# --- Web slice (routes + templates) ---


def test_web_writeoff_form(client, session, stocked_product):
    """/writeoff: page renders «Списание»; bad input -> 422 RU error, 0
    writes; code->name lookup answers 204 for an unknown code."""
    response = client.get("/writeoff")
    assert response.status_code == 200
    assert "Списание" in response.text

    bad_response = client.post(
        "/writeoff",
        data={"code": stocked_product.code, "qty": "", "reason_code": "expired", "note": ""},
    )
    assert bad_response.status_code == 422
    assert _writeoff_ops(session) == []

    lookup_response = client.get("/writeoff/lookup", params={"code": "NO-SUCH-CODE", "name": ""})
    assert lookup_response.status_code == 204


def test_web_writeoff_oversell(client, session, stocked_product):
    """OPS-01/D-04: write-off oversell warns-but-allows — writing off more
    than the picked batch holds with no confirm writes 0 rows and shows a
    batch-scoped warning + confirm control; confirm=1 writes and stock may go
    to/through zero."""
    batch = _only_batch(session, stocked_product)
    response = client.post(
        "/writeoff",
        data={
            "code": stocked_product.code,
            "qty": "100",
            "reason_code": "expired",
            "note": "",
            "batch_id": batch.id,
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    assert "Списать всё равно" in response.text
    assert _writeoff_ops(session) == []

    confirm_response = client.post(
        "/writeoff",
        data={
            "code": stocked_product.code,
            "qty": "100",
            "reason_code": "expired",
            "note": "",
            "batch_id": batch.id,
            "confirm": "1",
        },
    )
    assert confirm_response.status_code == 200
    session.expire_all()
    assert stocked_product.quantity <= 0
    assert len(_writeoff_ops(session)) == 1


def test_web_writeoff_lookup_emits_batch_picker(client, session, stocked_product):
    """LOT-05: the /writeoff/lookup response for a stocked product emits the
    shared batch picker (oob) so the operator can pick a batch."""
    response = client.get(
        "/writeoff/lookup", params={"code": stocked_product.code, "name": ""}
    )
    assert response.status_code == 200
    assert 'id="batch-wrap-first"' in response.text
    assert "Выберите партию" in response.text


def test_web_writeoff_create_ownership_guard_does_not_echo_foreign_batch(
    client, session, stocked_product, product
):
    """D-10: a client-submitted batch_id naming another product's batch is
    never echoed back into the picker on POST /writeoff's error branch."""
    foreign_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=_only_batch(session, stocked_product).warehouse_id,
        quantity=0,
    )
    session.add(foreign_batch)
    session.commit()

    response = client.post(
        "/writeoff",
        data={
            "code": stocked_product.code,
            "qty": "3",
            "reason_code": "expired",
            "note": "",
            "batch_id": foreign_batch.id,
        },
    )

    assert response.status_code == 422
    assert foreign_batch.id not in response.text


def test_web_writeoff_reachable_from_nav(client, product):
    """Gap-closure guard: 05-VERIFICATION.md's Gap #1 (unreachable /writeoff
    — no nav entry point anywhere in the rendered UI) must never silently
    regress; the home page must always link to /writeoff."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/writeoff"' in response.text
