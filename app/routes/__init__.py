"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import settings as _config_settings
from app.core import format_cents, format_ru_date, iso_to_local
from app.models import (
    CASH_BUCKET_LABELS,
    CASH_CATEGORIES,
    CONTACT_KINDS,
    OPERATION_TYPE_LABELS,
    ROLES,
    WRITEOFF_REASONS,
)
from app.services.security import session_csrf


def _auth_context(request: Request) -> dict:
    """Inject current_user + csrf_token into EVERY template (Phase 25, AUTH-05).

    Mirrors the RU-label globals below: no route re-passes these. current_user
    is the user the guard attached to request.state (None for anon/first-run);
    csrf_token is the session synchronizer token (empty when no SessionMiddleware
    session exists in scope, e.g. bare mobile_client_factory tests).
    """
    return {
        "current_user": getattr(request.state, "user", None),
        "csrf_token": session_csrf(request) if "session" in request.scope else "",
    }


templates = Jinja2Templates(
    directory="app/templates", context_processors=[_auth_context]
)
# D-07: store UTC, display local; D-06: cents rendered only via helper.
# Aliased to _config_settings (not `settings`) so this package's own
# `settings` attribute-name namespace doesn't collide with the sibling
# route submodule app/routes/settings.py (D-06) — `from app.routes import
# settings` in app/main.py must resolve to that router module, not to this
# config instance (Python package attribute shadowing).
templates.env.filters["local_dt"] = lambda iso: iso_to_local(
    iso, _config_settings.display_tz
)
templates.env.filters["cents"] = format_cents
# LOT-03: batch expiry stored as ISO text; rendered dd.mm.yyyy in every surface.
templates.env.filters["ru_date"] = format_ru_date
# Phase 5 (D-16): expose RU-label constants to every template without every
# route re-passing them into its render context.
templates.env.globals["WRITEOFF_REASONS"] = WRITEOFF_REASONS
templates.env.globals["OPERATION_TYPE_LABELS"] = OPERATION_TYPE_LABELS
# Phase 16 (Pitfall 2): the manual-entry forms + cash history render category
# and bucket labels; expose them as globals so no template raises UndefinedError
# or blank-renders. CASH_BUCKETS stays server-side only (never rendered).
templates.env.globals["CASH_CATEGORIES"] = CASH_CATEGORIES
templates.env.globals["CASH_BUCKET_LABELS"] = CASH_BUCKET_LABELS
# Phase 21 (CUST-01..04): expose the RU contact-kind labels for
# customer_contacts.html the same established way as the constants above.
templates.env.globals["CONTACT_KINDS"] = CONTACT_KINDS
# Phase 25 (ROLE-01): expose the role allow-list (Latin key → RU label) so the
# role <select> and the role-conditioned menu-hide can read labels globally.
templates.env.globals["ROLES"] = ROLES
