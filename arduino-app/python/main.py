# Arduino Trader LED Display
# Ambient awareness display with 4 matrix states and RGB LED activity indicators

from arduino.app_utils import App, Bridge, Logger, Frame
import math
import time
import requests
import numpy as np

logger = Logger("trader-display")

API_URL = "http://172.17.0.1:8000"

# Persistent HTTP session for connection pooling (reuses TCP connections)
_http_session = requests.Session()

ROWS = 8
COLS = 13

# Default brightness constants (0 = off, 255 = brightest)
# These can be overridden by API settings
PIXEL_BRIGHT = 150    # Main animation brightness (default)
PIXEL_DIM = 60        # Secondary/fading pixels
PIXEL_OFF = 0

# Default ticker speed in ms (can be overridden by API)
DEFAULT_TICKER_SPEED = 50


# =============================================================================
# Animation state
# =============================================================================

phase = 0
trade_start_time = 0
last_mode = None


# =============================================================================
# Matrix animations
# =============================================================================

def animate_syncing(phase: int) -> np.ndarray:
    """Faster horizontal wave - shows active work.

    Wave travels left-to-right over ~1 second.
    Peak brightness 150.
    """
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    # Wave position (1 second cycle at 100ms updates = 10 frames)
    wave_col = (phase % 15) * COLS / 15

    for col in range(COLS):
        dist = abs(col - wave_col)
        if dist <= 2:
            brightness = int(150 * (1 - dist / 3))
            for row in range(ROWS):
                arr[row, col] = max(0, brightness)

    return arr


def animate_trade(phase: int, is_buy: bool) -> np.ndarray:
    """Expanding ring from center - celebration.

    Ring expands over ~1 second, full brightness.
    """
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    # Center of matrix
    center_row = ROWS / 2 - 0.5
    center_col = COLS / 2 - 0.5

    # Ring radius expands (10 frames = 1 second)
    radius = (phase % 10) * max(ROWS, COLS) / 10

    for row in range(ROWS):
        for col in range(COLS):
            dist = math.sqrt((row - center_row) ** 2 + (col - center_col) ** 2)
            # Draw ring with some thickness
            if abs(dist - radius) < 1.5:
                arr[row, col] = 200

    return arr


# =============================================================================
# Bridge helpers
# =============================================================================

def draw_frame(frame: Frame) -> bool:
    """Safely draw a frame to the LED matrix."""
    try:
        Bridge.call("draw", frame.to_board_bytes(), timeout=5)
        return True
    except Exception as e:
        logger.error(f"Draw failed: {e}")
        return False


def set_rgb3(r: int, g: int, b: int) -> bool:
    """Set RGB LED 3 color (sync indicator)."""
    try:
        Bridge.call("setRGB3", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setRGB3 failed: {e}")
        return False


def set_rgb4(r: int, g: int, b: int) -> bool:
    """Set RGB LED 4 color (processing indicator)."""
    try:
        Bridge.call("setRGB4", r, g, b, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setRGB4 failed: {e}")
        return False


def scroll_text(text: str, speed: int = 50) -> bool:
    """Scroll text across LED matrix using native ArduinoGraphics.

    Args:
        text: Text to scroll
        speed: Milliseconds per scroll step (lower = faster)
    """
    try:
        Bridge.call("scrollText", text, speed, timeout=30)
        return True
    except Exception as e:
        logger.debug(f"scrollText failed: {e}")
        return False


def print_text(text: str, x: int = 0, y: int = 1) -> bool:
    """Display static text at position using native ArduinoGraphics.

    Args:
        text: Text to display
        x: X position
        y: Y position
    """
    try:
        Bridge.call("printText", text, x, y, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"printText failed: {e}")
        return False


# =============================================================================
# API communication
# =============================================================================

def fetch_display_state() -> dict | None:
    """Fetch display state from FastAPI backend.

    Uses persistent session for HTTP connection pooling (keep-alive).
    """
    try:
        with _http_session.get(f"{API_URL}/api/status/led/display", timeout=2) as resp:
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug(f"API fetch: {e}")
    return None


# =============================================================================
# Main loop
# =============================================================================

def loop():
    global phase, trade_start_time, last_mode

    try:
        state = fetch_display_state()

        if state is None:
            # API unreachable - show scrolling error using native text
            scroll_text("TRADING API OFFLINE", DEFAULT_TICKER_SPEED)
            time.sleep(2)  # Prevent rapid polling during API failures
            return

        mode = state.get("mode", "normal")
        error_message = state.get("error_message")
        trade_is_buy = state.get("trade_is_buy", True)
        led3 = state.get("led3", [0, 0, 0])
        led4 = state.get("led4", [0, 0, 0])
        ticker_text = state.get("ticker_text", "")
        activity_message = state.get("activity_message", "")

        # Get configurable settings from API
        ticker_speed_ms = state.get("ticker_speed", DEFAULT_TICKER_SPEED)

        # Mode change logging
        if mode != last_mode:
            logger.info(f"Mode: {mode}")
            if mode == "trade":
                trade_start_time = time.time()
            last_mode = mode

        # Update RGB LEDs 3 & 4 from API state
        set_rgb3(led3[0], led3[1], led3[2])
        set_rgb4(led4[0], led4[1], led4[2])

        # Matrix animation based on mode
        # Priority: error > trade > activity > syncing > ticker
        if mode == "error" and error_message:
            # Scrolling error text using native ArduinoGraphics
            scroll_text(error_message, int(ticker_speed_ms))

        elif mode == "trade":
            # Trade celebration - auto-returns to normal after 3s
            elapsed = time.time() - trade_start_time
            if elapsed < 3.0:
                draw_frame(Frame(animate_trade(phase, trade_is_buy)))
                time.sleep(0.1)
            else:
                # Trade animation done, show ticker using native text
                if ticker_text:
                    scroll_text(ticker_text, int(ticker_speed_ms))

        elif activity_message:
            # Activity message using native text (higher priority than ticker)
            # Activity runs slightly faster than normal ticker
            activity_speed = max(20, int(ticker_speed_ms * 0.8))
            scroll_text(activity_message, activity_speed)

        elif mode == "syncing":
            # Active sync wave
            draw_frame(Frame(animate_syncing(phase)))
            time.sleep(0.1)

        else:
            # Normal mode - show ticker using native ArduinoGraphics text
            if ticker_text:
                scroll_text(ticker_text, int(ticker_speed_ms))

        phase += 1

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(1)


logger.info("LED Display starting (ambient awareness mode)...")
App.run(user_loop=loop)
