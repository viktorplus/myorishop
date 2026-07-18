"""Auth routes (AUTH-01/03/04): login, logout, first-run admin setup.

Thin routes over the fat services (warehouses precedent): credential logic lives
in `app.services.auth.verify_password` and user creation in
`app.services.users.create_user`; this module only wires HTTP → session.

These three paths are the ONLY ones reachable without a session (they are listed
in `security.PUBLIC_PATHS`, so the app-level `auth_guard` returns early for them
and does not require CSRF on `POST /login` / `POST /setup`). `POST /logout` is a
state-change carrying the CSRF token via the auth_base `hx-headers`.

CLAUDE.md safety: a raw password is verified/hashed in the service and is never
echoed back into the re-rendered form or logged.
"""

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.routes import templates
from app.services.auth import verify_password
from app.services.users import count_users, create_user

router = APIRouter()

# UI-SPEC Copywriting Contract (lines 109-110). HTML-free, same message for an
# unknown login and a wrong password (login-oracle mitigation T-25-04-05).
BAD_CREDENTIALS_ERROR = "Неверный логин или пароль."
DEACTIVATED_ERROR = "Учётная запись отключена. Обратитесь к администратору."


def _redirect(target: str, request: Request) -> Response:
    """303 for a plain request; 204 + HX-Redirect for an HTMX request (Pitfall 3)."""
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": target})
    return RedirectResponse(target, status_code=303)


@router.get("/login")
def login_form(request: Request, session: Session = Depends(get_session)):
    # First-run self-close: with zero users there is nothing to log into — the
    # only path is /setup (AUTH-04).
    if count_users(session) == 0:
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "pages/login.html", {"login": ""})


@router.post("/login")
def login_submit(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    login = login.strip()
    user = session.scalar(select(User).where(User.login == login))
    # Verify the password BEFORE branching on is_active so a deactivated account
    # is not disclosed to someone who does not know the password (no enumeration
    # oracle); unknown login and wrong password share one generic message.
    if user is not None and verify_password(session, user, password):
        if user.is_active != 1:
            return templates.TemplateResponse(
                request,
                "pages/login.html",
                {"login": login, "error": DEACTIVATED_ERROR},
                status_code=422,
            )
        request.session["user_id"] = user.id  # AUTH-03
        return _redirect("/", request)
    # Bad credentials: ZERO session written, password cleared, login preserved.
    return templates.TemplateResponse(
        request,
        "pages/login.html",
        {"login": login, "error": BAD_CREDENTIALS_ERROR},
        status_code=422,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()  # AUTH-03: ends the session
    return _redirect("/login", request)


@router.get("/setup")
def setup_form(request: Request, session: Session = Depends(get_session)):
    # Self-close: once any user exists, /setup is no longer a valid surface.
    if count_users(session) > 0:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "pages/setup.html", {"form": {}, "errors": {}}
    )


@router.post("/setup")
def setup_submit(
    request: Request,
    display_name: str = Form(""),
    login: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    # Re-check server-side (closes the double-submit race): the first user must
    # be created exactly once, and only while the DB is empty (AUTH-04).
    if count_users(session) > 0:
        return RedirectResponse("/login", status_code=303)
    user, errors = create_user(
        session,
        display_name=display_name,
        login=login,
        role="administrator",
        password=password,
    )
    if errors:
        return templates.TemplateResponse(
            request,
            "pages/setup.html",
            {"form": {"display_name": display_name, "login": login}, "errors": errors},
            status_code=422,
        )
    request.session["user_id"] = user.id  # log the new admin straight in
    return _redirect("/", request)
