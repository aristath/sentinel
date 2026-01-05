"""Configuration management for Tradernet service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration."""

    service_name: str = "tradernet-service"
    version: str = "1.0.0"
    host: str = "0.0.0.0"  # nosec B104 - Docker service needs to bind to all interfaces
    port: int = 9001
    log_level: str = "INFO"

    # Tradernet API credentials
    tradernet_api_key: str = ""
    tradernet_api_secret: str = ""

    # Service limits
    max_batch_symbols: int = 100
    default_trade_history_limit: int = 500
    default_cash_flow_limit: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
