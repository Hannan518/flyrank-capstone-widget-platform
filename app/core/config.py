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

    @model_validator(mode="after")
    def _enforce_invariants(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
