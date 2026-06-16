from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IDNOW_",
        case_sensitive=False,
        extra="ignore",
    )

    # OAuth2 ROPC credentials
    username: str = Field(...)
    password: str = Field(...)
    oauth_client_id: str = Field(...)

    # Realm & environment
    realm: str = Field(default="ariadnext-idcheck-sandbox")
    env: Literal["sandbox", "production"] = Field(default="sandbox")

    # Timeouts
    poll_timeout_seconds: int = Field(default=120, ge=10, le=600)
    poll_interval_seconds: int = Field(default=5, ge=1, le=30)
    request_timeout_seconds: int = Field(default=30)

    # Logging
    log_level: str = Field(default="INFO")

    @computed_field
    @property
    def base_url(self) -> str:
        return {
            "sandbox":    "https://api.idcheck-sandbox.ariadnext.io/gw/cis",
            "production": "https://api.idcheck.ariadnext.io/gw/cis",
        }[self.env]

    @computed_field
    @property
    def token_url(self) -> str:
        return {
            "sandbox": (
                "https://sso.idcheck-sandbox.ariadnext.io"
                "/auth/realms/customer-identity"
                "/protocol/openid-connect/token"
            ),
            "production": (
                "https://sso.idcheck.ariadnext.io"
                "/auth/realms/customer-identity"
                "/protocol/openid-connect/token"
            ),
        }[self.env]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
