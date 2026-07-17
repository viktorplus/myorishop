"""Settings hub service (D-06): composes existing warehouse/backup summaries.

No new business logic — just reads the two existing services' data and
shapes it for the /settings hub page (thin-route rule, mirrors
app/routes/backup.py's pattern).
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.services.backup import list_backups
from app.services.warehouses import list_warehouses


def settings_summary(session: Session, backup_dir: Path) -> dict:
    """Warehouse count (active only) + last-backup timestamp, or None."""
    warehouse_count = list_warehouses(session)["total"]
    backups = list_backups(backup_dir)
    last_backup_iso = backups[0]["created_iso"] if backups else None
    return {
        "warehouse_count": warehouse_count,
        "last_backup_iso": last_backup_iso,
    }
