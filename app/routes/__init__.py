"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import settings as _config_settings
from app.core import format_cents, format_ru_date, iso_to_local
from app.db import SessionLocal
from app.models import (
    CASH_BUCKET_LABELS,
    CASH_CATEGORIES,
    CONTACT_KINDS,
    OPERATION_TYPE_LABELS,
    ROLES,
    WRITEOFF_REASONS,
    SyncState,
)
from app.services.security import session_csrf
from app.services.sync_client import (
    SyncResult,
    format_sync_message,
    unsynced_count,
)


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


def _sync_status_context(request: Request) -> dict:
    """Inject the sync surface (message + last-sync line + badge) into EVERY page.

    Phase 29 (D-01/D-02): base.html renders `partials/sync_status.html` on first
    paint for both roles, so `sync_message`, `last_sync_line` and `unsynced` must
    be present on every render without each route re-passing them (mirrors
    `_auth_context`). Opens its own short-lived `SessionLocal()` session (the
    Plan-01 partial index keeps the count cheap) and reads the stored last result
    (`last_result`) + last-sync time; the never-synced row yields an empty message
    and the "Ещё не синхронизировано" line.

    SRV-03: any error (missing DB / sync_state hiccup) is swallowed to a neutral
    default so a sync problem can NEVER break page rendering. The token is never
    read here (T-29-07).

    quick-260721-egc: also exposes is_server_db (SRV-01/02: the deployed central
    server is the only role that ever runs on postgresql+..., every local client
    defaults to sqlite:///) so base.html can style the nav distinctly. Computed
    once up front — it's a pure string check on already-loaded settings, never
    touches the DB, so it cannot itself raise the exception this fallback guards
    against and must be identical in both branches below."""
    is_server_db = _config_settings.database_url.startswith("postgresql")
    try:
        with SessionLocal() as session:
            # WR-02: READ-ONLY on the render path — never INSERT the sync_state
            # singleton here. get_or_create_sync_state did add()+flush() on a fresh
            # install, taking a SQLite write/reserved lock on EVERY page render
            # (the session then rolls back, so it never even persisted) and
            # contending with the background tick's writes. A missing row simply
            # means "never synced".
            row = session.get(SyncState, 1)
            unsynced = unsynced_count(session)
            # First paint shows the LAST stored result string (already a fixed D-12
            # message, T-29-07); the last-sync line is derived from the row (the
            # dummy status does not affect it — see format_sync_message, which
            # treats a None row as "Ещё не синхронизировано").
            _, last_sync_line = format_sync_message(
                SyncResult(status="ok"), row, _config_settings.display_tz
            )
            return {
                "sync_message": (row.last_result if row else "") or "",
                "last_sync_line": last_sync_line,
                "unsynced": unsynced,
                "sync_configured": bool(_config_settings.sync_server_url),
                "is_server_db": is_server_db,
            }
    except Exception:
        return {
            "sync_message": "",
            "last_sync_line": "Ещё не синхронизировано",
            "unsynced": 0,
            "sync_configured": bool(_config_settings.sync_server_url),
            "is_server_db": is_server_db,
        }


templates = Jinja2Templates(
    directory="app/templates",
    context_processors=[_auth_context, _sync_status_context],
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
