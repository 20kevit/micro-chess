"""Application configuration. Env-driven with safe production defaults.

Secrets come only from the environment (never committed, never bundled
into the frontend). In production the app refuses to start with the
development JWT secret — see Settings.ensure_ready(), called from the
app lifespan.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MicroChess"
    environment: str = "development"
    database_url: str = "sqlite:///./microchess.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    # Abuse protection hooks (see app.core.rate_limit). Limits are
    # centralized here, never hard-coded in route handlers.
    rate_limit_enabled: bool = True
    auth_rate_limit_per_minute: int = 30
    # Phase 11 support abuse protection (spam ticket/message creation).
    support_rate_limit_per_minute: int = 20
    # Free/Premium verification + coupon abuse protection.
    verification_telegram_enabled: bool = False
    verification_rate_limit_per_minute: int = 20
    billing_rate_limit_per_minute: int = 30
    webhook_rate_limit_per_minute: int = 120
    # Server-side session lifetimes (single place; never scattered).
    guest_session_expire_days: int = 30

    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    def ensure_ready(self) -> None:
        """Fail fast on unsafe production configuration."""
        if self.is_production() and self.jwt_secret == "change-me-in-production":
            raise RuntimeError("JWT_SECRET must be set to a unique value in production")


settings = Settings()
