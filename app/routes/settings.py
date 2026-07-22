"""Settings hub page (D-06/D-08): thin route, all summary logic in the service.

Mirrors app/routes/backup.py's exact shape — one service call, one context
dict, one template. Zero query/form params accepted (V12).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services import update
from app.services.settings import save_autosync_config, settings_summary
from app.services.sync_client import DEFAULT_INTERVAL_SECONDS

router = APIRouter()


def _render_update_panel(request: Request, update_status, *, outcome=None, manual=False):
    """Render the shared #update-panel partial (always 200; T-32-03).

    The three update routes are thin: they call the service, then hand the
    resulting `UpdateStatus` (+ an optional apply `outcome`) to this one partial.
    A failure is a fixed Russian caption in the partial — never a 5xx or a raw
    error byte (T-29-07).
    """
    return templates.TemplateResponse(
        request,
        "partials/update_panel.html",
        {"update_status": update_status, "outcome": outcome, "manual": manual},
    )


@router.get("/settings")
def settings_page(request: Request, session: Session = Depends(get_session)):
    context = settings_summary(session, Path(settings.backup_dir))
    return templates.TemplateResponse(request, "pages/settings.html", context)


@router.post("/settings/sync")
def settings_save_sync(
    request: Request,
    auto_enabled: str = Form(""),
    auto_interval_seconds: str = Form(""),
    session: Session = Depends(get_session),
):
    """Persist the D-15 auto-sync config (admin-gated via the settings router).

    The checkbox posts `auto_enabled=on` only when checked (absent = disabled).
    The interval is parsed leniently: an unparseable value falls back to the
    default and the service clamps it into 60..3600 — a bad input is never a
    5xx (D-15). CSRF is carried by the base body `hx-headers`; the token is
    NEVER shown (T-29-07).
    """
    enabled = auto_enabled.strip().lower() in ("on", "true", "1", "yes")
    try:
        interval = int(auto_interval_seconds)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_SECONDS
    save_autosync_config(session, enabled=enabled, interval_seconds=interval)

    context = settings_summary(session, Path(settings.backup_dir))
    context["sync_saved"] = True
    return templates.TemplateResponse(request, "pages/settings.html", context)


@router.post("/settings/update/check")
def settings_update_check(request: Request):
    """UPD-07: manual «Проверить обновления» — always 200 with the #update-panel.

    `update.check_for_update` is broadly guarded (offline ⇒ a benign "offline"
    status, never a raise), so this route only shapes the partial. A manual check
    shows the offline caption; the startup check stays silent (manual=True here).
    """
    status = update.check_for_update()
    return _render_update_panel(request, status, manual=True)


@router.post("/settings/update/apply")
def settings_update_apply(request: Request):
    """UPD-03: notify-and-confirm apply — verify-before-unpack, always 200.

    The click IS the explicit confirmation (no second modal). The verified core
    (`update.apply`) either stages a bundle for the launcher ("applying") or —
    on the hard verify gate failing — raises `UpdateVerificationError`, surfaced
    as the `.error-block` verification-failed caption (nothing was installed).
    An offline/no-op apply leaves the notice up so the admin can retry. The
    release notes are echoed AUTOESCAPED via the cached status (T-32-01).
    """
    status = update.get_cached_status()
    outcome = None
    try:
        result = update.apply()
        if result.state == "staged":
            outcome = "applying"
    except update.UpdateVerificationError:
        outcome = "verification_failed"
    except Exception:
        # Any post-verify apply/migration failure ⇒ matched-pair rollback
        # reassurance; never a raw error/stack into the panel (T-29-07).
        outcome = "rollback"
    return _render_update_panel(request, status, outcome=outcome, manual=True)


@router.post("/settings/update/dismiss")
def settings_update_dismiss(request: Request):
    """UPD-03 «Позже»: dismiss the offered notice for this session (always 200).

    Renders the empty panel so the notice is gone from the current DOM; a later
    manual/startup check re-populates it if the update is still available.
    """
    return _render_update_panel(request, None)
