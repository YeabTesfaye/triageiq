"""
Application configuration using pydantic-settings.
All values come from environment variables or .env file.
No hardcoded secrets anywhere in the codebase.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv

load_dotenv()  # Load .env file at startup, if it exists


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "TriageIQ"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Server ─────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins — no wildcard in production.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://triageiq:triageiq@localhost:5432/triageiq"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False  # set True only in dev; never in prod

    # ── Redis ──────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    # Prefix for all Redis keys to avoid collisions with other apps
    REDIS_KEY_PREFIX: str = "triageiq:"

    # ── JWT ────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_MINIMUM_32_CHARS"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Security ───────────────────────────────────────────────────────────────
    BCRYPT_ROUNDS: int = 12
    # Max failed logins before account lock
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    # Minutes to lock account after too many failures
    ACCOUNT_LOCK_MINUTES: int = 15

    # ── Rate Limiting ──────────────────────────────────────────────────────────
    # Global rate limit per IP
    RATE_LIMIT_PER_MINUTE: int = 100
    # Stricter limit for auth endpoints
    AUTH_RATE_LIMIT_PER_15_MIN: int = 20

    # ── OpenAI ─────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: int = 15
    OPENAI_MAX_RETRIES: int = 2

    # ── Observability ──────────────────────────────────────────────────────────
    ENABLE_METRICS: bool = True

    # ── Firebase ───────────────────────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = "firebase_service_account.json"
    FIREBASE_DATABASE_URL: str

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENV must be one of {allowed}")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere."""
    return Settings()
