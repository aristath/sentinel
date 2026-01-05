"""Configuration settings for Yahoo Finance microservice."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    service_name: str = "Yahoo Finance Microservice"
    version: str = "1.0.0"
    log_level: str = "INFO"
    port: int = 9003

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()

