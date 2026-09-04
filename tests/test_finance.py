"""FIN-01/02/06 append-only + balance/contract tests for the cash ledger
(Phase 15, Plan 01 + Plan 02).

Plan 02 adds app.services.finance import (compute_balance, next_seq,
record_cash_movement) now that the service exists.

Plan 03 adds the integration tests proving the sale-credit / return-debit
hooks wired into app.services.sales.register_sale and
app.services.returns.register_return (credit, sale_rollback, debit,
partial, atomic).
"""

import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from alembic import command
from app.config import settings
from app.core import local_today_iso, new_id, utcnow_iso
from app.models import (  # noqa: F401  (CASH_CATEGORIES: contract symbol)
    CASH_BUCKET_LABELS,
    CASH_BUCKETS,
    CASH_CATEGORIES,
    CashMovement,
    Operation,
    Warehouse,
)
from app.services.batches import open_batches
from app.services.finance import (
    AMOUNT_ERROR,
    cash_history_view,
    compute_balance,
    next_seq,
    record_cash_movement,
    record_manual_movement,
)
from app.services.ledger import OP_DATE_FORMAT_ERROR, OP_DATE_FUTURE_ERROR
from app.services.returns import register_return
from app.services.sales import register_sale


def _cash_count(session):
    return session.scalar(select(func.count()).select_from(CashMovement))


def test_cash_movement_append_only_update_is_rejected(session):
    """D-00a: UPDATE on cash_movements is blocked at the database level."""
    session.add(
        CashMovement(
            id=new_id(),
            category="sale",
            amount_cents=12500,
            device_id=settings.device_id,
            seq=1,
            created_at=utcnow_iso(),
            created_by=settings.operator_name,
        )
    )
    session.commit()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE cash_movements SET amount_cents = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_cash_movement_append_only_delete_is_rejected(session):
    """D-00a: DELETE on cash_movements is blocked at the database level."""
    session.add(
        CashMovement(
            id=new_id(),
            category="sale",
            amount_cents=12500,
            device_id=settings.device_id,
            seq=1,
            created_at=utcnow_iso(),
            created_by=settings.operator_name,
        )
    )
    session.commit()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM cash_movements"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_balance_empty_is_zero(session):
    """D-00b: compute_balance on an empty ledger returns 0."""
    assert compute_balance(session) == 0


def test_balance_sums_mixed(session):
    """D-00b: compute_balance is the live signed SUM(amount_cents)."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="return", amount_cents=-5000)
    assert compute_balance(session) == 7500


def test_balance_scopes_by_currency(session):
    """CUR-02: compute_balance is scoped to ONE currency; the two never sum."""
    session.add(Warehouse(id=new_id(), name="Склад EUR", currency="EUR"))
    session.commit()
    record_cash_movement(session, category="sale", amount_cents=1000)  # RUB default
    record_cash_movement(session, category="sale", amount_cents=2000, currency="EUR")

    assert compute_balance(session, "RUB") == 1000
    assert compute_balance(session, "EUR") == 2000
    assert compute_balance(session, "RUB") != compute_balance(session, "RUB") + compute_balance(
        session, "EUR"
    )


def test_record_manual_movement_writes_entered_currency(session):
    """CUR-02: record_manual_movement's written row carries the entered currency."""
    session.add(Warehouse(id=new_id(), name="Склад EUR", currency="EUR"))
    session.commit()
    result, errors = record_manual_movement(
        session,
        category="deposit_opening",
        amount_raw="50,00",
        note="",
        currency="EUR",
    )
    assert errors == {}
    assert result["movement"].currency == "EUR"


def test_contract_stamps_audit_and_seq(session):
    """D-00b/FND-03: record_cash_movement stamps audit fields and increments
    seq per device (mirrors test_ledger.py:test_audit_trail)."""
    mv1 = record_cash_movement(session, category="sale", amount_cents=12500)
    mv2 = record_cash_movement(session, category="return", amount_cents=-5000)

    assert mv1.created_by == settings.operator_name
    assert isinstance(mv1.created_at, str) and mv1.created_at

    assert mv1.seq == 1
    assert mv2.seq == 2
    assert next_seq(session, settings.device_id) == 3


def test_contract_unknown_category_raises(session):
    """T-15-02: an unknown category raises ValueError and stages no row
    (mirrors test_ledger.py:test_record_operation_unknown_product_raises_value_error)."""
    with pytest.raises(ValueError, match="unknown cash category"):
        record_cash_movement(session, category="bogus", amount_cents=1)
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM cash_movements")) == 0


# --- Phase 16 Plan 01: manual category + bucket constant contracts ---

_MANUAL_CATEGORY_KEYS = (
    "withdrawal_supplier",
    "withdrawal_salary",
    "withdrawal_rent",
    "withdrawal_utilities",
    "withdrawal_other",
    "deposit_opening",
    "deposit_correction",
)


def test_categories_manual_keys_present():
    """D-01/D-01b: all 7 manual keys exist in CASH_CATEGORIES with non-empty RU
    labels, and every category key fits CashMovement.category String(20)."""
    for key in _MANUAL_CATEGORY_KEYS:
        assert key in CASH_CATEGORIES, f"missing manual category key: {key!r}"
        assert CASH_CATEGORIES[key].strip(), f"empty label for {key!r}"
    # existing system keys stay unchanged
    assert CASH_CATEGORIES["sale"] == "Продажа"
    assert CASH_CATEGORIES["return"] == "Возврат"
    # every key must fit the String(20) category column
    assert all(len(k) <= 20 for k in CASH_CATEGORIES)


def test_buckets_cover_categories():
    """D-01a: every key in every CASH_BUCKETS tuple is a real CASH_CATEGORIES
    key (no orphans), and CASH_BUCKET_LABELS keys match CASH_BUCKETS keys."""
    for bucket, cats in CASH_BUCKETS.items():
        assert cats, f"empty bucket tuple for {bucket!r}"
        for cat in cats:
            assert cat in CASH_CATEGORIES, f"orphan bucket category: {cat!r}"
    assert set(CASH_BUCKET_LABELS) == set(CASH_BUCKETS)
    assert all(label.strip() for label in CASH_BUCKET_LABELS.values())
    # the 4 coarse buckets from D-01a/D-07a
    assert set(CASH_BUCKETS) == {"sale", "return", "withdrawal", "deposit"}
    assert set(CASH_BUCKETS["withdrawal"]) == {
        "withdrawal_supplier",
        "withdrawal_salary",
        "withdrawal_rent",
        "withdrawal_utilities",
        "withdrawal_other",
    }
    assert set(CASH_BUCKETS["deposit"]) == {"deposit_opening", "deposit_correction"}


# --- Plan 03 integration: sale credit / return debit hooks ---


def test_sale_credits_till(session, stocked_product):
    """FIN-01: a committed sale of total T writes exactly one +T cash row,
    category="sale", linked by sale_id; balance rises by T."""
    bid = open_batches(session, stocked_product.id)[0].id
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result
    total_cents = result["total_cents"]
    header_id = result["header"].id

    rows = list(session.scalars(select(CashMovement)))
    assert len(rows) == 1
    assert rows[0].amount_cents == total_cents
    assert rows[0].category == "sale"
    assert rows[0].sale_id == header_id
    assert compute_balance(session) == total_cents


def test_sale_rollback_writes_zero_cash(session, stocked_product):
    """T-15-03: a sale forced down its no-write path (oversell without
    confirm) writes zero cash rows; balance unchanged."""
    bid = open_batches(session, stocked_product.id)[0].id
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],  # exceeds the batch's available quantity (8)
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result and "oversell" in result
    assert _cash_count(session) == 0
    assert compute_balance(session) == 0


def test_full_return_restores_balance(session, stocked_product):
    """FIN-02: a sale-linked return debits -(qty x frozen unit_price_cents),
    category="return"; a FULL return restores the pre-sale balance."""
    bid = open_batches(session, stocked_product.id)[0].id
    pre_sale_balance = compute_balance(session)

    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="2"
    )
    assert return_errors == {}
    assert return_result

    debit_row = session.scalars(
        select(CashMovement).where(CashMovement.category == "return")
    ).first()
    assert debit_row.amount_cents == -(2 * 1500)
    assert compute_balance(session) == pre_sale_balance


def test_partial_return_debits_independently(session, stocked_product):
    """FIN-02/D-00d: a partial return debits only returned_qty x the frozen
    unit_price_cents, computed independently of the full sale credit."""
    bid = open_batches(session, stocked_product.id)[0].id
    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["4"],
        prices=["20,00"],  # 2000 cents/unit, distinct from the card price
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="1"
    )
    assert return_errors == {}
    assert return_result

    debit_row = session.scalars(
        select(CashMovement).where(CashMovement.category == "return")
    ).first()
    # Independent partial debit (1 x 2000), NOT the full credit (4 x 2000).
    assert debit_row.amount_cents == -(1 * 2000)
    assert debit_row.amount_cents != -sale_result["total_cents"]


def test_return_is_atomic(session, stocked_product):
    """T-15-03: after a successful return, the count of `return` ops equals
    the count of `return` cash rows (both written, one transaction)."""
    bid = open_batches(session, stocked_product.id)[0].id
    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="2"
    )
    assert return_errors == {}
    assert return_result

    return_op_count = session.scalar(
        select(func.count()).select_from(Operation).where(Operation.type == "return")
    )
    return_cash_count = session.scalar(
        select(func.count()).select_from(CashMovement).where(CashMovement.category == "return")
    )
    assert return_op_count == return_cash_count == 1


# --- Plan 04: balance page render (FIN-06) ---


def test_page_empty_shows_zero(client):
    """FIN-06: GET /finance renders «Баланс кассы» with 0,00 on an empty ledger."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert "Баланс кассы" in response.text
    assert "0,00" in response.text


def test_web_finance_renders_non_empty_currency_selects_rub_default(client):
    """CLAUDE.md select check: /finance's withdraw + deposit forms each render
    a non-empty currency select, RUB preselected by default."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert response.text.count('name="currency"') >= 2
    for code in ("RUB", "UAH", "EUR"):
        assert f'value="{code}"' in response.text
    assert 'value="RUB" selected' in response.text


def test_page_shows_balance(client, session):
    """FIN-06: GET /finance renders the live balance via the cents filter."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    response = client.get("/finance")
    assert response.status_code == 200
    assert "125,00" in response.text


def test_mobile_page_shows_balance(mobile_client_factory, session):
    """FIN-06: GET /m/finance mirrors the desktop page on its own router."""
    from app.routes import mobile_finance

    record_cash_movement(session, category="sale", amount_cents=12500)
    mobile_client = mobile_client_factory(mobile_finance.router)
    response = mobile_client.get("/m/finance")
    assert response.status_code == 200
    assert "Баланс кассы" in response.text
    assert "125,00" in response.text


# --- Plan 02: record_manual_movement (FIN-03/04/05) ---


def test_withdraw_writes_one_negative_row(session):
    """FIN-03/D-02a: a manual withdrawal writes exactly one row with the sign
    applied server-side (positive input -> negative amount_cents). Balance is
    pre-seeded so the negative-balance gate (D-05) does not fire here."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw="15,00", note=""
    )
    assert errors == {}
    assert result
    withdraw_rows = list(
        session.scalars(
            select(CashMovement).where(CashMovement.category == "withdrawal_supplier")
        )
    )
    assert len(withdraw_rows) == 1
    assert withdraw_rows[0].amount_cents == -1500
    assert withdraw_rows[0].category == "withdrawal_supplier"
    assert compute_balance(session) == 10000 - 1500


def test_deposit_writes_one_positive_row(session):
    """FIN-04/D-02a: a manual deposit writes exactly one positive row."""
    result, errors = record_manual_movement(
        session, category="deposit_opening", amount_raw="100", note=""
    )
    assert errors == {}
    assert result
    rows = list(session.scalars(select(CashMovement)))
    assert len(rows) == 1
    assert rows[0].amount_cents == 10000
    assert compute_balance(session) == 10000


@pytest.mark.parametrize("bad", ["", "0", "-5", "abc", "1,2,3"])
def test_withdraw_rejects_bad_amount(session, bad):
    """T-16-01/D-02a: blank/zero/negative/non-numeric amount -> (None, errors),
    ZERO writes."""
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw=bad, note=""
    )
    assert result is None
    assert "amount" in errors
    assert _cash_count(session) == 0


@pytest.mark.parametrize("cat", ["sale", "return", "bogus", ""])
def test_withdraw_rejects_unknown_category(session, cat):
    """T-16-02: a system key ("sale"/"return") or unknown key is NOT a manual
    category -> (None, {"category": ...}), ZERO writes."""
    result, errors = record_manual_movement(
        session, category=cat, amount_raw="10,00", note="x"
    )
    assert result is None
    assert "category" in errors
    assert _cash_count(session) == 0


def test_withdraw_other_requires_comment(session):
    """D-04: withdrawal_other with a whitespace note -> (None, {"note": ...})."""
    result, errors = record_manual_movement(
        session, category="withdrawal_other", amount_raw="10,00", note="   "
    )
    assert result is None
    assert "note" in errors
    assert _cash_count(session) == 0


def test_deposit_correction_requires_comment(session):
    """D-04: deposit_correction with a blank note -> (None, {"note": ...})."""
    result, errors = record_manual_movement(
        session, category="deposit_correction", amount_raw="10,00", note=""
    )
    assert result is None
    assert "note" in errors
    assert _cash_count(session) == 0


def test_withdraw_other_with_comment_succeeds(session):
    """D-04: the mandatory-comment categories succeed with a non-blank note.
    Balance pre-seeded so the D-05 gate does not fire."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    result, errors = record_manual_movement(
        session, category="withdrawal_other", amount_raw="10,00", note="ремонт"
    )
    assert errors == {}
    assert result
    assert result["movement"].note == "ремонт"
    assert _cash_count(session) == 2


def test_withdraw_supplier_allows_blank_comment(session):
    """D-04: other categories succeed with a blank note (stored as NULL).
    Balance pre-seeded so the D-05 gate does not fire."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw="10,00", note=""
    )
    assert errors == {}
    assert result
    assert result["movement"].note is None
    assert _cash_count(session) == 2


def test_negative_gate_blocks_without_confirm(session):
    """D-05/FIN-05: a withdrawal that would drive the balance below zero with
    confirm != "1" warns with ZERO writes."""
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw="50,00", confirm="", note=""
    )
    assert errors == {}
    assert result and "negative_balance" in result
    assert result["negative_balance"] == {"balance": 0, "amount": 5000}
    assert _cash_count(session) == 0
    assert compute_balance(session) == 0


def test_negative_gate_allows_with_confirm(session):
    """D-05/FIN-05: confirm == "1" writes and the balance may go negative."""
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw="50,00", confirm="1", note=""
    )
    assert errors == {}
    assert result
    assert _cash_count(session) == 1
    assert compute_balance(session) == -5000


def test_negative_gate_deposit_never_warns(session):
    """D-05: a deposit never enters the negative-balance branch."""
    result, errors = record_manual_movement(
        session, category="deposit_opening", amount_raw="50,00", confirm="", note=""
    )
    assert errors == {}
    assert result and "negative_balance" not in result
    assert compute_balance(session) == 5000


def test_negative_gate_covered_withdrawal_no_warn(session):
    """D-05: a withdrawal the balance covers never warns."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    result, errors = record_manual_movement(
        session, category="withdrawal_supplier", amount_raw="50,00", confirm="", note=""
    )
    assert errors == {}
    assert result and "negative_balance" not in result
    assert compute_balance(session) == 5000


# --- Phase 33 (VA-14): «Дата операции» on the manual cash write path ---
#
# record_manual_movement is the SECOND independent write path in the app — it
# reaches cash_movements through record_cash_movement, not through
# ledger.record_operation — so the business date has to be threaded and proven
# here separately from the five ledger services.


def _days_from_today(offset: int) -> str:
    """An ISO day `offset` days from today's LOCAL day (the same definition
    parse_op_date's future check and the today_iso() Jinja global both use)."""
    return (
        date.fromisoformat(local_today_iso(settings.display_tz))
        + timedelta(days=offset)
    ).isoformat()


def test_manual_withdrawal_stores_the_backdated_business_date(session):
    """DATE-01: a back-dated withdrawal lands its own business_date, while
    created_at keeps recording when the row was actually entered (DATE-04)."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    back_date = _days_from_today(-20)

    result, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="15,00",
        note="",
        op_date=back_date,
    )

    assert errors == {}
    mv = result["movement"]
    assert mv.business_date == back_date
    # The audit timestamp is NOT overwritten by the operator's date.
    assert mv.created_at[:10] != back_date


def test_manual_deposit_stores_the_backdated_business_date(session):
    """DATE-01: the deposit direction carries the date too — both cash forms
    post to the same service entry point."""
    back_date = _days_from_today(-3)

    result, errors = record_manual_movement(
        session,
        category="deposit_opening",
        amount_raw="100",
        note="",
        op_date=back_date,
    )

    assert errors == {}
    assert result["movement"].business_date == back_date


def test_manual_movement_empty_date_stamps_todays_local_day(session):
    """DATE-08/D-15: an empty value is not an error — it means «today», and the
    fallback is resolved exactly ONCE, inside record_cash_movement. Asserted
    against local_today_iso, never against created_at's UTC prefix (the two
    differ for every row entered in the 00:00-03:00 local window)."""
    result, errors = record_manual_movement(
        session, category="deposit_opening", amount_raw="100", note="", op_date=""
    )

    assert errors == {}
    assert result["movement"].business_date == local_today_iso(settings.display_tz)


def test_manual_movement_rejects_a_future_date_with_zero_writes(session):
    """DATE-02/T-33-16: a future date is refused in Russian and NOTHING is
    written — the CashMovement count is unchanged."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    before = _cash_count(session)

    result, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="15,00",
        note="",
        op_date=_days_from_today(1),
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FUTURE_ERROR
    assert _cash_count(session) == before


def test_manual_movement_rejects_a_malformed_date_with_zero_writes(session):
    """DATE-02/D-12: a typo gets the OTHER message — a malformed date and a
    future date are different operator mistakes and never share one string."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    before = _cash_count(session)

    result, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="15,00",
        note="",
        op_date="15.08.2026",
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FORMAT_ERROR
    assert errors["op_date"] != OP_DATE_FUTURE_ERROR
    assert _cash_count(session) == before


def test_manual_movement_date_error_rides_alongside_the_amount_error(session):
    """The date is validated in the SAME block as the amount, so a form with
    both mistakes surfaces both in one 422 instead of one at a time."""
    result, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="abc",
        note="",
        op_date=_days_from_today(1),
    )

    assert result is None
    assert errors["amount"] == AMOUNT_ERROR
    assert errors["op_date"] == OP_DATE_FUTURE_ERROR
    assert _cash_count(session) == 0


def test_manual_movement_date_survives_the_negative_balance_confirm(session):
    """D-05 + DATE-01: the warn path writes nothing; the confirm re-POST carries
    the SAME back-date through to the stored row. This is the path where the
    date could silently be lost, because confirm re-submits the re-rendered
    form rather than the operator's original one."""
    back_date = _days_from_today(-7)

    warn, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="50,00",
        note="",
        confirm="",
        op_date=back_date,
    )
    assert errors == {}
    assert "negative_balance" in warn
    assert _cash_count(session) == 0

    result, errors = record_manual_movement(
        session,
        category="withdrawal_supplier",
        amount_raw="50,00",
        note="",
        confirm="1",
        op_date=back_date,
    )
    assert errors == {}
    assert result["movement"].business_date == back_date


# --- Plan 02: cash_history_view (FIN-07) ---

_WITHDRAWAL_KEYS = (
    "withdrawal_supplier",
    "withdrawal_salary",
    "withdrawal_rent",
    "withdrawal_utilities",
    "withdrawal_other",
)


def test_cash_history_empty(session):
    """FIN-07: an empty ledger returns the contract shape, total_pages >= 1."""
    assert cash_history_view(session) == {
        "rows": [],
        "page": 0,
        "total": 0,
        "total_pages": 1,
        "bucket": "",
        "currency": "RUB",
    }


def test_cash_history_paginates_and_clamps(session):
    """FIN-07/T-14-04: page never exceeds page_size; out-of-range page clamps
    to the last page (never empty)."""
    for _ in range(25):
        record_cash_movement(session, category="sale", amount_cents=100)

    page0 = cash_history_view(session, page=0)
    assert len(page0["rows"]) == 20  # LIST_PAGE_SIZE
    assert page0["total"] == 25
    assert page0["total_pages"] == 2

    page1 = cash_history_view(session, page=1)
    assert len(page1["rows"]) == 5

    clamped = cash_history_view(session, page=9)
    assert clamped["page"] == 1
    assert len(clamped["rows"]) == 5


def test_cash_history_newest_first(session):
    """FIN-07: rows are ordered created_at desc, seq desc."""
    for _ in range(3):
        record_cash_movement(session, category="sale", amount_cents=100)
    rows = cash_history_view(session)["rows"]
    assert rows[0].created_at >= rows[1].created_at
    assert rows[0].seq > rows[1].seq


def test_cash_history_bucket_withdrawal(session):
    """FIN-07/Pitfall 3: bucket="withdrawal" narrows to exactly the 5
    withdrawal_* categories (a `== bucket` filter cannot express «Снятие»)."""
    record_cash_movement(session, category="sale", amount_cents=100)
    for cat in _WITHDRAWAL_KEYS:
        record_cash_movement(session, category=cat, amount_cents=-100)

    result = cash_history_view(session, bucket="withdrawal")
    assert result["total"] == 5
    assert result["bucket"] == "withdrawal"
    assert {r.category for r in result["rows"]} == set(_WITHDRAWAL_KEYS)


def test_cash_history_bucket_sale_only(session):
    """FIN-07: bucket="sale" returns only sale rows."""
    record_cash_movement(session, category="sale", amount_cents=100)
    record_cash_movement(session, category="return", amount_cents=-50)
    result = cash_history_view(session, bucket="sale")
    assert result["total"] == 1
    assert result["rows"][0].category == "sale"


def test_cash_history_unknown_bucket_ignored(session):
    """FIN-07/T-16-07: an unknown/tampered bucket is ignored (no filter)."""
    record_cash_movement(session, category="sale", amount_cents=100)
    record_cash_movement(session, category="return", amount_cents=-50)
    unfiltered_total = cash_history_view(session)["total"]
    result = cash_history_view(session, bucket="bogus")
    assert result["total"] == unfiltered_total == 2


def test_cash_history_includes_all_categories(session):
    """FIN-07: the unfiltered view includes sale credits, return debits AND
    manual entries — no category is excluded."""
    record_cash_movement(session, category="sale", amount_cents=100)
    record_cash_movement(session, category="return", amount_cents=-50)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-30)
    record_cash_movement(session, category="deposit_opening", amount_cents=200)
    cats = {r.category for r in cash_history_view(session)["rows"]}
    assert cats == {"sale", "return", "withdrawal_rent", "deposit_opening"}


# --- Plan 03 Task 1: desktop withdraw/deposit POST routes + shared forms ---

_HX = {"HX-Request": "true"}


def test_web_withdraw_persists_and_refreshes_balance(client, session):
    """FIN-03: a valid withdraw POST returns 200, persists exactly one negative
    row via the service, and carries an out-of-band #cash-balance refresh."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    response = client.post(
        "/finance/withdraw",
        data={"amount": "15,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    rows = list(
        session.scalars(
            select(CashMovement).where(CashMovement.category == "withdrawal_supplier")
        )
    )
    assert len(rows) == 1
    assert rows[0].amount_cents == -1500
    # oob balance refresh: 10000 - 1500 = 8500 -> «85,00»
    assert 'id="cash-balance"' in response.text
    assert "hx-swap-oob" in response.text
    assert "85,00" in response.text


def test_web_withdraw_blank_amount_returns_422(client, session):
    """T-16-01: a blank amount re-renders the form (422) with the UI-SPEC error
    and writes nothing."""
    response = client.post(
        "/finance/withdraw",
        data={"amount": "", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Введите сумму больше нуля." in response.text
    assert _cash_count(session) == 0


def test_web_withdraw_missing_comment_returns_422(client, session):
    """D-04: withdrawal_other with a blank comment -> 422, «Укажите комментарий.»,
    zero writes."""
    response = client.post(
        "/finance/withdraw",
        data={"amount": "10,00", "category": "withdrawal_other", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Укажите комментарий." in response.text
    assert _cash_count(session) == 0


def test_web_negative_warns_without_confirm(client, session):
    """D-05/T-16-05: a withdrawal that would go negative without confirm returns
    HTTP 200 (not 422) with the warn + a confirm control, and writes nothing."""
    response = client.post(
        "/finance/withdraw",
        data={"amount": "50,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    assert "Баланс уйдёт в минус" in response.text
    assert "Снять всё равно" in response.text
    assert "confirm" in response.text
    assert "#withdraw-form-wrap" in response.text
    assert _cash_count(session) == 0


def test_web_negative_allows_with_confirm(client, session):
    """D-05: the same withdrawal with confirm="1" returns 200 and persists the row."""
    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "50,00",
            "category": "withdrawal_supplier",
            "note": "",
            "confirm": "1",
        },
        headers=_HX,
    )
    assert response.status_code == 200
    assert _cash_count(session) == 1
    assert compute_balance(session) == -5000


def test_web_deposit_writes_positive_row(client, session):
    """FIN-04: a valid deposit POST returns 200 and persists exactly one positive
    row; the negative-balance branch never fires for deposits."""
    response = client.post(
        "/finance/deposit",
        data={"amount": "100", "category": "deposit_opening", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    rows = list(session.scalars(select(CashMovement)))
    assert len(rows) == 1
    assert rows[0].amount_cents == 10000
    assert "Баланс уйдёт в минус" not in response.text


def test_web_deposit_blank_category_returns_422(client, session):
    """UI-SPEC §D: a blank basis on the deposit form surfaces «Выберите основание.»
    (deposit-specific copy) at 422 with zero writes."""
    response = client.post(
        "/finance/deposit",
        data={"amount": "100", "category": "", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите основание." in response.text
    assert _cash_count(session) == 0


def test_web_finance_page_renders_both_forms(client):
    """D-06: GET /finance renders «Снять деньги» / «Внести деньги» forms whose
    select options carry the RU labels from CASH_CATEGORIES."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert "Снять деньги" in response.text
    assert "Внести деньги" in response.text
    assert "Оплата поставщику" in response.text  # withdrawal_supplier label
    assert "Начальный остаток" in response.text  # deposit_opening label


# --- Plan 03 Task 2: GET /finance/history + desktop history block ---


def test_web_cash_history_full_page_renders_rows_and_filter(client, session):
    """D-07: GET /finance (non-HX) renders the #cash-history-rows block with the
    «Тип» bucket filter (Все типы + the 4 bucket labels) and the movement rows."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-3000)
    response = client.get("/finance")
    assert response.status_code == 200
    assert "<!doctype" in response.text.lower()  # full-page chrome
    assert 'id="cash-history-rows"' in response.text
    assert "Все типы" in response.text
    for label in ("Продажа", "Возврат", "Снятие", "Внесение"):
        assert label in response.text
    assert "Аренда" in response.text  # withdrawal_rent category label in a row


def test_web_cash_history_hx_returns_partial_only(client, session):
    """D-07: an HX GET /finance/history returns ONLY the rows partial (no base
    chrome) and a bucket filter narrows to that bucket's categories."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-3000)
    response = client.get("/finance/history?bucket=withdrawal", headers=_HX)
    assert response.status_code == 200
    assert "<!doctype" not in response.text.lower()  # partial, no full chrome
    assert "Баланс кассы" not in response.text
    assert 'id="cash-history-rows"' in response.text
    # the withdrawal row is present, the sale row is filtered out (compared by
    # amount, since «Продажа» always appears as a bucket <option> in the filter)
    assert "Аренда" in response.text  # withdrawal_rent row label
    assert "-30,00" in response.text  # withdrawal amount
    assert "125,00" not in response.text  # sale row filtered out


def test_web_cash_history_non_hx_full_page_renders(client, session):
    """CR-01 regression: a plain (non-HX) GET /finance/history — the URL every
    filter/pagination control pushes via hx-push-url — must render the full
    page, not 500. It must include the dashboard tiles context (_metrics_context)
    exactly like GET /finance does."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    response = client.get("/finance/history?bucket=withdrawal")
    assert response.status_code == 200
    assert "<!doctype" in response.text.lower()
    assert 'id="cash-history-rows"' in response.text
    assert "metric-tile" in response.text  # dashboard tiles rendered, no UndefinedError


def test_web_cash_history_pagination_preserves_bucket(client, session):
    """FIN-07: with >20 movements the second page renders, and pagination links
    carry &bucket=… so the active filter survives paging (extra_qs)."""
    for _ in range(25):
        record_cash_movement(session, category="withdrawal_supplier", amount_cents=-100)
    first = client.get("/finance/history?bucket=withdrawal", headers=_HX)
    assert first.status_code == 200
    assert "bucket=withdrawal" in first.text  # extra_qs on pagination links
    second = client.get("/finance/history?bucket=withdrawal&page=1", headers=_HX)
    assert second.status_code == 200
    assert "Страница 2 из 2" in second.text


def test_web_cash_history_empty_states(client, session):
    """UI-SPEC §C: unfiltered empty ledger vs a filter with no matches show the
    two distinct empty-state messages."""
    empty = client.get("/finance/history", headers=_HX)
    assert "Движений пока нет." in empty.text

    record_cash_movement(session, category="sale", amount_cents=100)
    filtered = client.get("/finance/history?bucket=withdrawal", headers=_HX)
    assert "Нет движений по выбранному типу." in filtered.text


def test_web_cash_history_escapes_note(client, session):
    """T-16-06: a note containing markup renders escaped (autoescape; no |safe)."""
    record_cash_movement(
        session, category="withdrawal_rent", amount_cents=-100, note="<script>alert(1)</script>"
    )
    response = client.get("/finance/history", headers=_HX)
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_web_withdraw_oob_refreshes_history(client, session):
    """D-07: a successful withdraw POST carries an out-of-band #cash-history-rows
    refresh showing the new movement."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    response = client.post(
        "/finance/withdraw",
        data={"amount": "15,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    assert 'id="cash-history-rows"' in response.text
    assert response.text.count("hx-swap-oob") >= 2  # balance + history both oob
    assert "Оплата поставщику" in response.text  # the new withdrawal row


# --- Plan 04 Task 1: mobile withdraw/deposit POST + SHARED forms on /m/finance ---


def _mobile_finance_client(mobile_client_factory):
    """Build an isolated TestClient bound to the mobile_finance router
    (mirrors test_mobile_page_shows_balance's fixture usage)."""
    from app.routes import mobile_finance

    return mobile_client_factory(mobile_finance.router)


def test_mobile_withdraw_persists_and_refreshes_balance(mobile_client_factory, session):
    """FIN-03/D-06a: a valid mobile withdraw POST returns 200, persists exactly
    one negative row via the SHARED service, echoes the shared form whose hx-post
    targets /m/finance/withdraw (finance_base), and carries an oob #cash-balance."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "15,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    rows = list(
        session.scalars(
            select(CashMovement).where(CashMovement.category == "withdrawal_supplier")
        )
    )
    assert len(rows) == 1
    assert rows[0].amount_cents == -1500
    assert 'hx-post="/m/finance/withdraw"' in response.text  # finance_base, no /finance leak
    assert 'id="cash-balance"' in response.text
    assert "hx-swap-oob" in response.text
    assert "85,00" in response.text  # 10000 - 1500 = 8500


def test_mobile_withdraw_blank_amount_returns_422(mobile_client_factory, session):
    """T-16-01: a blank mobile amount re-renders the shared form (422) with the
    UI-SPEC error and writes nothing."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Введите сумму больше нуля." in response.text
    assert _cash_count(session) == 0


def test_mobile_withdraw_missing_comment_returns_422(mobile_client_factory, session):
    """D-04: withdrawal_other with a blank comment -> 422, «Укажите комментарий.»,
    zero writes on the mobile surface."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "10,00", "category": "withdrawal_other", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Укажите комментарий." in response.text
    assert _cash_count(session) == 0


def test_mobile_negative_warns_without_confirm(mobile_client_factory, session):
    """D-05/T-16-05: a mobile withdrawal that would go negative without confirm
    returns HTTP 200 with the warn + a confirm control targeting /m/finance/withdraw,
    and writes nothing."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "50,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    assert "Баланс уйдёт в минус" in response.text
    assert "Снять всё равно" in response.text
    assert 'hx-post="/m/finance/withdraw"' in response.text
    assert _cash_count(session) == 0


def test_mobile_negative_allows_with_confirm(mobile_client_factory, session):
    """D-05: the same mobile withdrawal with confirm="1" returns 200 and persists."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={
            "amount": "50,00",
            "category": "withdrawal_supplier",
            "note": "",
            "confirm": "1",
        },
        headers=_HX,
    )
    assert response.status_code == 200
    assert _cash_count(session) == 1
    assert compute_balance(session) == -5000


def test_mobile_deposit_writes_positive_row(mobile_client_factory, session):
    """FIN-04: a valid mobile deposit POST returns 200 and persists exactly one
    positive row; deposits never warn."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/deposit",
        data={"amount": "100", "category": "deposit_opening", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    rows = list(session.scalars(select(CashMovement)))
    assert len(rows) == 1
    assert rows[0].amount_cents == 10000
    assert "Баланс уйдёт в минус" not in response.text


def test_mobile_deposit_blank_category_returns_422(mobile_client_factory, session):
    """UI-SPEC §D: a blank basis on the mobile deposit form surfaces «Выберите
    основание.» at 422 with zero writes."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/deposit",
        data={"amount": "100", "category": "", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите основание." in response.text
    assert _cash_count(session) == 0


def test_mobile_finance_page_renders_both_forms(mobile_client_factory):
    """D-06/D-06a: GET /m/finance renders both shared forms whose hx-post targets
    resolve on the mobile surface (finance_base), never the desktop /finance."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance")
    assert response.status_code == 200
    assert 'hx-post="/m/finance/withdraw"' in response.text
    assert 'hx-post="/m/finance/deposit"' in response.text
    assert 'hx-post="/finance/withdraw"' not in response.text  # no desktop leakage


# --- Plan 04 Task 2: mobile cash history (cards + «Показать ещё» load-more) ---


def test_mobile_cash_history_full_page_renders_cards_and_filter(
    mobile_client_factory, session
):
    """D-07/UI-SPEC Q1: GET /m/finance (non-HX) renders a #cash-history-cards div
    with a .mobile-card per movement and a «Тип» bucket <select> (Все типы + the
    4 bucket labels) — NOT a numbered pagination bar."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-3000)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance")
    assert response.status_code == 200
    assert 'id="cash-history-cards"' in response.text
    assert "mobile-card" in response.text
    assert "Все типы" in response.text
    for label in ("Продажа", "Возврат", "Снятие", "Внесение"):
        assert label in response.text
    assert "Аренда" in response.text  # withdrawal_rent category label in a card


def test_mobile_cash_history_hx_returns_cards_and_load_more(
    mobile_client_factory, session
):
    """D-07: an HX GET /m/finance/history returns the card partial PLUS an oob
    #cash-history-load-more; with more pages the «Показать ещё» button's hx-get
    carries the next page and the active bucket."""
    for _ in range(25):
        record_cash_movement(session, category="sale", amount_cents=100)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance/history?page=0", headers=_HX)
    assert response.status_code == 200
    assert "<!doctype" not in response.text.lower()  # partial, no full chrome
    assert "mobile-card" in response.text
    assert 'id="cash-history-load-more"' in response.text
    assert "hx-swap-oob" in response.text
    assert "Показать ещё" in response.text
    assert "page=1" in response.text  # next page on the load-more button


def test_mobile_cash_history_non_hx_full_page_renders(mobile_client_factory, session):
    """CR-01 regression: a plain (non-HX) GET /m/finance/history — the URL every
    filter/«Показать ещё» control pushes via hx-push-url — must render the full
    page, not 500. It must include the dashboard tiles context (_metrics_context)
    exactly like GET /m/finance does."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance/history?bucket=withdrawal")
    assert response.status_code == 200
    assert 'id="cash-history-cards"' in response.text
    assert "metric-tile" in response.text  # dashboard tiles rendered, no UndefinedError


def test_mobile_cash_history_last_page_hides_button(mobile_client_factory, session):
    """D-07: on the last page has_next is false, so the «Показать ещё» button
    is absent (the oob sentinel div is still present, empty)."""
    for _ in range(25):
        record_cash_movement(session, category="sale", amount_cents=100)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance/history?page=1", headers=_HX)
    assert response.status_code == 200
    assert 'id="cash-history-load-more"' in response.text
    assert "Показать ещё" not in response.text


def test_mobile_cash_history_bucket_filter(mobile_client_factory, session):
    """FIN-07/Pitfall 3: bucket=withdrawal lists only withdrawal-category cards."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-3000)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance/history?bucket=withdrawal", headers=_HX)
    assert response.status_code == 200
    assert "Аренда" in response.text  # withdrawal_rent card present
    assert "-30,00" in response.text
    assert "125,00" not in response.text  # sale card filtered out


def test_mobile_cash_history_escapes_note(mobile_client_factory, session):
    """T-16-06: a note containing markup renders escaped (autoescape; no |safe)."""
    record_cash_movement(
        session,
        category="withdrawal_rent",
        amount_cents=-100,
        note="<script>alert(1)</script>",
    )
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.get("/m/finance/history", headers=_HX)
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_mobile_cash_history_empty_states(mobile_client_factory, session):
    """UI-SPEC §C: unfiltered empty ledger vs a filter with no matches show the
    two distinct empty-state messages on the mobile cards."""
    mc = _mobile_finance_client(mobile_client_factory)
    empty = mc.get("/m/finance/history", headers=_HX)
    assert "Движений пока нет." in empty.text

    record_cash_movement(session, category="sale", amount_cents=100)
    filtered = mc.get("/m/finance/history?bucket=withdrawal", headers=_HX)
    assert "Нет движений по выбранному типу." in filtered.text


def test_mobile_withdraw_oob_refreshes_history(mobile_client_factory, session):
    """D-07: a successful mobile withdraw POST carries an out-of-band
    #cash-history-cards refresh showing the new movement."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "15,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 200
    assert 'id="cash-history-cards"' in response.text
    assert "Оплата поставщику" in response.text  # the new withdrawal card label


def test_web_withdraw_rejects_deposit_category(client, session):
    """WR-01 defence-in-depth: a deposit_* category posted to /finance/withdraw is
    rejected at the route (422, «Выберите категорию.») with zero writes — the
    withdraw endpoint accepts only withdrawal_* categories, never a
    cross-direction deposit (the service derives direction from the category)."""
    response = client.post(
        "/finance/withdraw",
        data={"amount": "15,00", "category": "deposit_opening", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите категорию." in response.text
    assert _cash_count(session) == 0


def test_web_deposit_rejects_withdrawal_category(client, session):
    """WR-01 defence-in-depth: a withdrawal_* category posted to /finance/deposit is
    rejected at the route (422, «Выберите основание.») with zero writes — no
    expense is recorded via the deposit endpoint, and no false 'success' leaks
    from the shared service's negative-balance branch."""
    response = client.post(
        "/finance/deposit",
        data={"amount": "50,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите основание." in response.text
    assert _cash_count(session) == 0


def test_mobile_withdraw_rejects_deposit_category(mobile_client_factory, session):
    """WR-01 defence-in-depth (mobile parity): a deposit_* category posted to
    /m/finance/withdraw is rejected at the route (422) with zero writes."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/withdraw",
        data={"amount": "15,00", "category": "deposit_opening", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите категорию." in response.text
    assert _cash_count(session) == 0


def test_mobile_deposit_rejects_withdrawal_category(mobile_client_factory, session):
    """WR-01 defence-in-depth (mobile parity): a withdrawal_* category posted to
    /m/finance/deposit is rejected at the route (422) with zero writes."""
    mc = _mobile_finance_client(mobile_client_factory)
    response = mc.post(
        "/m/finance/deposit",
        data={"amount": "50,00", "category": "withdrawal_supplier", "note": ""},
        headers=_HX,
    )
    assert response.status_code == 422
    assert "Выберите основание." in response.text
    assert _cash_count(session) == 0


def test_migration_0024_adds_currency_and_backfills_rub(tmp_path, monkeypatch):
    """Existing cash_movements rows come out of the upgrade as RUB (mirrors
    test_warehouses.py::test_migration_0023_adds_currency_and_backfills_rub)."""
    db_file = tmp_path / "cash_currency.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("alembic.ini")

    # Stop one revision BEFORE the currency migration, insert a movement the
    # old way, then upgrade — the backfill must reach rows that already existed.
    command.upgrade(cfg, "0023")
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute(
            "INSERT INTO cash_movements"
            " (id, category, amount_cents, device_id, seq, created_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id(), "deposit_opening", 1000, new_id(), 1,
             "2026-01-01T00:00:00+00:00", "Оператор"),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cash_movements)")}
        assert "currency" in cols
        currencies = [
            row[0] for row in conn.execute("SELECT currency FROM cash_movements")
        ]
        assert currencies == ["RUB"]


# --- Phase 33 (DATE-01/DATE-02): the two cash forms, desktop AND mobile ------
#
# These are WIRING tests: they drive the real routes, not the service. 33-11
# recorded a defect where op_date reached the form and the echo but never the
# service, with every service-level test green — so every assertion below that
# claims a date was stored reads the persisted CashMovement row.


def _last_movement(session):
    return session.scalars(
        select(CashMovement).order_by(CashMovement.seq.desc())
    ).first()


def test_web_finance_page_renders_both_prefixed_date_inputs(client):
    """T-33-33: both cash forms render on ONE page, so their date inputs carry
    PREFIXED ids — an unprefixed shared one would appear twice in the document
    and break the second form's <label for> association."""
    today = local_today_iso(settings.display_tz)
    response = client.get("/finance")

    assert response.status_code == 200
    assert 'id="withdraw-op-date"' in response.text
    assert 'id="deposit-op-date"' in response.text
    # No duplicate id anywhere on the page.
    assert 'id="op_date"' not in response.text
    # Each label points at its OWN input.
    assert '<label for="withdraw-op-date">Дата операции</label>' in response.text
    assert '<label for="deposit-op-date">Дата операции</label>' in response.text
    # The posted NAME is shared and appears exactly twice — once per form.
    assert response.text.count('name="op_date"') == 2
    assert response.text.count(f'value="{today}" max="{today}"') == 2


def test_mobile_finance_page_renders_both_prefixed_date_inputs(mobile_client_factory):
    """One template edit covers both surfaces (the forms are SHARED and
    parameterised by finance_base), so /m/finance renders the identical ids."""
    mc = _mobile_finance_client(mobile_client_factory)
    today = local_today_iso(settings.display_tz)
    response = mc.get("/m/finance")

    assert response.status_code == 200
    assert 'id="withdraw-op-date"' in response.text
    assert 'id="deposit-op-date"' in response.text
    assert 'id="op_date"' not in response.text
    assert '<label for="withdraw-op-date">Дата операции</label>' in response.text
    assert '<label for="deposit-op-date">Дата операции</label>' in response.text
    assert response.text.count('name="op_date"') == 2
    assert response.text.count(f'value="{today}" max="{today}"') == 2


def test_web_withdraw_backdated_post_stores_the_business_date(client, session):
    """The wiring proof for снятие: the date the browser posts reaches the
    PERSISTED row, not just the form and the echo."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    back_date = _days_from_today(-12)

    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": back_date,
        },
        headers=_HX,
    )

    assert response.status_code == 200
    mv = _last_movement(session)
    assert mv.category == "withdrawal_supplier"
    assert mv.business_date == back_date
    assert mv.created_at[:10] != back_date


def test_web_deposit_backdated_post_stores_the_business_date(client, session):
    """The wiring proof for внесение."""
    back_date = _days_from_today(-5)

    response = client.post(
        "/finance/deposit",
        data={
            "amount": "100",
            "category": "deposit_opening",
            "note": "",
            "op_date": back_date,
        },
        headers=_HX,
    )

    assert response.status_code == 200
    assert _last_movement(session).business_date == back_date


def test_mobile_withdraw_backdated_post_stores_the_business_date(
    mobile_client_factory, session
):
    """The mobile twin — same shared form, same service, same stored date."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    mc = _mobile_finance_client(mobile_client_factory)
    back_date = _days_from_today(-9)

    response = mc.post(
        "/m/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": back_date,
        },
        headers=_HX,
    )

    assert response.status_code == 200
    assert _last_movement(session).business_date == back_date


def test_mobile_deposit_backdated_post_stores_the_business_date(
    mobile_client_factory, session
):
    mc = _mobile_finance_client(mobile_client_factory)
    back_date = _days_from_today(-2)

    response = mc.post(
        "/m/finance/deposit",
        data={
            "amount": "100",
            "category": "deposit_opening",
            "note": "",
            "op_date": back_date,
        },
        headers=_HX,
    )

    assert response.status_code == 200
    assert _last_movement(session).business_date == back_date


def test_web_withdraw_future_date_returns_422_and_echoes_the_typed_value(
    client, session
):
    """DATE-02 through the real route: 422, the Russian refusal, ZERO writes,
    and the submitted date still in the input's value= so the operator can fix
    it instead of retyping it."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    before = _cash_count(session)
    tomorrow = _days_from_today(1)

    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": tomorrow,
        },
        headers=_HX,
    )

    assert response.status_code == 422
    assert OP_DATE_FUTURE_ERROR in response.text
    assert f'value="{tomorrow}"' in response.text
    assert 'id="withdraw-op-date"' in response.text
    assert _cash_count(session) == before


def test_web_deposit_future_date_returns_422_and_echoes_the_typed_value(
    client, session
):
    tomorrow = _days_from_today(1)

    response = client.post(
        "/finance/deposit",
        data={
            "amount": "100",
            "category": "deposit_opening",
            "note": "",
            "op_date": tomorrow,
        },
        headers=_HX,
    )

    assert response.status_code == 422
    assert OP_DATE_FUTURE_ERROR in response.text
    assert f'value="{tomorrow}"' in response.text
    assert 'id="deposit-op-date"' in response.text
    assert _cash_count(session) == 0


def test_mobile_withdraw_future_date_returns_422_and_echoes_the_typed_value(
    mobile_client_factory, session
):
    mc = _mobile_finance_client(mobile_client_factory)
    tomorrow = _days_from_today(1)

    response = mc.post(
        "/m/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": tomorrow,
        },
        headers=_HX,
    )

    assert response.status_code == 422
    assert OP_DATE_FUTURE_ERROR in response.text
    assert f'value="{tomorrow}"' in response.text
    assert _cash_count(session) == 0


def test_mobile_deposit_future_date_returns_422_and_echoes_the_typed_value(
    mobile_client_factory, session
):
    mc = _mobile_finance_client(mobile_client_factory)
    tomorrow = _days_from_today(1)

    response = mc.post(
        "/m/finance/deposit",
        data={
            "amount": "100",
            "category": "deposit_opening",
            "note": "",
            "op_date": tomorrow,
        },
        headers=_HX,
    )

    assert response.status_code == 422
    assert OP_DATE_FUTURE_ERROR in response.text
    assert f'value="{tomorrow}"' in response.text
    assert _cash_count(session) == 0


def test_web_withdraw_malformed_date_gets_the_other_message(client, session):
    """D-12: a typo and a future date are different mistakes with different
    messages, and the 422 never shows the wrong one."""
    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": "15.08.2026",
        },
        headers=_HX,
    )

    assert response.status_code == 422
    assert OP_DATE_FORMAT_ERROR in response.text
    assert OP_DATE_FUTURE_ERROR not in response.text
    assert _cash_count(session) == 0


def test_web_withdraw_date_survives_the_negative_balance_confirm(client, session):
    """D-05 + DATE-01 through the route: «Снять всё равно» re-POSTs the
    RE-RENDERED form, so the back-date has to come back in that form's value=
    or the confirmed withdrawal would silently land on today."""
    back_date = _days_from_today(-6)
    payload = {
        "amount": "50,00",
        "category": "withdrawal_supplier",
        "note": "",
        "op_date": back_date,
    }

    warn = client.post("/finance/withdraw", data=payload, headers=_HX)
    assert warn.status_code == 200
    assert "Баланс уйдёт в минус" in warn.text
    assert _cash_count(session) == 0
    # The value the confirm button will re-submit is the one that was typed.
    assert f'value="{back_date}"' in warn.text

    confirmed = client.post(
        "/finance/withdraw", data={**payload, "confirm": "1"}, headers=_HX
    )
    assert confirmed.status_code == 200
    assert _last_movement(session).business_date == back_date


def test_web_withdraw_success_resets_the_date_to_today(client, session):
    """_movement_success renders a FRESH empty form, so the next entry starts
    from today rather than inheriting the previous back-date."""
    record_cash_movement(session, category="sale", amount_cents=10000)
    today = local_today_iso(settings.display_tz)

    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": _days_from_today(-12),
        },
        headers=_HX,
    )

    assert response.status_code == 200
    assert f'value="{today}" max="{today}"' in response.text


def test_web_withdraw_empty_date_stamps_today(client, session):
    """An omitted date is not an error — the write path supplies today's local
    day, never a column default (DATE-08's NULL sentinel stays intact for the
    sync path only)."""
    record_cash_movement(session, category="sale", amount_cents=10000)

    response = client.post(
        "/finance/withdraw",
        data={
            "amount": "15,00",
            "category": "withdrawal_supplier",
            "note": "",
            "op_date": "",
        },
        headers=_HX,
    )

    assert response.status_code == 200
    assert _last_movement(session).business_date == local_today_iso(settings.display_tz)
