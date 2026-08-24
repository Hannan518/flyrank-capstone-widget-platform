from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    database_url: str

    jwt_secret: str
    jwt_ttl_hours: int = 24

    public_base_url: str = "http://localhost:8000"
    cors_origins: list[str] = []

    submission_max_body_bytes: int = 65_536

    rate_limit_ip_max: int = 5
    rate_limit_ip_window_seconds: int = 60
    rate_limit_widget_max: int = 100
    rate_limit_widget_window_seconds: int = 60
    rate_limit_retention_seconds: int = 7_200

    geo_provider_mode: str = "live"
    geo_total_budget_ms: int = 2_000
    dev_public_ip: str = "8.8.8.8"

    email_mode: str = "console"
    jobs_poll_interval_seconds: float = 2.0
    job_retention_days: int = 7

    @model_validator(mode="after")
    def _enforce_invariants(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if self.geo_provider_mode not in ("live", "mock"):
            raise ValueError("GEO_PROVIDER_MODE must be 'live' or 'mock'")
        if self.email_mode not in ("console", "smtp"):
            raise ValueError("EMAIL_MODE must be 'console' or 'smtp'")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
