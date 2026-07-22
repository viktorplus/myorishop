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
    # T-28-27 (Plan 06, ASVS V3): the session cookie must carry `Secure` on an
    # internet-facing HTTPS deployment so it is never sent over plain HTTP. The
    # default MUST stay False — a `Secure` cookie is not transmitted over http,
    # so flipping this on would break every local run.bat client and the entire
    # test suite (both plain HTTP). It is set true ONLY in the server's
    # /etc/myorishop.env (env var SESSION_HTTPS_ONLY=true). Never hardcode True.
    session_https_only: bool = False
    # Sync pre-flight (A2 / Pitfall 6): the static "device-01" sentinel is
    # replaced by a persisted per-install UUID resolved below.
    device_id: str = "device-01"
    # Phase 29 (SYNC-06/SRV-03): outbound online-sync client config, resolved
    # from `.env` ONLY. `sync_server_url` is the central server base URL
    # (e.g. https://sync.example.com); `sync_token` is the per-device Bearer
    # secret the driver authenticates with. `sync_token` is a SECRET — like
    # `secret_key` it lives in `.env`, is NEVER a `sync_state`/DB column (a
    # copied myorishop.db must not carry the device credential), and is NEVER
    # logged/printed (CLAUDE.md safety).
    #
    # `sync_server_url` defaults to the known central server so the local
    # distribution knows where to sync out of the box; the operator only needs to
    # enter the per-device `sync_token` (which stays "" here — a secret, never
    # defaulted). The CENTRAL SERVER itself must NOT be a sync client, so its
    # deployment sets SYNC_SERVER_URL="" in the environment (env wins over this
    # default) to stay unconfigured — mirrors SESSION_HTTPS_ONLY being server-only.
    # The auto-sync toggle/interval are NOT here — they must be runtime-mutable
    # (D-15) and live in the `sync_state` table, not static `.env`.
    sync_server_url: str = "https://ori.viktorplus.com"
    sync_token: str = ""
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
