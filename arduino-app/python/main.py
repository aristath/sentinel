# Arduino Trader LED Display
# Ambient awareness display with 4 matrix states and RGB LED activity indicators

from arduino.app_utils import App, Bridge, Logger, Frame
import math
import time
import requests
import numpy as np

logger = Logger("trader-display")

API_URL = "http://172.17.0.1:8000"

ROWS = 8
COLS = 13

# Brightness constants (0 = off, 255 = brightest)
PIXEL_BRIGHT = 150    # Main animation brightness
PIXEL_DIM = 60        # Secondary/fading pixels
PIXEL_OFF = 0


# =============================================================================
# Character patterns for scrolling text (3x5 pixels each)
# =============================================================================

DIGITS = {
    '0': ['111', '101', '101', '101', '111'],
    '1': ['010', '110', '010', '010', '111'],
    '2': ['111', '001', '111', '100', '111'],
    '3': ['111', '001', '111', '001', '111'],
    '4': ['101', '101', '111', '001', '001'],
    '5': ['111', '100', '111', '001', '111'],
    '6': ['111', '100', '111', '101', '111'],
    '7': ['111', '001', '001', '001', '001'],
    '8': ['111', '101', '111', '101', '111'],
    '9': ['111', '101', '111', '001', '111'],
}

LETTERS = {
    'A': ['010', '101', '111', '101', '101'],
    'B': ['110', '101', '110', '101', '110'],
    'C': ['011', '100', '100', '100', '011'],
    'D': ['110', '101', '101', '101', '110'],
    'E': ['111', '100', '110', '100', '111'],
    'F': ['111', '100', '110', '100', '100'],
    'G': ['011', '100', '101', '101', '011'],
    'H': ['101', '101', '111', '101', '101'],
    'I': ['111', '010', '010', '010', '111'],
    'J': ['001', '001', '001', '101', '010'],
    'K': ['101', '110', '100', '110', '101'],
    'L': ['100', '100', '100', '100', '111'],
    'M': ['101', '111', '101', '101', '101'],
    'N': ['101', '111', '111', '101', '101'],
    'O': ['111', '101', '101', '101', '111'],
    'P': ['110', '101', '110', '100', '100'],
    'Q': ['010', '101', '101', '110', '011'],
    'R': ['110', '101', '110', '101', '101'],
    'S': ['011', '100', '010', '001', '110'],
    'T': ['111', '010', '010', '010', '010'],
    'U': ['101', '101', '101', '101', '111'],
    'V': ['101', '101', '101', '101', '010'],
    'W': ['101', '101', '101', '111', '101'],
    'X': ['101', '101', '010', '101', '101'],
    'Y': ['101', '101', '010', '010', '010'],
    'Z': ['111', '001', '010', '100', '111'],
    ' ': ['000', '000', '000', '000', '000'],
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
    """Slow breathing wave - calm ambient presence.

    Single column travels left-to-right over ~3 seconds.
    Peak brightness 80, fades over 2 columns.
    """
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    # Wave position (3 second cycle at 100ms updates = 30 frames)
    wave_col = (phase % 30) * COLS / 30

    for col in range(COLS):
        dist = abs(col - wave_col)
        if dist <= 2:
            # Fade based on distance from wave center
            brightness = int(80 * (1 - dist / 2.5))
            for row in range(ROWS):
                arr[row, col] = max(0, brightness)

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


def animate_error_scroll(text: str, offset: int) -> np.ndarray:
    """Scrolling error text across matrix."""
    arr = np.zeros((ROWS, COLS), dtype=np.uint8)

    text_width = len(text) * 4  # Each char is 3 wide + 1 space
    start_col = COLS - (offset % (text_width + COLS))
    start_row = 1  # Vertically center the 5-row text

    col = start_col
    for char in text.upper():
        pattern = LETTERS.get(char, DIGITS.get(char))
        if pattern:
            for row_idx, row_pattern in enumerate(pattern):
                for col_idx, pixel in enumerate(row_pattern):
                    if pixel == '1':
                        r = start_row + row_idx
                        c = col + col_idx
                        if 0 <= r < ROWS and 0 <= c < COLS:
                            arr[r, c] = PIXEL_BRIGHT
            col += 4
        elif char == ' ':
            col += 2

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


# =============================================================================
# API communication
# =============================================================================

def fetch_display_state() -> dict | None:
    """Fetch display state from FastAPI backend."""
    try:
        resp = requests.get(f"{API_URL}/api/status/led/display", timeout=2)
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
            # API unreachable - show scrolling error
            draw_frame(Frame(animate_error_scroll("API DOWN", scroll_offset)))
            scroll_offset += 1
            time.sleep(0.12)
            return

        mode = state.get("mode", "normal")
        error_message = state.get("error_message")
        trade_is_buy = state.get("trade_is_buy", True)
        led3 = state.get("led3", [0, 0, 0])
        led4 = state.get("led4", [0, 0, 0])

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
        if mode == "error" and error_message:
            # Scrolling error text
            draw_frame(Frame(animate_error_scroll(error_message, scroll_offset)))
            scroll_offset += 1
            time.sleep(0.12)

        elif mode == "trade":
            # Trade celebration - auto-returns to normal after 3s
            elapsed = time.time() - trade_start_time
            if elapsed < 3.0:
                draw_frame(Frame(animate_trade(phase, trade_is_buy)))
                time.sleep(0.1)
            else:
                # Trade animation done, show normal
                draw_frame(Frame(animate_normal(phase)))
                time.sleep(0.1)

        elif mode == "syncing":
            # Active sync wave
            draw_frame(Frame(animate_syncing(phase)))
            time.sleep(0.1)

        else:
            # Normal - calm breathing wave
            draw_frame(Frame(animate_normal(phase)))
            time.sleep(0.1)

        phase += 1

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(1)


logger.info("LED Display starting (ambient awareness mode)...")
App.run(user_loop=loop)
