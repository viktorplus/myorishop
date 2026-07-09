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

from app.services.writeoffs import register_writeoff  # noqa: F401
from sqlalchemy import select

from app.models import WRITEOFF_REASONS, Operation
from app.services.ledger import compute_stock


def _writeoff_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "writeoff")).all()


# --- Service level ---


def test_stock_and_reason(session, stocked_product):
    """OPS-01: a write-off writes a `writeoff` op (qty_delta<0); Product.quantity
    AND compute_stock() both drop by qty; the reason is persisted in payload
    as exactly {reason_code, note}."""
    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="3",
        reason_code="expired",
        note="",
    )
    assert errors == {}
    assert result

    ops = _writeoff_ops(session)
    assert len(ops) == 1
    op = ops[0]
    assert op.qty_delta == -3
    assert op.payload == {"reason_code": "expired", "note": ""}

    session.expire_all()
    assert stocked_product.quantity == 8 - 3
    assert compute_stock(session, stocked_product.id) == 8 - 3


def test_reason_allowlist(session, stocked_product):
    """OPS-01: a reason_code NOT in WRITEOFF_REASONS is rejected server-side
    (the authoritative allow-list — never trust the <select>); 0 writes."""
    assert "not-a-real-reason" not in WRITEOFF_REASONS

    result, errors = register_writeoff(
        session,
        code=stocked_product.code,
        name="",
        qty_raw="1",
        reason_code="not-a-real-reason",
        note="",
    )
    assert result is None
    assert errors
    assert _writeoff_ops(session) == []


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
    than in stock with no confirm writes 0 rows and shows a warning +
    confirm control; confirm=1 writes and stock may go to/through zero."""
    response = client.post(
        "/writeoff",
        data={
            "code": stocked_product.code,
            "qty": "100",
            "reason_code": "expired",
            "note": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает на складе" in response.text
    assert "Списать всё равно" in response.text
    assert _writeoff_ops(session) == []

    confirm_response = client.post(
        "/writeoff",
        data={
            "code": stocked_product.code,
            "qty": "100",
            "reason_code": "expired",
            "note": "",
            "confirm": "1",
        },
    )
    assert confirm_response.status_code == 200
    session.expire_all()
    assert stocked_product.quantity <= 0
    assert len(_writeoff_ops(session)) == 1
