"""Mobile Покупатели page (MOB-01): reuses customers.list_customers_view unchanged.

Thin route mirroring mobile_products.py's shape: one plain full-page GET, no
HX-partial branch. Each card links to the existing desktop customer-detail
page (GET /customers/{id}) — no new mobile detail route in this plan.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.customers import list_customers_view

router = APIRouter()


@router.get("/m/customers")
def mobile_customers(
    request: Request,
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = list_customers_view(session, page=page)
    return templates.TemplateResponse(request, "mobile_pages/customers.html", context)
