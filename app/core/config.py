"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AAE typed configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="AAE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "testing", "production"] = Field(
        default="development",
        description="Execution environment",
    )
    debug: bool = Field(default=False, description="Debug mode")
    app_name: str = Field(default="AI Automation Engineer", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")

    # Server
    host: str = Field(default="127.0.0.1", description="Server bind host")
    port: int = Field(default=8000, description="Server bind port")

    # Security
    secret_key: SecretStr = Field(
        default=SecretStr("dev_insecure_secret_key_change_in_production_min_32_chars"),
        description="Internal signing key",
    )

    # Database
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://postgres:postgres@localhost:5432/aae_dev"),
        description="Database connection URL (PostgreSQL required for runtime)",
    )
    db_pool_size: int = Field(default=5, description="Database pool size")
    db_max_overflow: int = Field(default=10, description="Database max overflow")
    db_timeout_seconds: int = Field(default=5, description="Database connection timeout in seconds")

    # n8n Provider
    n8n_url: str = Field(default="http://localhost:5678", description="n8n instance base URL")
    n8n_api_key: SecretStr = Field(default=SecretStr(""), description="n8n API Key")
    n8n_timeout_seconds: float = Field(default=10.0, description="n8n HTTP client timeout")
    n8n_verify_ssl: bool = Field(default=True, description="Verify SSL certificates for n8n")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Log verbosity level",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "testing", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"Invalid environment: {v}. Must be one of {allowed}")
        return v.lower()

    def get_database_url_str(self) -> str:
        """Return the unmasked database URL for connection creation."""
        return self.database_url.get_secret_value()

    def get_n8n_api_key_str(self) -> str:
        """Return the unmasked n8n API key."""
        return self.n8n_api_key.get_secret_value()

    def safe_dict(self) -> dict:
        """Return configuration dictionary with all secrets masked."""
        data = self.model_dump()
        data["secret_key"] = "********" if self.secret_key.get_secret_value() else ""
        # Mask database password if present
        raw_db = self.database_url.get_secret_value()
        if "@" in raw_db and ":" in raw_db.split("@")[0]:
            parts = raw_db.split("@")
            user_pass = parts[0].split("://")[-1]
            if ":" in user_pass:
                user = user_pass.split(":")[0]
                masked_prefix = raw_db.split("://")[0] + f"://{user}:********@"
                data["database_url"] = masked_prefix + parts[1]
            else:
                data["database_url"] = "********"
        else:
            data["database_url"] = "********"
        data["n8n_api_key"] = "********" if self.n8n_api_key.get_secret_value() else ""
        return data

    def __repr__(self) -> str:
        return f"<Settings: env={self.environment}, version={self.app_version}>"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
