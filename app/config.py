"""Application settings (D-17): loaded from environment / optional .env file.

No secrets are hardcoded here — `secret_key` and the per-install `device_id`
are resolved from `.env` (which wins) or from local files persisted under the
DB directory (outside the synced DB, RESEARCH A2 / Pitfall 5 / Pitfall 6).
Never log or print `secret_key` / `device_id` (CLAUDE.md safety).
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.device_id import get_or_create_local_id


class Settings(BaseSettings):
    """Local app configuration; every field can be overridden via .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_path: str = "data/myorishop.db"
    # SRV-01/SRV-02 (Phase 26): the SINGLE DB-URL source of truth read by both
    # alembic/env.py and app/db.py. Empty default so an explicit DATABASE_URL in
    # .env/environment wins (field database_url ⇒ env var DATABASE_URL via
    # pydantic-settings); otherwise _resolve_local_identity fills the local
    # sqlite:///{db_path} default below. A PostgreSQL URL
    # (postgresql+psycopg://…) only ever arrives via env/.env — never hardcode a
    # host/user/password here.
    database_url: str = ""
    operator_name: str = "operator"
    # AUTH-03 (Pitfall 5): signing key for session cookies. Empty default so an
    # explicit SECRET_KEY in .env wins; otherwise a stable per-install key is
    # persisted below so a restart does not invalidate every session cookie.
    secret_key: str = ""
    # Sync pre-flight (A2 / Pitfall 6): the static "device-01" sentinel is
    # replaced by a persisted per-install UUID resolved below.
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

    @model_validator(mode="after")
    def _resolve_local_identity(self) -> "Settings":
        """Fill secret_key / device_id from persisted per-install files.

        The identity files live in the DB's directory (gitignored `data/`),
        NOT inside the synced DB, so copying `myorishop.db` cannot clone them.
        An env-provided value is left untouched; only the empty `secret_key`
        default and the static `"device-01"` sentinel are replaced.
        """
        data_dir = Path(self.db_path).parent
        # Single source of truth: only the empty default is filled; an explicit
        # DATABASE_URL (e.g. postgresql+psycopg://…) is left untouched.
        if not self.database_url:
            self.database_url = f"sqlite:///{self.db_path}"
        if not self.secret_key:
            self.secret_key = get_or_create_local_id(data_dir / "secret_key")
        if self.device_id == "device-01":
            self.device_id = get_or_create_local_id(data_dir / "device_id")
        return self


settings = Settings()
