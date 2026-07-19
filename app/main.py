"""FastAPI application entry point: lifespan backup + static mount + routers."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Aliased to config_settings so it does not collide with the `settings` route
# submodule imported below (app/routes/settings.py).
from app.config import settings as config_settings
from app.routes import (
    auth,
    backup,
    catalogs,
    categories,
    corrections,
    customers,
    dictionary,
    export,
    finance,
    history,
    home,
    mobile_corrections,
    mobile_customers,
    mobile_finance,
    mobile_history,
    mobile_home,
    mobile_products,
    mobile_receipts,
    mobile_reports,
    mobile_returns,
    mobile_sales,
    mobile_search,
    mobile_transfers,
    mobile_writeoff,
    products,
    receipts,
    reports,
    returns,
    sales,
    settings,
    sync,
    transfers,
    users,
    warehouses,
    writeoffs,
)

# Module-qualified import: tests monkeypatch backup_service.startup_backup
# as ONE seam (PD-13).
from app.services import backup as backup_service
from app.services.security import NotAuthenticated, auth_guard, require_role


@asynccontextmanager
async def lifespan(app: FastAPI):
    # D-09: snapshot the DB BEFORE serving requests; the sync call is
    # intentional — startup must block until the backup finishes.
    backup_service.startup_backup()
    yield


# AUTH-01/ROLE-02: a SINGLE app-level dependency guards every current + future
# router (deny-by-default). Adding the guard per-router would be 33 chances to
# forget one; the app-level dependency is the "every route" guarantee. The
# StaticFiles mount below is NOT a router, so app-level dependencies never apply
# to it — /static stays public automatically.
app = FastAPI(
    title="MyOriShop",
    lifespan=lifespan,
    dependencies=[Depends(auth_guard)],
)
# AUTH-03: itsdangerous-signed session cookie (survives refresh; offline). Only
# user_id + csrf are ever stored. same_site=lax; https_only=False for localhost.
app.add_middleware(
    SessionMiddleware,
    secret_key=config_settings.secret_key,
    same_site="lax",
    https_only=False,
)


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated) -> Response:
    """Turn a guard NotAuthenticated into an auth redirect (AUTH-01, Pitfall 3).

    HTMX 2 does NOT swap 4xx responses (base.html htmx-config marks [45].. as
    non-swapping/error), so a naive 303 body on an HX request would silently
    vanish. For an HX request return 401 + HX-Redirect (HTMX performs a full
    navigation); for a plain request return a 303 redirect.
    """
    if request.headers.get("HX-Request"):
        return Response(status_code=401, headers={"HX-Redirect": exc.redirect})
    return RedirectResponse(exc.redirect, status_code=303)


app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Auth surfaces are public (listed in security.PUBLIC_PATHS) — /login /logout /setup.
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(catalogs.router)
# ROLE-02/03: the admin-only routers (user management, warehouses, dictionaries,
# settings) are gated SERVER-SIDE with require_role — the menu-hide in Plan 06 is
# cosmetic only. require_role reads request.state.user (attached by the app-level
# auth_guard, which runs first), so an operator hitting any of these gets a 403
# «Доступ только для администратора.» while an administrator (admin ⊇ operator)
# passes. Every OTHER router below stays operator-accessible — an operator needs
# products + warehouse pickers during receipts/sales (ROLE-03 lists ONLY these
# four sections as admin-only).
app.include_router(
    warehouses.router, dependencies=[Depends(require_role("administrator"))]
)
app.include_router(
    dictionary.router, dependencies=[Depends(require_role("administrator"))]
)
app.include_router(receipts.router)
app.include_router(sales.router)
app.include_router(customers.router)
app.include_router(backup.router)
app.include_router(writeoffs.router)
app.include_router(transfers.router)
app.include_router(returns.router)
app.include_router(corrections.router)
app.include_router(history.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(finance.router)
app.include_router(
    settings.router, dependencies=[Depends(require_role("administrator"))]
)
# USER-01..04 / ROLE-03: the admin user-management surface at /settings/users.
app.include_router(
    users.router, dependencies=[Depends(require_role("administrator"))]
)
# SYNC-09: the token-authenticated sync tree. NO `dependencies=` here — unlike the
# admin routers above it is NOT gated by the app-level auth_guard (security.py
# returns early for the SYNC_PATH_PREFIX), but it is NOT unguarded: every route
# declares Depends(require_device), a per-device Bearer gate strictly NARROWER
# than a session cookie (a browser cannot forge an Authorization header).
app.include_router(sync.router)
app.include_router(mobile_home.router)
app.include_router(mobile_sales.router)
app.include_router(mobile_receipts.router)
app.include_router(mobile_search.router)
app.include_router(mobile_writeoff.router)
app.include_router(mobile_corrections.router)
app.include_router(mobile_products.router)
app.include_router(mobile_customers.router)
app.include_router(mobile_transfers.router)
app.include_router(mobile_returns.router)
app.include_router(mobile_history.router)
app.include_router(mobile_reports.router)
app.include_router(mobile_finance.router)
