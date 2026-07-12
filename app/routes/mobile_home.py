"""Mobile home (D-03): static 8-tile grid, no service call."""

from fastapi import APIRouter, Request

from app.routes import templates

router = APIRouter()


@router.get("/m/")
def mobile_home(request: Request):
    return templates.TemplateResponse(request, "mobile_pages/home.html", {})
