#!/usr/bin/env python3
"""Native LED Display Script for Arduino Uno Q.

Polls the FastAPI application for display text and sends it to the MCU via serial port.
Runs as a systemd service, replacing the Docker-based Arduino App framework implementation.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

import requests
import serial
from serial import SerialException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Configure logging
log_dir = settings.data_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(log_dir / "led-display.log")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler],
)

logger = logging.getLogger(__name__)

# Configuration
API_URL = "http://localhost:8000"
SERIAL_PORT = settings.led_serial_port
BAUD_RATE = settings.led_baud_rate
POLL_INTERVAL = 2.0  # Poll every 2 seconds
SERIAL_RETRY_DELAY = 5.0  # Retry serial connection after 5 seconds
API_RETRY_DELAY = 5.0  # Retry API connection after 5 seconds

_session = requests.Session()
_serial_conn: Optional[serial.Serial] = None
_last_text = ""
_last_speed = 0
_last_brightness = 0


def connect_serial() -> bool:
    """Connect to serial port. Returns True if successful."""
    global _serial_conn
    try:
        if _serial_conn and _serial_conn.is_open:
            return True

        logger.info(f"Connecting to serial port {SERIAL_PORT} at {BAUD_RATE} baud...")
        _serial_conn = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for serial connection to stabilize
        logger.info("Serial connection established")
        return True
    except SerialException as e:
        logger.error(f"Failed to connect to serial port: {e}")
        _serial_conn = None
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to serial: {e}")
        _serial_conn = None
        return False


def send_command(command: str) -> bool:
    """Send a command to the MCU via serial. Returns True if successful."""
    global _serial_conn

    if not _serial_conn or not _serial_conn.is_open:
        if not connect_serial():
            return False

    try:
        _serial_conn.write(f"{command}\n".encode("utf-8"))
        _serial_conn.flush()
        return True
    except SerialException as e:
        logger.warning(f"Serial write failed: {e}, will retry connection")
        _serial_conn = None
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing to serial: {e}")
        return False


def set_text(text: str) -> bool:
    """Send text to MCU for scrolling."""
    if not text:
        return True  # Empty text is valid
    return send_command(f"TEXT:{text}")


def set_speed(speed: int) -> bool:
    """Set scroll speed on MCU."""
    return send_command(f"SPEED:{speed}")


def set_brightness(brightness: int) -> bool:
    """Set LED brightness on MCU."""
    return send_command(f"BRIGHTNESS:{brightness}")


def fetch_display_data() -> Optional[dict]:
    """Fetch display text and settings from API. Returns None on error."""
    try:
        response = _session.get(f"{API_URL}/api/status/display/text", timeout=2)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"API returned status {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        logger.warning("API connection failed, will retry")
        return None
    except requests.exceptions.Timeout:
        logger.warning("API request timed out")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching display data: {e}")
        return None


def main_loop():
    """Main loop - fetch display text from API, update MCU if changed."""
    global _last_text, _last_speed, _last_brightness

    logger.info("Starting LED display native script")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Serial port: {SERIAL_PORT}")

    # Initial serial connection
    if not connect_serial():
        logger.error("Failed to establish initial serial connection")
        logger.info("Will retry in main loop...")

    consecutive_errors = 0
    max_consecutive_errors = 10

    while True:
        try:
            # Fetch data from API
            data = fetch_display_data()

            if data is None:
                # API unavailable - show error on display
                if _last_text != "API OFFLINE":
                    set_text("API OFFLINE")
                    _last_text = "API OFFLINE"
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive API errors, exiting")
                    sys.exit(1)
                time.sleep(API_RETRY_DELAY)
                continue

            # Reset error counter on success
            consecutive_errors = 0

            text = data.get("text", "")
            speed = data.get("speed", 50)
            brightness = data.get("brightness", 150)

            # Update settings if changed
            if speed != _last_speed:
                if set_speed(speed):
                    _last_speed = speed
                    logger.debug(f"Speed updated to {speed}")

            if brightness != _last_brightness:
                if set_brightness(brightness):
                    _last_brightness = brightness
                    logger.debug(f"Brightness updated to {brightness}")

            # Update text if changed
            if text != _last_text:
                if set_text(text):
                    _last_text = text
                    logger.debug(f"Text updated: {text[:50]}...")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL)

    # Cleanup
    if _serial_conn and _serial_conn.is_open:
        logger.info("Closing serial connection...")
        _serial_conn.close()


if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
