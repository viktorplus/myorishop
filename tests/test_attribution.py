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

from sqlalchemy import select

from app.core import new_id
from app.models import CashMovement, Operation, User, Warehouse
from app.services import auth


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
