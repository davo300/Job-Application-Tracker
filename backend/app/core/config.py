from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://tracker:local-development-only@localhost:5432/tracker"
    session_ttl_hours: int = Field(default=24, ge=1, le=168)
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    auth_rate_limit: int = Field(default=20, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_origins(self):
        if not self.allowed_origins:
            raise ValueError("At least one explicit origin is required")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError("Origins must be explicit HTTP(S) origins without paths")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError("Production requires HTTPS origins")
        return self

    @property
    def session_cookie_name(self) -> str:
        return "__Host-tracker_session" if self.environment == "production" else "tracker_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-tracker_csrf" if self.environment == "production" else "tracker_csrf"


@lru_cache
def get_settings() -> Settings:
    return Settings()
