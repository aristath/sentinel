# Arduino Trader LED Display
# Simple scrolling text display for 8x13 LED matrix and RGB LEDs 3 & 4

from arduino.app_utils import App, Bridge, Logger
import time
import requests
import subprocess

logger = Logger("trader-display")

API_URL = "http://192.168.1.11:8000"

# Persistent HTTP session for connection pooling (reuses TCP connections)
_http_session = requests.Session()

# Default ticker speed in ms (can be overridden by API)
DEFAULT_TICKER_SPEED = 50


def scroll_text(text: str, speed: int = 50) -> bool:
    """Scroll text across LED matrix using native ArduinoGraphics.

    Args:
        text: Text to scroll (uses Euro symbol € directly)
        speed: Milliseconds per scroll step (lower = faster)

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("scrollText", text, speed, timeout=5)
        return True
    except Exception as e:
        logger.debug(f"scrollText failed: {e}")
        return False


def set_rgb3(r: int, g: int, b: int) -> bool:
    """Set RGB LED 3 color (sync indicator).

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setRGB3", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setRGB3 failed: {e}")
        return False


def set_rgb4(r: int, g: int, b: int) -> bool:
    """Set RGB LED 4 color (processing indicator).

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setRGB4", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setRGB4 failed: {e}")
        return False


def handle_stats_mode(stats: dict) -> bool:
    """Handle system stats visualization mode.

    Args:
        stats: Dict with cpu_percent, ram_percent, pixels_on, brightness

    Returns:
        True if successful, False otherwise
    """
    pixels_on = stats.get("pixels_on", 0)
    brightness = stats.get("brightness", 100)
    cpu_percent = stats.get("cpu_percent", 0)
    ram_percent = stats.get("ram_percent", 0)

    # Calculate animation interval: 2000ms - (load% × 19.9)
    load_percent = (cpu_percent + ram_percent) / 2
    interval_ms = max(10, int(2000 - (load_percent * 19.9)))

    try:
        Bridge.call("setSystemStats", pixels_on, brightness, interval_ms, timeout=2)
        logger.debug(f"Stats mode: {pixels_on} pixels, brightness {brightness}, {interval_ms}ms interval")
        return True
    except Exception as e:
        logger.debug(f"setSystemStats failed: {e}")
        return False


def fetch_display_state() -> dict | None:
    """Fetch display state from FastAPI backend.

    Uses persistent session for HTTP connection pooling (keep-alive).
    """
    try:
        with _http_session.get(f"{API_URL}/api/status/led/display", timeout=2) as resp:
            if resp.status_code == 200:
                state = resp.json()
                logger.debug(f"Fetched display state: text='{state.get('display_text', '')}', led3={state.get('led3')}, led4={state.get('led4')}")
                return state
            else:
                logger.warning(f"API returned status {resp.status_code}")
    except Exception as e:
        logger.debug(f"API fetch failed: {e}")
    return None


def check_bridge_health() -> bool:
    """Check if Bridge is responsive."""
    try:
        # Try a simple call with short timeout
        Bridge.call("setRGB3", 0, 0, 0, timeout=1)
        return True
    except Exception:
        return False


def restart_bridge_if_needed() -> bool:
    """Restart Bridge if it's stuck.

    Tries to restart the Docker container via Arduino App Framework.
    """
    try:
        # Try to restart the Docker container
        # Arduino App Framework manages the container, so we try docker restart
        result = subprocess.run(
            ["docker", "restart", "trader-display"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("Restarted trader-display container")
            return True
    except FileNotFoundError:
        # Docker command not available - log and continue
        logger.debug("Docker command not found, cannot restart container")
    except Exception as e:
        logger.debug(f"Failed to restart bridge: {e}")
    return False


def loop():
    """Main loop - fetch display state from API, update MCU.

    Polls every 2 seconds (0.5Hz). Handles two modes:
    - STATS: System stats visualization (default)
    - TICKER: Scrolling text when ticker data exists
    """
    try:
        state = fetch_display_state()

        if state is None:
            # API unreachable
            if not check_bridge_health():
                restart_bridge_if_needed()
            time.sleep(2)  # Changed to 2s (0.5Hz)
            return

        # Update RGB LEDs (always send, let Arduino handle it)
        led3 = state.get("led3", [0, 0, 0])
        led4 = state.get("led4", [0, 0, 0])
        set_rgb3(led3[0], led3[1], led3[2])
        set_rgb4(led4[0], led4[1], led4[2])

        # Handle display mode
        mode = state.get("mode", "TICKER")

        if mode == "STATS":
            # System stats mode (default when no ticker data)
            stats = state.get("stats")
            if stats:
                success = handle_stats_mode(stats)
                if not success:
                    logger.warning("Failed to send stats to Arduino")
            else:
                logger.debug("Stats mode but no stats data")

        elif mode == "TICKER":
            # Ticker mode (when ticker data exists)
            display_text = state.get("display_text", "")
            if display_text:
                ticker_speed = state.get("ticker_speed", DEFAULT_TICKER_SPEED)
                success = scroll_text(display_text, ticker_speed)
                if not success:
                    logger.warning(f"Failed to send ticker to Arduino: '{display_text}'")
            else:
                logger.debug("Ticker mode but no display text")

        # Poll at 0.5Hz (every 2 seconds)
        time.sleep(2)

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(2)


logger.info("LED Display starting (system stats + ticker mode)...")
App.run(user_loop=loop)
