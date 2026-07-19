"""Backup service (BCK-01, D-08/D-09/D-10): VACUUM INTO snapshots + retention.

D-08: every backup is a `VACUUM INTO` copy — WAL-safe, compact, standalone
(no -wal/-shm sidecars), safe to take while the app is running. VACUUM
cannot run inside a transaction, so create_backup opens its OWN connection
with isolation_level="AUTOCOMMIT" and passes the target path as a BOUND
parameter — never f-string interpolation (T-3-08: Windows backslashes break
SQL quoting). D-09: startup_backup holds ALL skip conditions (flag off /
DB file missing / DB empty) so app.main's lifespan stays a one-liner and
tests monkeypatch a single seam (PD-13). D-10: prune_backups runs only
AFTER a successful backup and keeps the newest settings.backup_keep files.
PD-11: same-second filenames get a "-2", "-3"... suffix; pruning and
listing order by file mtime so suffixed names sort correctly.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Operation, Product


def create_backup(engine: Engine, backup_dir: Path) -> Path:
    """VACUUM the live database into a timestamped standalone file (D-08).

    Raises on failure; a partially written target is deleted first
    (RESEARCH Pitfall 4: an interrupted VACUUM INTO leaves a corrupt file
    that would later masquerade as a valid backup).
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"myorishop-{stamp}.db"
    # PD-11: VACUUM INTO fails if the target exists — suffix within a second.
    counter = 2
    while target.exists():
        target = backup_dir / f"myorishop-{stamp}-{counter}.db"
        counter += 1
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("VACUUM INTO ?", (str(target),))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def prune_backups(backup_dir: Path, keep: int = 30) -> None:
    """Delete all but the newest `keep` backups, ordered by mtime (D-10)."""
    files = sorted(backup_dir.glob("myorishop-*.db"), key=lambda p: p.stat().st_mtime)
    doomed = files[:-keep] if keep > 0 else files
    for old in doomed:
        old.unlink()


def list_backups(backup_dir: Path) -> list[dict]:
    """Existing backups newest-first: name, created_iso (UTC), size label."""
    files = sorted(
        backup_dir.glob("myorishop-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    entries = []
    for file in files:
        stat = file.stat()
        entries.append(
            {
                "name": file.name,
                "created_iso": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(
                    timespec="seconds"
                ),
                "size_label": _size_label(stat.st_size),
            }
        )
    return entries


def _size_label(size: int) -> str:
    """Human-readable size, RU units: <1 MiB in КБ, otherwise «1,2 МБ»."""
    if size < 1024 * 1024:
        return f"{max(1, size // 1024)} КБ"
    megabytes = size / (1024 * 1024)
    return f"{megabytes:.1f}".replace(".", ",") + " МБ"


def startup_backup(engine: Engine | None = None) -> Path | None:
    """The D-09 gate: backup on app start unless disabled/missing/empty (PD-13)."""
    if not settings.backup_on_startup:
        return None
    if not Path(settings.db_path).exists():
        return None
    if engine is None:
        # Lazy import keeps the monkeypatch/test seam: tests pass their own
        # engine; production resolves the module-level app engine here.
        from app import db

        engine = db.engine
    # Dialect gate (OQ-6, Plan 06): create_backup issues `VACUUM INTO`, a
    # SQLite-only statement. Today a PostgreSQL deployment survives boot only
    # BY ACCIDENT — settings.db_path happens to name a file that does not exist
    # on the server, so the file-missing skip above fires first. If that file
    # ever exists (a stray copy, a shared volume, a developer's .env), the
    # accident evaporates and create_backup would run `VACUUM INTO` against the
    # PostgreSQL engine, raising inside lifespan and taking the whole server
    # down on boot. The dialect is the REAL condition; the missing file is an
    # accident. This guard makes the skip explicit and unconditional on Postgres.
    if engine.dialect.name != "sqlite":
        return None
    if not _db_has_data(engine):
        return None
    path = create_backup(engine, Path(settings.backup_dir))
    prune_backups(Path(settings.backup_dir), keep=settings.backup_keep)
    return path


def _db_has_data(engine: Engine) -> bool:
    """True when the DB holds any product or operation rows (D-09 skip guard).

    A schema-less or foreign file must not crash startup — any SQLAlchemy
    error counts as "no data" and skips the backup.
    """
    try:
        with Session(engine) as session:
            products = session.scalar(select(func.count()).select_from(Product))
            operations = session.scalar(select(func.count()).select_from(Operation))
    except SQLAlchemyError:
        return False
    return bool(products or operations)
