"""Export page + routes (BCK-02): thin routes, all CSV work in the service.

Security V12 / T-06-09: NEITHER of the three CSV endpoints accepts a
filename, path, Form or Query parameter — each is a hardcoded server-side
dump of one table (mirrors app/routes/backup.py's established V12 pattern).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services import export as export_service

router = APIRouter()


@router.get("/export")
def export_page(request: Request):
    return templates.TemplateResponse(request, "pages/export.html", {})


@router.get("/export/products.csv")
def export_products(session: Session = Depends(get_session)):
    return export_service.stream_products_csv(session)


@router.get("/export/sales.csv")
def export_sales(session: Session = Depends(get_session)):
    return export_service.stream_sales_csv(session)


@router.get("/export/customers.csv")
def export_customers(session: Session = Depends(get_session)):
    return export_service.stream_customers_csv(session)
