"""Application settings, loaded from environment variables.

Secrets (database URL, JWT key, seed passwords) are never hard-coded; they come
from the environment (see `.env.example`). Local, non-container runs may also use
a `.env` file.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Known-insecure default signing key shipped for local development only.
INSECURE_DEFAULT_JWT_KEY = "dev-only-insecure-signing-key-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    environment: str = "production"
    # API docs are opt-in and intended for development; off by default so a
    # production image does not publish its schema/attack surface (see ADR-014).
    swagger_enabled: bool = False

    # --- Database (async SQLAlchemy / asyncpg) ---
    # e.g. postgresql+asyncpg://user:pass@db:5432/teleradio
    database_url: str = "postgresql+asyncpg://teleradio:teleradio@localhost:5432/teleradio"

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    frontend_origins: str = "http://localhost:4200"

    # --- JWT / auth (consumed from the auth iteration onward) ---
    jwt_key: str = INSECURE_DEFAULT_JWT_KEY
    jwt_issuer: str = "teleradiokin"
    jwt_audience: str = "teleradiokin-clients"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Study storage & uploads ---
    storage_root_path: str = "/app/storage"
    # Max accepted study file size (bytes). Default 300 MiB.
    max_upload_bytes: int = 314_572_800
    # Max chunk size accepted in a single append (bytes). Default 8 MiB.
    max_chunk_bytes: int = 8_388_608

    # --- Seed account passwords (development convenience) ---
    seed_admin_password: str | None = None
    seed_radiologist_password: str | None = None
    seed_clinician_password: str | None = None

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


def validate_security(settings: "Settings") -> None:
    """Fail fast outside development when secrets are missing or insecure.

    Guards against the common disaster of deploying with the committed default
    JWT key (which would let anyone forge admin tokens). Development runs are
    left untouched so the local stack stays single-command.
    """
    if settings.is_development:
        return
    problems: list[str] = []
    if settings.jwt_key == INSECURE_DEFAULT_JWT_KEY:
        problems.append("JWT_KEY is still the insecure development default")
    if len(settings.jwt_key) < 32:
        problems.append("JWT_KEY must be at least 32 characters")
    if problems:
        raise RuntimeError(
            "Insecure configuration for environment="
            f"{settings.environment!r}: " + "; ".join(problems)
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (used as a FastAPI dependency and at startup)."""
    return Settings()
