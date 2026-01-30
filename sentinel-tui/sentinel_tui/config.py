"""Configuration for sentinel-tui."""

import argparse
import os

DEFAULT_API_URL = "http://localhost:8000"


def get_api_url() -> str:
    """Return API URL from CLI arg > env var > default."""
    parser = argparse.ArgumentParser(description="Sentinel TUI")
    parser.add_argument("--api-url", type=str, default=None, help="Sentinel API URL")
    args = parser.parse_args()

    if args.api_url:
        return args.api_url.rstrip("/")

    env_url = os.environ.get("SENTINEL_API_URL")
    if env_url:
        return env_url.rstrip("/")

    return DEFAULT_API_URL
