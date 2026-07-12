"""Phase 11 Plan 01 foundation tests: mobile_client_factory + batch_card_picker.html.

Neither the real mobile routers nor app.main registration exist yet (that
happens in Plans 02-09) — this file only proves the two pieces of shared
foundation this plan builds actually work, using a throwaway stub router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session

probe_router = APIRouter()


@probe_router.get("/probe")
def probe(session: Session = Depends(get_session)):
    # Proves the mobile_client_factory session override actually wires up:
    # a trivial query against the injected session must succeed.
    session.execute(select(1))
    return {"ok": True}


def test_mobile_client_factory_session_override_round_trips(mobile_client_factory):
    client = mobile_client_factory(probe_router)
    response = client.get("/probe")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def _render_batch_card_picker(**context):
    from app.routes import templates

    template = templates.get_template("mobile_partials/batch_card_picker.html")
    context.setdefault("pick_url", "/m/sales/step/batch")
    return template.render(**context)


def test_batch_card_picker_renders_all_four_fields_and_selected_state(session, product, warehouse):
    from app.core import new_id
    from app.models import Batch

    b1 = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2027-01-15",
        price_cents=1500,
        location="Полка 1",
        comment="Хрупкое",
        quantity=5,
    )
    b2 = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry=None,
        price_cents=None,
        location=None,
        comment=None,
        quantity=2,
    )
    session.add_all([b1, b2])
    session.commit()

    html = _render_batch_card_picker(
        code=product.code,
        batch_id=b1.id,
        batches=[b1, b2],
        selected_batch_id=b1.id,
    )

    assert "Цена:" in html
    assert "Срок годности:" in html
    assert "Остаток:" in html
    assert 'class="mobile-card selected"' in html
    assert "Полка 1" in html
    assert "Хрупкое" in html
    assert "Цена: —" in html
    assert "без срока" in html


def test_batch_card_picker_empty_state_blocks_no_batches(session, product, warehouse):
    html = _render_batch_card_picker(
        code=product.code,
        batch_id="",
        batches=[],
        selected_batch_id=None,
        show_empty=True,
    )

    assert "Нет партий с остатком." in html
    assert "mobile-card" not in html


def test_batch_card_picker_auto_note_for_single_batch(session, product, warehouse):
    from app.core import new_id
    from app.models import Batch

    solo = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=3,
    )
    session.add(solo)
    session.commit()

    html = _render_batch_card_picker(
        code=product.code,
        batch_id=solo.id,
        batches=[solo],
        selected_batch_id=solo.id,
        auto_note=True,
    )

    assert "Партия выбрана автоматически — единственная" in html


def test_batch_card_picker_never_uses_safe_filter():
    # Guards the static file itself (T-11-02), independent of any render.
    from pathlib import Path

    text = Path("app/templates/mobile_partials/batch_card_picker.html").read_text(encoding="utf-8")
    assert "| safe" not in text
