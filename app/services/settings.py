"""Settings hub service (D-06): composes existing warehouse/backup summaries.

No new business logic — just reads the two existing services' data and
shapes it for the /settings hub page (thin-route rule, mirrors
app/routes/backup.py's pattern).
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.services.backup import list_backups
from app.services.sync_client import (
    _clamp_interval,
    get_or_create_sync_state,
    read_autosync_config,
)
from app.services.warehouses import list_warehouses


def settings_summary(session: Session, backup_dir: Path) -> dict:
    """Warehouse count + last-backup timestamp + the D-15 auto-sync config.

    The auto-sync toggle + interval are read FRESH from `sync_state` (D-08) for
    the Settings «Синхронизация» control. The non-secret `sync_server_url` is
    surfaced read-only; the `sync_token` is a SECRET and is NEVER returned here
    (T-29-07).
    """
    warehouse_count = list_warehouses(session)["total"]
    backups = list_backups(backup_dir)
    last_backup_iso = backups[0]["created_iso"] if backups else None
    auto_enabled, auto_interval_seconds = read_autosync_config(session)
    return {
        "warehouse_count": warehouse_count,
        "last_backup_iso": last_backup_iso,
        "auto_enabled": auto_enabled,
        "auto_interval_seconds": auto_interval_seconds,
        "sync_server_url": settings.sync_server_url,
    }


def save_autosync_config(
    session: Session, *, enabled: bool, interval_seconds: int
) -> None:
    """Persist the D-15 auto-sync toggle + clamped interval to the sync_state row.

    Get-or-creates the single `sync_state` row (id=1), sets `auto_enabled` to
    1/0 and `auto_interval_seconds` to the value CLAMPED into
    `MIN_INTERVAL_SECONDS..MAX_INTERVAL_SECONDS` (D-15; an invalid/unparseable
    value falls back to the default), and commits. The loop picks up the change
    on its next tick (fresh read, D-08).
    """
    row = get_or_create_sync_state(session)
    row.auto_enabled = 1 if enabled else 0
    row.auto_interval_seconds = _clamp_interval(interval_seconds)
    session.commit()
