#!/usr/bin/env python3
"""Native LED Display Script for Arduino Uno Q.

Connects to FastAPI SSE endpoint for real-time display updates and sends them to the MCU via Router Bridge.
Runs as a systemd service, using native arduino-router service (no Docker required).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings  # noqa: E402

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
SSE_ENDPOINT = f"{API_URL}/api/status/led/display/stream"
DEFAULT_TICKER_SPEED = 50  # ms per scroll step

# Try to import Router Bridge client
try:
    # Import from scripts directory
    import importlib.util

    router_bridge_path = Path(__file__).parent / "router_bridge_client.py"
    spec = importlib.util.spec_from_file_location("router_bridge_client", router_bridge_path)
    if spec and spec.loader:
        router_bridge_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(router_bridge_module)
        bridge_call = router_bridge_module.call
        ROUTER_BRIDGE_AVAILABLE = True
    else:
        raise ImportError("Failed to load router_bridge_client module")
except ImportError as e:
    logger.warning(f"Router Bridge client not available: {e}")
    ROUTER_BRIDGE_AVAILABLE = False
    bridge_call = None
except Exception as e:
    logger.error(f"Failed to initialize Router Bridge client: {e}")
    ROUTER_BRIDGE_AVAILABLE = False
    bridge_call = None

_session = requests.Session()
_last_text = ""
_last_text_speed = 0
_last_led3 = None
_last_led4 = None


def set_text(text: str, speed: int = DEFAULT_TICKER_SPEED) -> bool:
    """Send text to MCU for scrolling via Router Bridge.

    Args:
        text: Text to scroll (ASCII only, Euro symbol will be replaced)
        speed: Milliseconds per scroll step (lower = faster)

    Returns:
        True if successful, False otherwise
    """
    if not ROUTER_BRIDGE_AVAILABLE:
        logger.error("Router Bridge client not available")
        return False

    if not text:
        return True  # Empty text is valid

    try:
        # Replace Euro symbol with EUR (Font_5x7 only has ASCII 32-126)
        text = text.replace("€", "EUR")
        bridge_call("scrollText", text, speed, timeout=30)
        return True
    except Exception as e:
        logger.error(f"Failed to set text via Router Bridge: {e}")
        return False


def set_rgb3(r: int, g: int, b: int) -> bool:
    """Set RGB LED 3 color via Router Bridge.

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    if not ROUTER_BRIDGE_AVAILABLE:
        return False

    try:
        bridge_call("setRGB3", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"Failed to set RGB3 via Router Bridge: {e}")
        return False


def set_rgb4(r: int, g: int, b: int) -> bool:
    """Set RGB LED 4 color via Router Bridge.

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    if not ROUTER_BRIDGE_AVAILABLE:
        return False

    try:
        bridge_call("setRGB4", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"Failed to set RGB4 via Router Bridge: {e}")
        return False


def parse_sse_event(line: str) -> Optional[dict]:
    """Parse SSE event line (data: {json}).

    Args:
        line: SSE event line starting with "data:"

    Returns:
        Parsed JSON data, or None if invalid
    """
    if not line.startswith("data:"):
        return None

    try:
        json_str = line[5:].strip()  # Remove "data:" prefix
        if not json_str:
            return None

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse SSE event: {e}")
        return None


def _process_display_data(data: dict) -> None:
    """Process display data and update MCU if changed."""
    global _last_text, _last_text_speed, _last_led3, _last_led4

    # Get ticker text from display state
    ticker_text = data.get("ticker_text", "")
    ticker_speed = data.get("ticker_speed", DEFAULT_TICKER_SPEED)

    # Handle different display modes
    mode = data.get("mode", "normal")
    error_message = data.get("error_message")
    activity_message = data.get("activity_message")
    led3 = data.get("led3", [0, 0, 0])
    led4 = data.get("led4", [0, 0, 0])

    # Update RGB LEDs (only if changed - optimization)
    led3_tuple = tuple(led3)
    if _last_led3 != led3_tuple and ROUTER_BRIDGE_AVAILABLE:
        set_rgb3(led3[0], led3[1], led3[2])
        _last_led3 = led3_tuple

    led4_tuple = tuple(led4)
    if _last_led4 != led4_tuple and ROUTER_BRIDGE_AVAILABLE:
        set_rgb4(led4[0], led4[1], led4[2])
        _last_led4 = led4_tuple

    # Determine what text to display (priority: error > activity > ticker)
    if mode == "error" and error_message:
        display_text = error_message
    elif activity_message:
        display_text = activity_message
    elif ticker_text:
        display_text = ticker_text
    else:
        display_text = ""

    # Update text only if changed (optimization)
    if display_text != _last_text or ticker_speed != _last_text_speed:
        logger.info(f"Updating display text: {display_text[:50]}...")
        if set_text(display_text, speed=ticker_speed):
            _last_text = display_text
            _last_text_speed = ticker_speed
        else:
            logger.error("Failed to update display text")


def main_loop():
    """Main loop - connect to SSE stream, receive events, update MCU via Router Bridge."""
    global _last_text

    logger.info("Starting LED display native script (SSE mode)")
    logger.info(f"SSE endpoint: {SSE_ENDPOINT}")

    if not ROUTER_BRIDGE_AVAILABLE:
        logger.error("Router Bridge client not available. Exiting.")
        logger.error("Make sure msgpack is installed: pip install msgpack")
        logger.error("Make sure arduino-router service is running: sudo systemctl status arduino-router")
        sys.exit(1)

    # Test Router Bridge connection
    try:
        bridge_call("scrollText", "READY", 50, timeout=2)
        logger.info("Router Bridge connection test successful")
    except Exception as e:
        logger.error(f"Router Bridge connection test failed: {e}")
        logger.error("Make sure arduino-router service is running: sudo systemctl status arduino-router")
        logger.error("Make sure the MCU sketch is uploaded with Router Bridge functions")
        sys.exit(1)

    # Initialize LEDs to OFF
    if ROUTER_BRIDGE_AVAILABLE:
        set_rgb3(0, 0, 0)
        set_rgb4(0, 0, 0)
        _last_led3 = (0, 0, 0)
        _last_led4 = (0, 0, 0)
        logger.info("Initialized RGB LEDs to OFF")

    # Connect to SSE stream
    try:
        logger.info(f"Connecting to SSE endpoint: {SSE_ENDPOINT}")
        # Use tuple timeout: (connect_timeout, read_timeout)
        # Read timeout of 30s allows for heartbeats every 5s with margin
        response = _session.get(SSE_ENDPOINT, stream=True, timeout=(10, 30))

        if response.status_code != 200:
            logger.error(f"SSE endpoint returned status {response.status_code}")
            sys.exit(1)

        logger.info("SSE connection established")

        # Process SSE stream using iter_lines for better SSE handling
        buffer = ""
        for line in response.iter_lines(decode_unicode=True):
            if line is None:
                continue

            # SSE events are separated by empty lines
            if line == "":
                # End of event block, process accumulated buffer
                if buffer:
                    data = parse_sse_event(buffer)
                    if data is not None:
                        _process_display_data(data)
                    buffer = ""
            else:
                # Accumulate lines (in case of multi-line events)
                if buffer:
                    buffer += "\n" + line
                else:
                    buffer = line

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to SSE endpoint: {e}")
        logger.error("Make sure the FastAPI server is running")
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        logger.error(f"SSE connection timed out: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
