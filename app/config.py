"""Application settings (D-17): loaded from environment / optional .env file.

No secrets live here — only local paths and operator identity defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Local app configuration; every field can be overridden via .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_path: str = "data/myorishop.db"
    operator_name: str = "operator"
    device_id: str = "device-01"
    display_tz: str = "Europe/Moscow"
    # BCK-01 (D-08/D-09/D-10): startup + manual VACUUM INTO backups.
    # backup_on_startup exists as a flag so the TEST SUITE can disable the
    # lifespan backup (RESEARCH Pitfall 1) — env overrides BACKUP_ON_STARTUP.
    backup_dir: str = "backups"
    backup_on_startup: bool = True
    backup_keep: int = 30
    # RPT-02/RPT-04 (D-05): global fallback when a product's own threshold is NULL.
    low_stock_threshold: int = 5
    stale_days: int = 90
    # CAT-04: folder holding the published catalog PDFs (relative to CWD =
    # repo root when launched via run.bat). Served read-only by /catalogs.
    catalogs_dir: str = "catalogs"


settings = Settings()
