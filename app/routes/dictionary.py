"""Reference dictionary pages (CAT-02): thin routes, writes in the service.

PD-5: the autofill lookup lives HERE at GET /dictionary/lookup (not under
/products) — the dictionary router owns all dictionary reads, keeping
wave-3 file ownership conflict-free.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.dictionary import add_entry, list_entries, lookup, update_entry

router = APIRouter()

# Route order: the literal /dictionary/lookup MUST stay declared before the
# parameterized /dictionary/{entry_id} route below.


@router.get("/dictionary")
def dictionary_page(request: Request, session: Session = Depends(get_session)):
    context = {"entries": list_entries(session), "errors": {}, "form": {}}
    return templates.TemplateResponse(request, "pages/dictionary.html", context)


# Formalized under Phase 12 (PRICE-03) — shipped ad-hoc on feat/catalogs-pricing, now a permanent feature.
@router.get("/dictionary/lookup")
def dictionary_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    session: Session = Depends(get_session),
):
    # Pattern 2 (D-23): the SERVER decides fill vs no-op; htmx ignores 204.
    # Pitfall 5: a non-empty operator name is never overwritten.
    entry = lookup(session, code)
    if entry is None or name.strip():
        return Response(status_code=204)
    context = {"name": entry.name, "autofilled": True}
    return templates.TemplateResponse(request, "partials/name_input.html", context)


@router.post("/dictionary")
def dictionary_add(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    entry, errors = add_entry(session, code=code, name=name)
    context = {
        "entries": list_entries(session),
        "errors": errors,
        "form": {"code": code, "name": name} if errors else {},
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_rows.html",
        context,
        status_code=422 if errors else 200,
    )


@router.post("/dictionary/{entry_id}")
def dictionary_update(
    request: Request,
    entry_id: str,
    code: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    entry, errors = update_entry(session, entry_id, code=code, name=name)
    if "entry" in errors:
        raise HTTPException(status_code=404, detail="unknown dictionary entry")
    context = {
        "entries": list_entries(session),
        "errors": errors,
        "form": {},
        "error_entry_id": entry_id if errors else None,
        "error_form": {"code": code, "name": name} if errors else None,
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_rows.html",
        context,
        status_code=422 if errors else 200,
    )
