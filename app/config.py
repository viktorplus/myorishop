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


settings = Settings()
