# Arduino Trader LED Display
# Simple scrolling text display for 8x13 LED matrix and RGB LEDs 3 & 4

from arduino.app_utils import App, Bridge, Logger
import time
import requests
import json

logger = Logger("trader-display")

API_URL = "http://localhost:8001"

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


def set_blink3(r: int, g: int, b: int, interval_ms: int) -> bool:
    """Set LED3 to blink mode.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
        interval_ms: Blink interval in milliseconds

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setBlink3", r, g, b, interval_ms, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setBlink3 failed: {e}")
        return False


def stop_blink3() -> bool:
    """Stop LED3 blinking.

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("stopBlink3", timeout=2)
        return True
    except Exception as e:
        logger.debug(f"stopBlink3 failed: {e}")
        return False


def set_blink4(r: int, g: int, b: int, interval_ms: int) -> bool:
    """Set LED4 to simple blink mode.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
        interval_ms: Blink interval in milliseconds

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setBlink4", r, g, b, interval_ms, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setBlink4 failed: {e}")
        return False


def set_blink4_alternating(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, interval_ms: int) -> bool:
    """Set LED4 to alternating color mode.

    Args:
        r1, g1, b1: First color RGB values (0-255)
        r2, g2, b2: Second color RGB values (0-255)
        interval_ms: Blink interval in milliseconds

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setBlink4Alternating", r1, g1, b1, r2, g2, b2, interval_ms, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setBlink4Alternating failed: {e}")
        return False


def set_blink4_coordinated(r: int, g: int, b: int, interval_ms: int, led3_phase: bool) -> bool:
    """Set LED4 to coordinated mode with LED3.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
        interval_ms: Blink interval in milliseconds
        led3_phase: LED3 phase state (True = LED3 is on)

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("setBlink4Coordinated", r, g, b, interval_ms, led3_phase, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setBlink4Coordinated failed: {e}")
        return False


def stop_blink4() -> bool:
    """Stop LED4 blinking.

    Returns:
        True if successful, False otherwise
    """
    try:
        Bridge.call("stopBlink4", timeout=2)
        return True
    except Exception as e:
        logger.debug(f"stopBlink4 failed: {e}")
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

    # Calculate animation interval: faster when load is high
    # 500ms at 0% load, 5ms at 100% load
    load_percent = (cpu_percent + ram_percent) / 2
    interval_ms = int(500 - (load_percent * 4.95))
    # Clamp to reasonable range
    interval_ms = max(5, min(500, interval_ms))

    try:
        Bridge.call("setSystemStats", pixels_on, brightness, interval_ms, timeout=2)
        logger.debug(f"Stats mode: {pixels_on} pixels, brightness {brightness}, {interval_ms}ms interval")
        return True
    except Exception as e:
        logger.debug(f"setSystemStats failed: {e}")
        return False


def handle_portfolio_mode(clusters: list) -> bool:
    """Handle portfolio visualization mode.

    Args:
        clusters: List of cluster dicts with cluster_id, pixels, brightness, clustering, speed, symbol

    Returns:
        True if successful, False otherwise
    """
    if not clusters:
        logger.debug("Portfolio mode but no clusters data")
        return False

    try:
        # Convert clusters to JSON string for Arduino
        clusters_json = json.dumps(clusters)
        Bridge.call("setPortfolioMode", clusters_json, timeout=2)
        logger.debug(f"Portfolio mode: {len(clusters)} clusters")
        return True
    except Exception as e:
        logger.debug(f"setPortfolioMode failed: {e}")
        return False


def handle_led3(state: dict) -> bool:
    """Handle LED3 state based on mode.

    Args:
        state: Display state dict with led3, led3_mode, led3_blink

    Returns:
        True if successful, False otherwise
    """
    led3_mode = state.get("led3_mode", "solid")
    led3 = state.get("led3", [0, 0, 0])
    led3_blink = state.get("led3_blink")

    if led3_mode == "blink" and led3_blink:
        color = led3_blink.get("color", led3)
        interval_ms = led3_blink.get("interval_ms", 500)
        return set_blink3(color[0], color[1], color[2], interval_ms)
    else:
        # Solid color
        return set_rgb3(led3[0], led3[1], led3[2])


def handle_led4(state: dict) -> bool:
    """Handle LED4 state based on mode.

    Args:
        state: Display state dict with led4, led4_mode, led4_blink

    Returns:
        True if successful, False otherwise
    """
    led4_mode = state.get("led4_mode", "solid")
    led4 = state.get("led4", [0, 0, 0])
    led4_blink = state.get("led4_blink")

    if led4_mode == "blink" and led4_blink:
        color = led4_blink.get("color", led4)
        interval_ms = led4_blink.get("interval_ms", 500)
        return set_blink4(color[0], color[1], color[2], interval_ms)
    elif led4_mode == "alternating" and led4_blink:
        alt_color1 = led4_blink.get("alt_color1", [255, 0, 0])
        alt_color2 = led4_blink.get("alt_color2", [0, 255, 0])
        interval_ms = led4_blink.get("interval_ms", 500)
        return set_blink4_alternating(
            alt_color1[0], alt_color1[1], alt_color1[2],
            alt_color2[0], alt_color2[1], alt_color2[2],
            interval_ms
        )
    elif led4_mode == "coordinated" and led4_blink:
        color = led4_blink.get("color", led4)
        interval_ms = led4_blink.get("interval_ms", 500)
        # Get LED3 phase from led3_blink if available
        led3_blink = state.get("led3_blink")
        led3_phase = led3_blink.get("is_on", False) if led3_blink else False
        return set_blink4_coordinated(color[0], color[1], color[2], interval_ms, led3_phase)
    else:
        # Solid color
        return set_rgb4(led4[0], led4[1], led4[2])


def fetch_display_state() -> dict | None:
    """Fetch display state from API.

    Uses persistent session for HTTP connection pooling (keep-alive).
    """
    try:
        with _http_session.get(f"{API_URL}/api/system/led/display", timeout=2) as resp:
            if resp.status_code == 200:
                state = resp.json()
                logger.debug(f"Fetched display state: mode={state.get('mode')}, led3={state.get('led3')}, led4={state.get('led4')}")
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


def loop():
    """Main loop - fetch display state from API, update MCU.

    Polls every 2 seconds (0.5Hz). Handles three modes:
    - STATS: System stats visualization (default)
    - TICKER: Scrolling text when ticker data exists
    - PORTFOLIO: Portfolio visualization mode
    """
    try:
        state = fetch_display_state()

        if state is None:
            # API unreachable
            if not check_bridge_health():
                logger.warning("Bridge not responsive and API unreachable")
            time.sleep(2)
            return

        # Update RGB LEDs based on mode
        handle_led3(state)
        handle_led4(state)

        # Handle display mode
        mode = state.get("mode", "STATS")

        if mode == "PORTFOLIO":
            # Portfolio visualization mode (multi-cluster display)
            portfolio_state = state.get("portfolio_state")
            if portfolio_state and isinstance(portfolio_state, dict):
                clusters = portfolio_state.get("clusters", [])
                if clusters:
                    success = handle_portfolio_mode(clusters)
                    if not success:
                        logger.warning("Failed to send portfolio clusters to Arduino")
                else:
                    logger.debug("Portfolio mode but no clusters data")
            else:
                logger.debug("Portfolio mode but no portfolio_state data")

        elif mode == "STATS":
            # System stats mode (default when no ticker data)
            system_stats = state.get("system_stats")
            if system_stats and isinstance(system_stats, dict):
                # Convert system_stats to stats format expected by handle_stats_mode
                # Calculate pixels_on and brightness from CPU/RAM percentages
                cpu_percent = system_stats.get("cpu_percent", 0)
                ram_percent = system_stats.get("ram_percent", 0)

                # Calculate average load (0-100)
                load_percent = (cpu_percent + ram_percent) / 2.0
                load_percent = max(0, min(100, load_percent))

                # Calculate pixels_on: 0-104 pixels based on load (0% = 0 pixels, 100% = 104 pixels)
                pixels_on = int((load_percent / 100.0) * 104.0)

                # Calculate brightness: 100-220 based on load (0% = 100, 100% = 220)
                brightness = int(100 + (load_percent / 100.0) * 120.0)

                stats = {
                    "cpu_percent": cpu_percent,
                    "ram_percent": ram_percent,
                    "pixels_on": pixels_on,
                    "brightness": brightness,
                }
                success = handle_stats_mode(stats)
                if not success:
                    logger.warning("Failed to send stats to Arduino")
            else:
                logger.debug("Stats mode but no system_stats data")

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


logger.info("LED Display starting (portfolio + stats + ticker modes with LED blink support)...")
App.run(user_loop=loop)
