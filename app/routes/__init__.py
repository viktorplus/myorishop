"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import settings as _config_settings
from app.core import (
    CURRENCIES,
    DEFAULT_CURRENCY,
    format_cents,
    format_money,
    format_ru_date,
    iso_to_local,
)
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


# Path prefix -> nav section table (Task 1, quick-260813-l0y): shared by both
# base.html and mobile_base.html so a nested screen highlights its owning
# section instead of nothing (each previously used a bare startswith on its
# OWN prefix only). Every prefix here is mutually exclusive by construction
# (no listed prefix is itself a prefix of another listed prefix) — keep that
# invariant when adding a new entry. "/settings" alone covers
# "/settings/users" via startswith, so it is not listed twice.
# "/returns"/"/m/returns" map to "history" for the shared table's
# completeness even though today that route only ever renders as an HTMX
# fragment inside /history's #return-slot (see
# partials/history_rows.html's hx-get="/returns?..."), never full page
# chrome — this repo's staleness check: the locked-scope note describing
# /returns as nav-highlightable does not match the route's current
# fragment-only behavior; the mapping is added anyway since it is harmless
# and forward-compatible, but is provable only via a direct nav_section()
# unit test, not an HTTP round-trip.
NAV_SECTION_PREFIXES: list[tuple[str, str]] = [
    ("/products", "products"),
    ("/batches", "products"),
    ("/receipts", "products"),
    ("/writeoff", "products"),
    ("/transfers", "products"),
    ("/corrections", "products"),
    ("/categories", "products"),
    ("/locations", "products"),
    ("/dictionary", "products"),
    ("/catalogs", "products"),
    ("/warehouses", "products"),
    ("/m/products", "products"),
    ("/m/batches", "products"),
    ("/m/receipts", "products"),
    ("/m/writeoff", "products"),
    ("/m/transfers", "products"),
    ("/m/corrections", "products"),
    ("/m/search", "products"),
    ("/sales", "sales"),
    ("/m/sales", "sales"),
    ("/customers", "customers"),
    ("/m/customers", "customers"),
    ("/returns", "history"),
    ("/m/returns", "history"),
    ("/history", "history"),
    ("/m/history", "history"),
    ("/reports", "reports"),
    ("/m/reports/expiry", "reports"),
    ("/finance", "finance"),
    ("/m/finance", "finance"),
    ("/settings", "settings"),
]


def nav_section(path: str) -> str | None:
    """Return the section owning `path` (first matching prefix), else None.

    None covers both "/" and "/m/" (the home tile owns no section) and any
    path outside the table — the status quo everywhere today (T-quick-260813-
    l0y-02: no wrong-but-unsafe render, worst case is "nothing highlighted").
    """
    for prefix, section in NAV_SECTION_PREFIXES:
        if path.startswith(prefix):
            return section
    return None


def batch_identity_label(batch, product) -> str:
    """Identity label for a batch: stored name wins, else derived, else bare product name.

    batch.name set -> that name verbatim (any expiry). batch.name unset with an
    expiry -> "{product.name} — dd.mm.yyyy" (format_ru_date). Neither -> bare
    product.name. Used by breadcrumb identity lines (Task 2/3, quick-260813-l0y)
    so an operator editing one of a product's several batches can tell which
    one is open.
    """
    if batch.name:
        return batch.name
    if batch.expiry:
        return f"{product.name} — {format_ru_date(batch.expiry)}"
    return product.name


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
# App version shown in the header title. Single source in app/__init__.py,
# exposed as a template global so no route re-passes it (mirrors the label
# constants below). Bumped on every completed-task commit (1.0 → 1.1 → …).
from app import __version__ as _app_version

templates.env.globals["APP_VERSION"] = _app_version
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
# CUR-01: the supported per-warehouse currencies (code → symbol) plus the
# default, exposed the same established way so the warehouse form's <select>
# and every amount-rendering surface read them globally.
templates.env.globals["CURRENCIES"] = CURRENCIES
templates.env.globals["DEFAULT_CURRENCY"] = DEFAULT_CURRENCY
# Renders an amount together with its currency symbol: {{ cents | money(w.currency) }}
templates.env.filters["money"] = format_money
# quick-260813-l0y: shared nav-highlight table + batch identity label, read by
# both base.html and mobile_base.html / the six breadcrumb-carrying templates.
templates.env.globals["nav_section"] = nav_section
templates.env.globals["batch_identity_label"] = batch_identity_label
