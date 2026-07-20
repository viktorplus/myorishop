"""FastAPI application entry point: lifespan backup + static mount + routers."""

import asyncio
import contextlib
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Aliased to config_settings so it does not collide with the `settings` route
# submodule imported below (app/routes/settings.py).
from app.config import settings as config_settings

# Module-qualified import: tests monkeypatch backup_service.startup_backup
# as ONE seam (PD-13).
from app.db import SessionLocal
from app.routes import (
    auth,
    backup,
    catalogs,
    categories,
    corrections,
    customers,
    devices,
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
from app.services import backup as backup_service
from app.services import sync_client
from app.services.security import NotAuthenticated, auth_guard, require_role
from app.services.sync_client import DEFAULT_INTERVAL_SECONDS


async def _auto_sync_iteration() -> int:
    """Run ONE auto-sync tick decision; return the interval to sleep (seconds).

    D-08: the on/off toggle + interval are read FRESH from `sync_state` at the
    top of every iteration (never captured once at startup) so flipping the
    toggle takes effect on the next tick. D-07: when auto-sync is enabled the
    blocking driver `sync_client.run_sync_tick` (which opens its OWN fresh
    Session and holds the shared `_run_lock`, D-09) is offloaded OFF the event
    loop via `anyio.to_thread.run_sync` — the sync Session never runs on the
    loop. D-08: the WHOLE iteration (config read + tick) is wrapped in a broad
    guard so ANY error — offline / httpx transport / a transient DB hiccup —
    is swallowed and the loop just silently skips this tick and never dies (no
    log spam). On such an error the default interval is returned so the loop
    retries later.
    """
    interval = DEFAULT_INTERVAL_SECONDS
    try:
        with SessionLocal() as session:
            enabled, interval = sync_client.read_autosync_config(session)
        if enabled:
            # WR-03: abandon_on_cancel=False (also anyio's default, pinned here
            # explicitly for intent) means that when the lifespan cancels this
            # loop on shutdown, anyio does NOT abandon the worker thread — the
            # awaiting task waits for run_sync_tick to finish its DB commit before
            # the CancelledError propagates. That bounds the shutdown wait so a
            # live sync_state commit never races engine teardown.
            await anyio.to_thread.run_sync(
                sync_client.run_sync_tick, abandon_on_cancel=False
            )
    except Exception:
        # D-08: offline / transport / transient DB error → silently skip.
        pass
    return interval


async def _auto_sync_loop() -> None:
    """The D-06 optional interval auto-sync loop.

    Zero-dependency asyncio loop (no APScheduler/Celery/Redis) started in the
    lifespan so it keeps syncing with the browser tab closed. Each pass reads
    the config fresh, offloads the tick, then sleeps for the (clamped) interval.
    """
    while True:
        interval = await _auto_sync_iteration()
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # D-09: snapshot the DB BEFORE serving requests; the sync call is
    # intentional — startup must block until the backup finishes.
    backup_service.startup_backup()
    # D-06: start the optional interval auto-sync AFTER the startup backup. The
    # loop reads its on/off toggle fresh each tick (D-08), so a fresh install
    # (auto_enabled default 0) simply idles until an admin enables it.
    auto_sync_task = asyncio.create_task(_auto_sync_loop())
    try:
        yield
    finally:
        # D-08: cancel the background loop cleanly on shutdown (suppress the
        # expected CancelledError so shutdown never raises or hangs).
        auto_sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await auto_sync_task


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
# user_id + csrf are ever stored. same_site=lax stays; https_only is now
# environment-driven (T-28-27) — False for localhost/run.bat and the test suite
# (plain HTTP), True on the VPS via SESSION_HTTPS_ONLY=true so the cookie carries
# the Secure flag on the public HTTPS domain.
app.add_middleware(
    SessionMiddleware,
    secret_key=config_settings.secret_key,
    same_site="lax",
    https_only=config_settings.session_https_only,
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
# SYNC-09: the admin device-token surface at /settings/devices. Admin-only for
# security, not tidiness — revocation is the ONLY mitigation for a stolen device
# token (there is no expiry, by decision), so an operator must not be able to
# mint or revoke device credentials. Same server-side boundary as /settings/users.
app.include_router(
    devices.router, dependencies=[Depends(require_role("administrator"))]
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
