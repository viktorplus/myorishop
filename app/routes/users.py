"""Admin user-management routes (USER-01..04): thin over app/services/users.py.

Registered in app/main.py behind `require_role("administrator")` (ROLE-03), so
these handlers never re-check the role — the include_router dependency is the
server-side boundary. Every validation / creation / reset rule stays in the fat
user service (V5); these routes only wire HTTP → service → template swap
(warehouses precedent).

Paths: GET /settings/users (page + HX rows), POST /settings/users (create),
POST /settings/users/{id}/deactivate|reactivate|reset-password.

CLAUDE.md safety: a raw / new password is hashed in the service and is NEVER
echoed back into any rendered fragment or logged.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.routes import templates
from app.services.users import (
    create_user,
    deactivate_user,
    list_users,
    reactivate_user,
    reset_password,
)

router = APIRouter()

# Neutral success lines (UI-SPEC Copywriting Contract, lines 133-136). No green.
USER_CREATED_NOTICE = "Пользователь создан."
USER_DEACTIVATED_NOTICE = "Пользователь отключён."
USER_REACTIVATED_NOTICE = "Пользователь активирован."
PASSWORD_RESET_NOTICE = "Пароль сброшен."


def _rows_context(session: Session, **extra) -> dict:
    """Shared context for the users-table partial (all users + optional flags)."""
    return {"users": list_users(session), **extra}


@router.get("/settings/users")
def users_page(request: Request, session: Session = Depends(get_session)):
    context = _rows_context(session)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/user_rows.html", context)
    return templates.TemplateResponse(request, "pages/users.html", context)


@router.post("/settings/users")
def user_create(
    request: Request,
    display_name: str = Form(""),
    login: str = Form(""),
    role: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    _, errors = create_user(
        session, display_name=display_name, login=login, role=role, password=password
    )
    if errors:
        # The create form lives in pages/users.html OUTSIDE #users-table and is
        # not swapped, so the operator's typed values are preserved naturally;
        # the inline errors render at the top of the refreshed table region.
        context = _rows_context(session, errors=errors)
        return templates.TemplateResponse(
            request, "partials/user_rows.html", context, status_code=422
        )
    context = _rows_context(session, notice=USER_CREATED_NOTICE)
    return templates.TemplateResponse(request, "partials/user_rows.html", context)


@router.post("/settings/users/{user_id}/deactivate")
def user_deactivate(
    request: Request, user_id: str, session: Session = Depends(get_session)
):
    # Identity is server-derived (never a form field): the acting admin comes
    # from request.state.user set by the guard. deactivate_user refuses the
    # actor's own id server-side (USER-03 self-lockout guard, T-25-05-03).
    actor = getattr(request.state, "user", None)
    ok, errors = deactivate_user(
        session, user_id, actor_id=actor.id if actor is not None else ""
    )
    if not ok:
        context = _rows_context(session, errors=errors)
        return templates.TemplateResponse(
            request, "partials/user_rows.html", context, status_code=422
        )
    context = _rows_context(session, notice=USER_DEACTIVATED_NOTICE)
    return templates.TemplateResponse(request, "partials/user_rows.html", context)


@router.post("/settings/users/{user_id}/reactivate")
def user_reactivate(
    request: Request, user_id: str, session: Session = Depends(get_session)
):
    ok = reactivate_user(session, user_id)
    context = _rows_context(
        session, notice=USER_REACTIVATED_NOTICE if ok else None
    )
    return templates.TemplateResponse(request, "partials/user_rows.html", context)


@router.post("/settings/users/{user_id}/reset-password")
def user_reset_password(
    request: Request,
    user_id: str,
    new_password: str = Form(""),
    session: Session = Depends(get_session),
):
    user, errors = reset_password(session, user_id, new_password)
    if errors:
        # Unknown id → refresh the whole table with the error. A blank password
        # is a field-level error → re-render just this row's reset fragment with
        # the inline message (the password is never echoed back).
        if "user" in errors:
            context = _rows_context(session, errors=errors)
            return templates.TemplateResponse(
                request, "partials/user_rows.html", context, status_code=422
            )
        context = {"user": session.get(User, user_id), "reset_error": errors["password"]}
        return templates.TemplateResponse(
            request, "partials/user_reset.html", context, status_code=422
        )
    context = {"user": user, "reset_done": True}
    return templates.TemplateResponse(request, "partials/user_reset.html", context)
