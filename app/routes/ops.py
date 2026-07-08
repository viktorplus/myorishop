"""POST /ops — record a stock correction, return the HTMX partial (D-11/D-12/D-15).

Typed Form fields are the input validation (threat T-1-01): garbage in
qty_delta gets a 422 from FastAPI before any business code runs.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.ledger import ledger_view, record_operation

router = APIRouter()


@router.post("/ops")
def create_op(
    request: Request,
    product_id: str = Form(...),
    qty_delta: int = Form(...),
    session: Session = Depends(get_session),
):
    # Correction is the one op type needing no prices (walking skeleton).
    record_operation(session, type_="correction", product_id=product_id, qty_delta=qty_delta)
    context = ledger_view(session)
    return templates.TemplateResponse(request, "partials/ledger_rows.html", context)
