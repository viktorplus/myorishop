"""USER-05 attribution proof: contextvars -> sync-`def` threadpool propagation.

The phase's single riskiest mechanism (25-RESEARCH Pitfall 4 / Assumption A1):
the async `auth_guard` sets a `ContextVar` current-user, but every write
endpoint is a SYNC `def` that FastAPI runs in a threadpool. AnyIO's
`run_in_threadpool` copies the calling context into the worker thread, so the
contextvar SHOULD survive the hop — but that MUST be proven end to end, not just
asserted in a same-thread unit test.

These tests drive the REAL app-level guard (`anon_client`, no override), log a
known user in through `POST /login`, then POST a real receipt and a real cash
movement through their actual endpoints and assert the persisted rows carry
`author_id == user.id` (contextvars propagated) and `created_by ==
user.display_name`. A second user proves attribution is per-request, not a
global singleton. If any of these fail, contextvars propagation does NOT hold
and the documented fallback (explicit-parameter threading) is required.
"""

import re
from datetime import date

from sqlalchemy import select

from app.config import settings
from app.core import local_day_bounds_utc, new_id
from app.models import CashMovement, Operation, User, Warehouse
from app.services import auth
from app.services.ledger import next_seq
from app.services.operations import history_view
from app.services.reports import sales_profit_report

# A fixed day + a safely-mid-day UTC timestamp: 10:00 UTC on 2026-07-10 maps to
# 2026-07-10 in every realistic display_tz (UTC-10..UTC+13), so the sales-report
# period filter (which resolves from=to=this day into local bounds) always
# contains these rows regardless of the machine's configured timezone.
FILTER_DAY = date(2026, 7, 10)
FILTER_DAY_ISO = FILTER_DAY.isoformat()
FILTER_MID_DAY_UTC = "2026-07-10T10:00:00+00:00"


def _seed_user(session, *, login, display_name, password="pw", role="operator"):
    """Persist one active user with a real Argon2id hash for a login round-trip."""
    user = User(
        id=new_id(),
        login=login,
        display_name=display_name,
        role=role,
        password_hash=auth.hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _seed_warehouse(session, *, name="Склад атрибуции"):
    """Persist one active warehouse so a receipt POST has a target."""
    warehouse = Warehouse(id=new_id(), name=name)
    session.add(warehouse)
    session.commit()
    return warehouse


def _csrf_token(client) -> str:
    """Scrape the session CSRF token from the rendered login page hidden field."""
    html = client.get("/login").text
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "login page must render a csrf_token hidden field"
    return match.group(1)


def _post_receipt(client, session, *, code, warehouse_id):
    """POST a real receipt through the receipts router (reaches record_operation)."""
    token = _csrf_token(client)
    resp = client.post(
        "/receipts",
        data={
            "code": code,
            "name": "Товар атрибуции",
            "qty": "3",
            "cost": "10",
            "sale": "15",
            "warehouse_id": warehouse_id,
            "batch_choice": "new",
        },
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 200, resp.text
    return resp


def _post_deposit(client, *, amount="100", category="deposit_opening"):
    """POST a real cash deposit (reaches record_cash_movement)."""
    token = _csrf_token(client)
    resp = client.post(
        "/finance/deposit",
        data={"amount": amount, "category": category, "note": ""},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 200, resp.text
    return resp


def test_attribution_receipt_stamps_logged_in_author(anon_client, session, login):
    # Log a known user in through the REAL guard, then POST a receipt that
    # reaches record_operation via the def-endpoint threadpool.
    user = _seed_user(session, login="anna", display_name="Анна Оператор")
    warehouse = _seed_warehouse(session)
    assert login(anon_client, "anna", "pw").status_code == 303

    _post_receipt(anon_client, session, code="ATTR-001", warehouse_id=warehouse.id)

    op = session.scalars(
        select(Operation).where(Operation.type == "receipt")
    ).first()
    assert op is not None
    # Contextvars survived the sync-def threadpool hop (Pitfall 4 PROVEN):
    assert op.author_id == user.id
    assert op.created_by == user.display_name


def test_attribution_cash_movement_stamps_logged_in_author(anon_client, session, login):
    user = _seed_user(session, login="boris", display_name="Борис Кассир")
    assert login(anon_client, "boris", "pw").status_code == 303

    _post_deposit(anon_client)

    mv = session.scalars(select(CashMovement)).first()
    assert mv is not None
    assert mv.author_id == user.id
    assert mv.created_by == user.display_name


def test_attribution_is_per_request_not_global(anon_client, session, login):
    # Two different logged-in users must stamp THEIR OWN id — proving the
    # contextvar is request-scoped, not a leaked global singleton.
    user_a = _seed_user(session, login="anna", display_name="Анна")
    user_b = _seed_user(session, login="boris", display_name="Борис")
    warehouse = _seed_warehouse(session)
    assert user_a.id != user_b.id

    # User A records a receipt.
    assert login(anon_client, "anna", "pw").status_code == 303
    _post_receipt(anon_client, session, code="ATTR-A", warehouse_id=warehouse.id)
    anon_client.post("/logout", follow_redirects=False)

    # User B records a different receipt on the same client.
    assert login(anon_client, "boris", "pw").status_code == 303
    _post_receipt(anon_client, session, code="ATTR-B", warehouse_id=warehouse.id)

    op_a = session.scalars(
        select(Operation).where(Operation.type == "receipt", Operation.author_id == user_a.id)
    ).first()
    op_b = session.scalars(
        select(Operation).where(Operation.type == "receipt", Operation.author_id == user_b.id)
    ).first()
    assert op_a is not None and op_b is not None
    assert op_a.author_id == user_a.id
    assert op_b.author_id == user_b.id
    assert op_a.author_id != op_b.author_id


def _seed_sale_op(session, product, *, author_id, created_by, qty=1, price_cents=1000):
    """Direct-insert one sale Operation with an explicit author_id + created_at.

    Bypasses record_operation on purpose (like conftest.past_sale): it stamps
    author_id from the request contextvar, but these read-only filter tests need
    to seed rows attributed to arbitrary users AND a pre-auth NULL-author row.
    Does NOT touch stock projections — for read-only history/report proofs only.
    """
    op = Operation(
        id=new_id(),
        type="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=price_cents // 2,
        unit_price_cents=price_cents,
        author_id=author_id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=FILTER_MID_DAY_UTC,
        created_by=created_by,
    )
    session.add(op)
    session.commit()
    return op


def test_filter_by_user_history(client, session, product):
    # Two attributed users + one pre-auth NULL-author row (frozen "operator").
    user_a = _seed_user(session, login="anna", display_name="Анна А")
    user_b = _seed_user(session, login="boris", display_name="Борис Б")
    _seed_sale_op(session, product, author_id=user_a.id, created_by=user_a.display_name)
    _seed_sale_op(session, product, author_id=user_b.id, created_by=user_b.display_name)
    _seed_sale_op(session, product, author_id=None, created_by="operator")

    # Service: filtering by user_a returns ONLY user_a's rows.
    filtered = history_view(session, author_id=user_a.id)
    assert {r["op"].author_id for r in filtered["rows"]} == {user_a.id}
    assert filtered["author_id"] == user_a.id

    # Service: the unfiltered view keeps the pre-auth NULL-author row (LEFT
    # OUTER JOIN never drops it) and surfaces author=None so the template falls
    # back to the frozen created_by text.
    unfiltered = history_view(session)
    all_authors = {r["op"].author_id for r in unfiltered["rows"]}
    assert {user_a.id, user_b.id, None} <= all_authors
    null_row = next(r for r in unfiltered["rows"] if r["op"].author_id is None)
    assert null_row["author"] is None

    # HTTP: the pre-auth row renders as a muted «operator» in the unfiltered
    # view, and is EXCLUDED once a user is selected (route passes author through).
    unfiltered_html = client.get("/history").text
    assert 'class="muted">operator<' in unfiltered_html
    filtered_html = client.get(f"/history?author={user_a.id}").text
    assert 'class="muted">operator<' not in filtered_html


def test_filter_by_user_reports(client, session, product):
    user_a = _seed_user(session, login="anna", display_name="Анна")
    user_b = _seed_user(session, login="boris", display_name="Борис")
    _seed_sale_op(session, product, author_id=user_a.id, created_by=user_a.display_name, qty=2)
    _seed_sale_op(session, product, author_id=user_b.id, created_by=user_b.display_name, qty=5)
    _seed_sale_op(session, product, author_id=None, created_by="operator", qty=3)

    start_iso, end_iso = local_day_bounds_utc(FILTER_DAY, FILTER_DAY, settings.display_tz)

    # Service: author filter narrows totals to that operator; None = all authors.
    rep_a = sales_profit_report(session, start_iso, end_iso, user_a.id)
    assert rep_a["totals"]["units_sold"] == 2
    rep_all = sales_profit_report(session, start_iso, end_iso)
    assert rep_all["totals"]["units_sold"] == 10  # 2 + 5 + 3 (NULL-author included)

    # HTTP: /reports/sales?author=<id> passes the filter through the route —
    # only user_a's 2 units show, vs 10 for the unfiltered period.
    html_a = client.get(
        f"/reports/sales?from={FILTER_DAY_ISO}&to={FILTER_DAY_ISO}&author={user_a.id}"
    ).text
    assert '<td class="num">2</td>' in html_a
    html_all = client.get(
        f"/reports/sales?from={FILTER_DAY_ISO}&to={FILTER_DAY_ISO}"
    ).text
    assert '<td class="num">10</td>' in html_all
