"""Application settings, loaded from environment variables.

Every setting has a matching environment variable with the same name in UPPER
CASE (for example ``session_ttl_hours`` reads ``SESSION_TTL_HOURS``). In local
development, Docker Compose passes the values from the repo-root ``.env`` file.

Use it anywhere with::

    from app.core.config import get_settings

    settings = get_settings()
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default for local development only. Production must set APP_SECRET_KEY.
DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Also read a local .env file when running outside Docker.
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    environment: Literal["development", "test", "production"] = "development"

    # --- Database ----------------------------------------------------------
    postgres_user: str = "coursemgmt"
    postgres_password: SecretStr = SecretStr("coursemgmt")
    postgres_db: str = "coursemgmt"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # --- Superuser bootstrap -------------------------------------------------
    # On startup the API makes sure this account exists (see app/core/bootstrap.py).
    superuser_email: str = "admin@example.com"
    superuser_password: SecretStr = SecretStr("change-me-please")

    # --- Sessions / cookies --------------------------------------------------
    session_cookie_name: str = "session"
    session_ttl_hours: int = 24 * 7
    # Set to true when the site is served over HTTPS so browsers only send the
    # cookie over encrypted connections.
    session_cookie_secure: bool = False

    # --- Invitations ---------------------------------------------------------
    # How long a one-time invite link stays valid, in hours (default: 7 days).
    invite_ttl_hours: int = 24 * 7

    # --- Encryption ----------------------------------------------------------
    # Used to encrypt stored API keys and tokens (see app/core/crypto.py).
    # Use a long random value in production and keep it secret. If it changes,
    # previously saved API keys can no longer be read and must be re-entered.
    app_secret_key: SecretStr = SecretStr(DEV_SECRET_KEY)

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL built from the individual POSTGRES_* settings."""
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the settings object. Cached, so the environment is read only once."""
    return Settings()
