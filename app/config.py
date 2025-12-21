"""Application configuration from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Application
    app_name: str = "Arduino Trader"
    debug: bool = False

    # Database
    database_path: Path = Path("data/trader.db")

    # Tradernet API
    tradernet_api_key: str = ""
    tradernet_api_secret: str = ""
    tradernet_base_url: str = "https://api.tradernet.com"

    # Scheduling
    monthly_rebalance_day: int = 1  # Day of month for rebalance
    daily_sync_hour: int = 18  # Hour for daily portfolio sync

    # LED Display
    led_serial_port: str = "/dev/ttyACM0"
    led_baud_rate: int = 115200

    # Investment
    monthly_deposit: float = 1000.0  # EUR

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
