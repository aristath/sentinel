"""Application configuration from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Application
    app_name: str = "Arduino Trader"
    debug: bool = False

    # Database
    data_dir: Path = Path("data")
    database_path: Path = Path("data/trader.db")

    # Tradernet API
    tradernet_api_key: str = ""
    tradernet_api_secret: str = ""
    tradernet_base_url: str = "https://api.tradernet.com"

    # Scheduling
    daily_sync_hour: int = 18  # Hour for daily portfolio sync
    cash_check_interval_minutes: int = 15  # Check cash balance every 15 min

    # LED Display
    led_serial_port: str = "/dev/ttyACM0"
    led_baud_rate: int = 115200
    led_error_scroll_speed_ms: int = 30  # Scroll speed in milliseconds (lower = faster)

    # Investment / Rebalancing
    min_cash_threshold: float = 400.0  # EUR - minimum cash to trigger rebalance
    # Note: min_trade_size removed - now calculated from transaction costs in DB settings
    max_trades_per_cycle: int = 5  # Maximum trades per rebalance cycle
    min_stock_score: float = 0.5  # Minimum score to consider buying a stock

    # Price fetching / Retry configuration
    price_fetch_max_retries: int = 3  # Maximum retries for price fetching
    price_fetch_retry_delay_base: float = (
        1.0  # Base delay in seconds for exponential backoff
    )

    # Rate limiting
    rate_limit_max_requests: int = 60  # General API rate limit per window
    rate_limit_window_seconds: int = 60  # Rate limit window in seconds
    rate_limit_trade_max: int = 10  # Trade execution rate limit per window
    rate_limit_trade_window: int = 60  # Trade execution rate limit window in seconds

    # Job failure tracking
    job_failure_threshold: int = 5  # Consecutive failures before alerting
    job_failure_window_hours: int = 1  # Time window for failure tracking

    # Data retention
    daily_price_retention_days: int = 365  # Keep 1 year of daily prices
    snapshot_retention_days: int = 90  # Keep 90 days of portfolio snapshots
    backup_retention_count: int = 7  # Keep last 7 database backups

    # External API rate limiting
    external_api_rate_limit_delay: float = 0.33  # Delay between API calls (3 req/sec)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
