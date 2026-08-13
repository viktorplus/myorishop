"""Mobile batch edit screen tests (quick-260813-i28).

Mirrors app/routes/batches.py's desktop test shape via mobile_client_factory
(no CSRF token needed — mobile_client_factory's bare app has no auth_guard/
SessionMiddleware).
"""

from app.core import new_id
from app.models import Batch
from app.routes import mobile_batches
from app.services.catalog import PRICE_ERROR


def test_mobile_batch_edit_shows_readonly_rows_with_links(
    mobile_client_factory, session, product, warehouse
):
    seeded = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=5)
    session.add(seeded)
    session.commit()
    client = mobile_client_factory(mobile_batches.router)

    response = client.get(f"/m/batches/{seeded.id}/edit")
    assert response.status_code == 200
    assert f"/writeoff?code={product.code}" in response.text
    assert f"/transfers?code={product.code}" in response.text


def test_mobile_batch_update_saves_changes_and_redirects(
    mobile_client_factory, session, product, warehouse
):
    seeded = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=5)
    session.add(seeded)
    session.commit()
    client = mobile_client_factory(mobile_batches.router)

    response = client.post(
        f"/m/batches/{seeded.id}",
        data={
            "name": "Новая партия",
            "expiry": "",
            "location": "",
            "comment": "",
            "price": "12,50",
            "cost": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/m/search/product/{product.id}"
    session.expire_all()
    updated = session.get(Batch, seeded.id)
    assert updated.name == "Новая партия"
    assert updated.price_cents == 1250


def test_mobile_batch_update_invalid_expiry_rerenders_422(
    mobile_client_factory, session, product, warehouse
):
    seeded = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=5)
    session.add(seeded)
    session.commit()
    client = mobile_client_factory(mobile_batches.router)

    response = client.post(
        f"/m/batches/{seeded.id}",
        data={
            "name": "",
            "expiry": "not-a-date",
            "location": "",
            "comment": "",
            "price": "",
            "cost": "",
        },
    )
    assert response.status_code == 422
    assert "Укажите срок годности" in response.text


def test_mobile_batch_update_invalid_price_rejected(
    mobile_client_factory, session, product, warehouse
):
    seeded = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=5)
    session.add(seeded)
    session.commit()
    client = mobile_client_factory(mobile_batches.router)

    response = client.post(
        f"/m/batches/{seeded.id}",
        data={
            "name": "",
            "expiry": "",
            "location": "",
            "comment": "",
            "price": "abc",
            "cost": "",
        },
    )
    assert response.status_code == 422
    assert PRICE_ERROR in response.text


def test_mobile_batch_edit_unknown_id_404s(mobile_client_factory, session):
    client = mobile_client_factory(mobile_batches.router)
    response = client.get("/m/batches/no-such-batch/edit")
    assert response.status_code == 404


def test_mobile_batch_update_unknown_id_404s(mobile_client_factory, session):
    client = mobile_client_factory(mobile_batches.router)
    response = client.post(
        "/m/batches/no-such-batch",
        data={"name": "", "expiry": "", "location": "", "comment": "", "price": "", "cost": ""},
    )
    assert response.status_code == 404
