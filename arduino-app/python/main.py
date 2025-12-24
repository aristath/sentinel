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
# 7-pixel tall variable-width font for ticker
# Each character is 7 rows, variable width (2-5 pixels)
# Pattern strings: '1' = lit, '0' = off
# =============================================================================

FONT_7PX = {
    # Digits (4px wide)
    '0': ['0110', '1001', '1001', '1001', '1001', '1001', '0110'],
    '1': ['0010', '0110', '0010', '0010', '0010', '0010', '0111'],
    '2': ['0110', '1001', '0001', '0010', '0100', '1000', '1111'],
    '3': ['0110', '1001', '0001', '0110', '0001', '1001', '0110'],
    '4': ['0010', '0110', '1010', '1111', '0010', '0010', '0010'],
    '5': ['1111', '1000', '1110', '0001', '0001', '1001', '0110'],
    '6': ['0110', '1001', '1000', '1110', '1001', '1001', '0110'],
    '7': ['1111', '0001', '0010', '0010', '0100', '0100', '0100'],
    '8': ['0110', '1001', '1001', '0110', '1001', '1001', '0110'],
    '9': ['0110', '1001', '1001', '0111', '0001', '1001', '0110'],

    # Letters (4px wide, some are 5px)
    'A': ['0110', '1001', '1001', '1111', '1001', '1001', '1001'],
    'B': ['1110', '1001', '1001', '1110', '1001', '1001', '1110'],
    'C': ['0110', '1001', '1000', '1000', '1000', '1001', '0110'],
    'D': ['1110', '1001', '1001', '1001', '1001', '1001', '1110'],
    'E': ['1111', '1000', '1000', '1110', '1000', '1000', '1111'],
    'F': ['1111', '1000', '1000', '1110', '1000', '1000', '1000'],
    'G': ['0110', '1001', '1000', '1011', '1001', '1001', '0110'],
    'H': ['1001', '1001', '1001', '1111', '1001', '1001', '1001'],
    'I': ['111', '010', '010', '010', '010', '010', '111'],  # 3px
    'J': ['0011', '0001', '0001', '0001', '0001', '1001', '0110'],
    'K': ['1001', '1010', '1100', '1000', '1100', '1010', '1001'],
    'L': ['1000', '1000', '1000', '1000', '1000', '1000', '1111'],
    'M': ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],  # 5px
    'N': ['1001', '1101', '1101', '1011', '1011', '1001', '1001'],
    'O': ['0110', '1001', '1001', '1001', '1001', '1001', '0110'],
    'P': ['1110', '1001', '1001', '1110', '1000', '1000', '1000'],
    'Q': ['0110', '1001', '1001', '1001', '1011', '0110', '0001'],
    'R': ['1110', '1001', '1001', '1110', '1100', '1010', '1001'],
    'S': ['0111', '1000', '1000', '0110', '0001', '0001', '1110'],
    'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],  # 5px
    'U': ['1001', '1001', '1001', '1001', '1001', '1001', '0110'],
    'V': ['10001', '10001', '10001', '01010', '01010', '00100', '00100'],  # 5px
    'W': ['10001', '10001', '10101', '10101', '10101', '01010', '01010'],  # 5px
    'X': ['1001', '1001', '0110', '0110', '0110', '1001', '1001'],
    'Y': ['10001', '10001', '01010', '00100', '00100', '00100', '00100'],  # 5px
    'Z': ['1111', '0001', '0010', '0100', '1000', '1000', '1111'],

    # Currency symbols (5px wide)
    '€': ['00110', '01001', '11100', '01000', '11100', '01001', '00110'],  # Euro sign
    '$': ['00100', '01111', '10100', '01110', '00101', '11110', '00100'],
    '£': ['00110', '01001', '01000', '11110', '01000', '01000', '11111'],

    # Special characters
    '|': ['1', '1', '1', '1', '1', '1', '1'],  # 1px
    '-': ['0000', '0000', '0000', '1111', '0000', '0000', '0000'],  # 4px
    '+': ['000', '010', '010', '111', '010', '010', '000'],  # 3px
    '.': ['0', '0', '0', '0', '0', '0', '1'],  # 1px
    ',': ['00', '00', '00', '00', '00', '01', '10'],  # 2px
    ':': ['0', '0', '1', '0', '0', '1', '0'],  # 1px
    ' ': ['00', '00', '00', '00', '00', '00', '00'],  # 2px space
}


# =============================================================================
# Animation state
# =============================================================================

phase = 0
scroll_offset = 0
trade_start_time = 0
last_mode = None


# =============================================================================
# Matrix animations
# =============================================================================

def animate_normal(phase: int) -> np.ndarray:
    """Heartbeat pulse - radial glow from center that fades outward and over time.

    Center is brightest, fades radially outward, and fades over time.
    Fixed 1.5 second cycle with fixed brightness.
    """
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    # Center of matrix
    center_row = (ROWS - 1) / 2  # 3.5
    center_col = (COLS - 1) / 2  # 6

    # Max radius (30% smaller than full matrix)
    max_radius = 5.5

    # Fixed 15 frames for smooth 1.5 second cycle (10 fps)
    cycle_frames = 15

    # Fixed peak brightness
    peak_brightness = 200

    # Current expansion radius (0 to max_radius)
    expansion = (phase % cycle_frames) * max_radius / cycle_frames

    # Time-based fade (balanced curve)
    time_fade = (1.0 - (phase % cycle_frames) / cycle_frames) ** 1.2

    # Effective radius for radial fade (minimum 1.0 to avoid div by zero)
    effective_radius = max(expansion, 1.0)

    for row in range(ROWS):
        for col in range(COLS):
            # Distance from center
            dist = math.sqrt((row - center_row) ** 2 + (col - center_col) ** 2)

            # Only light pixels within current expansion radius
            if dist <= expansion:
                # Radial fade relative to current expansion (not max_radius)
                # This ensures edge pixels are always visibly dimmer
                radial_fade = 1.0 - (dist / effective_radius) ** 2.0

                # Combined brightness: radial gradient * time fade
                brightness = int(peak_brightness * radial_fade * time_fade)
                arr[row, col] = max(0, min(255, brightness))

    return arr


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


def animate_error_scroll(text: str, offset: int, brightness: int = PIXEL_BRIGHT) -> np.ndarray:
    """Scrolling error text across matrix using 7px font.

    This is now just a wrapper around animate_ticker for consistency.
    """
    return animate_ticker(text, offset, brightness)


def get_char_width(char: str) -> int:
    """Get width of a character in the 7px font."""
    pattern = FONT_7PX.get(char.upper())
    if pattern and len(pattern) > 0:
        return len(pattern[0])
    return 2  # Default for unknown chars


def get_text_width(text: str) -> int:
    """Calculate total pixel width of text including spacing."""
    width = 0
    for char in text.upper():
        width += get_char_width(char) + 1  # +1 for spacing
    return max(0, width - 1)  # Remove trailing space


def animate_ticker(text: str, offset: int, brightness: int = PIXEL_BRIGHT) -> np.ndarray:
    """Smooth scrolling ticker using 7px variable-width font.

    Text scrolls right-to-left across the 8x13 matrix.
    Uses 7-pixel tall characters, leaving 1 row for spacing at bottom.

    Args:
        text: Text to display
        offset: Current scroll offset (pixels)
        brightness: LED brightness (0-255)
    """
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    if not text:
        return arr

    text = text.upper()
    text_width = get_text_width(text)

    # Wrap offset for seamless looping
    total_width = text_width + COLS
    start_col = COLS - (offset % total_width)

    # Render each character
    col = start_col
    for char in text:
        pattern = FONT_7PX.get(char)
        if pattern:
            char_width = len(pattern[0])
            for row_idx, row_pattern in enumerate(pattern):
                for col_idx, pixel in enumerate(row_pattern):
                    if pixel == '1':
                        c = col + col_idx
                        # Only draw if within visible matrix
                        if 0 <= c < COLS and row_idx < ROWS:
                            arr[row_idx, c] = brightness
            col += char_width + 1  # Move to next char position + spacing
        else:
            # Unknown char - skip 3 pixels
            col += 3

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
        text: Text to scroll (ASCII only, no Euro symbol)
        speed: Milliseconds per scroll step (lower = faster)
    """
    try:
        # Replace Euro symbol with EUR (Font_5x7 only has ASCII 32-126)
        text = text.replace("€", "EUR")
        Bridge.call("scrollText", text, speed, timeout=30)
        return True
    except Exception as e:
        logger.debug(f"scrollText failed: {e}")
        return False


def print_text(text: str, x: int = 0, y: int = 1) -> bool:
    """Display static text at position using native ArduinoGraphics.

    Args:
        text: Text to display (ASCII only)
        x: X position
        y: Y position
    """
    try:
        text = text.replace("€", "EUR")
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
    global phase, scroll_offset, trade_start_time, last_mode

    try:
        state = fetch_display_state()

        if state is None:
            # API unreachable - show scrolling error with default brightness
            draw_frame(Frame(animate_error_scroll("API DOWN", scroll_offset, PIXEL_BRIGHT)))
            scroll_offset += 1
            time.sleep(0.12)
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
        led_brightness = int(state.get("led_brightness", PIXEL_BRIGHT))
        ticker_sleep = ticker_speed_ms / 1000.0  # Convert ms to seconds

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
            # Scrolling error text using configured brightness
            draw_frame(Frame(animate_error_scroll(error_message, scroll_offset, led_brightness)))
            scroll_offset += 1
            time.sleep(0.12)

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
                else:
                    draw_frame(Frame(animate_normal(phase)))
                    time.sleep(0.1)

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
            else:
                # Fallback to heartbeat if no ticker
                draw_frame(Frame(animate_normal(phase)))
                time.sleep(0.1)

        phase += 1

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(1)


logger.info("LED Display starting (ambient awareness mode)...")
App.run(user_loop=loop)
