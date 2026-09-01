"""Configuration. The only module in VoltDesk that reads the environment.

Owned by: Phase 1. Fully implemented.

Settings are loaded once and cached. Nothing here performs I/O beyond reading the
environment and an optional .env file, and nothing here makes a network call - the
package must import cleanly on a machine with no database, no Redis and no API keys.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every knob VoltDesk has. Documented in .env.example."""

    model_config = SettingsConfigDict(
        env_prefix="VOLTDESK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default="local", description="local | staging | production.")
    log_level: str = Field(default="INFO")

    # These defaults deliberately do not resolve. A default of localhost:5432 would
    # connect to whatever PostgreSQL the developer already runs, and applying
    # VoltDesk's migrations there would create its schemas inside somebody else's
    # database - silently, because the connection would succeed. Failing to resolve a
    # hostname is a loud, harmless error; writing into the wrong database is neither.
    #
    # Compose supplies the real values to the api and worker services. For host-side
    # use, see docker-compose.hostports.yml.
    database_url: str = Field(
        default="postgresql+psycopg://voltdesk:voltdesk@voltdesk-db-not-configured:5432/voltdesk",
        description="Set explicitly. The default is an unresolvable placeholder.",
    )
    redis_url: str = Field(
        default="redis://voltdesk-redis-not-configured:6379/0",
        description="Set explicitly. The default is an unresolvable placeholder.",
    )

    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))

    espocrm_base_url: str = Field(default="http://localhost:8080")
    espocrm_api_key: SecretStr = Field(default=SecretStr(""))
    espocrm_timeout_seconds: float = Field(default=30.0, gt=0)

    auto_write_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    review_floor_confidence: float = Field(default=0.30, ge=0.0, le=1.0)
    abstention_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    redaction_enabled: bool = Field(default=True)

    llm_timeout_seconds: float = Field(default=120.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    circuit_breaker_failure_threshold: int = Field(
        default=5, ge=1, description="Consecutive failures before a provider is cut out."
    )
    circuit_breaker_reset_seconds: float = Field(default=60.0, gt=0)

    def has_anthropic(self) -> bool:
        """A provider with no key is treated as unavailable, not as an error."""
        return bool(self.anthropic_api_key.get_secret_value())

    def has_openai(self) -> bool:
        return bool(self.openai_api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Call `get_settings.cache_clear()` in tests that override env."""
    return Settings()
