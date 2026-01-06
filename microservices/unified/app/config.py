"""Configuration management for unified microservice."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Service configuration
    service_name: str = "unified-microservice"
    version: str = "1.0.0"
    host: str = "0.0.0.0"  # nosec B104 - Docker service needs to bind to all interfaces
    port: int = 9000

    # Logging
    log_level: str = "INFO"

    # Tradernet API credentials (optional, can be passed via headers)
    tradernet_api_key: str = ""
    tradernet_api_secret: str = ""


settings = Settings()
