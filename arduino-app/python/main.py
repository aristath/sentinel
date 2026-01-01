# Arduino Trader LED Display
# System stats visualization with random pixel density and microservice health

from arduino.app_utils import App, Bridge, Logger
import time
import requests
import subprocess

logger = Logger("trader-display")

API_URL = "http://192.168.1.11:8000"

# Persistent HTTP session for connection pooling (reuses TCP connections)
_http_session = requests.Session()


def set_fill_percentage(percentage: float) -> bool:
    """Set LED matrix fill percentage for system stats visualization.

    Args:
        percentage: Fill percentage (0.0-100.0)

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setFillPercentage", percentage, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setFillPercentage failed: {e}")
        return False


def set_rgb3(r: int, g: int, b: int) -> bool:
    """Set RGB LED 3 color (microservice health indicator).

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
    """Set RGB LED 4 color (microservice health indicator).

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


def fetch_display_state() -> dict | None:
    """Fetch display state from FastAPI backend.

    Uses persistent session for HTTP connection pooling (keep-alive).
    """
    try:
        with _http_session.get(f"{API_URL}/api/status/led/display", timeout=2) as resp:
            if resp.status_code == 200:
                state = resp.json()
                logger.debug(f"Fetched display state: fill={state.get('fill_percentage', 0.0):.1f}%, led3={state.get('led3')}, led4={state.get('led4')}")
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

    Polls every 1 second. Always sends commands to Bridge (stateless).
    Arduino queue handles deduplication with latest-wins strategy.
    """
    try:
        state = fetch_display_state()

        if state is None:
            # API unreachable
            if not check_bridge_health():
                restart_bridge_if_needed()
            time.sleep(1)
            return

        # Update RGB LEDs (always send, let Arduino handle it)
        led3 = state.get("led3", [0, 0, 0])
        led4 = state.get("led4", [0, 0, 0])
        set_rgb3(led3[0], led3[1], led3[2])
        set_rgb4(led4[0], led4[1], led4[2])

        # Update fill percentage for LED matrix (always send, Arduino queues with latest-wins)
        fill_percentage = state.get("fill_percentage", 0.0)
        success = set_fill_percentage(fill_percentage)
        if not success:
            logger.warning(f"Failed to send fill percentage to Arduino: {fill_percentage:.1f}%")

        time.sleep(1)  # Poll every 1 second

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(1)


logger.info("LED Display starting (system stats visualization mode)...")
App.run(user_loop=loop)
