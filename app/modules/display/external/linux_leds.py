"""Linux sysfs LED control for Arduino Uno Q RGB LEDs.

Controls LED 1 and LED 2 via /sys/class/leds/ filesystem interface.
These LEDs are driven by the Qualcomm Dragonwing QRB2210 processor.

LED 1 (D27301) - User-controlled:
    - red:user → GPIO_41
    - green:user → GPIO_42
    - blue:user → GPIO_60

LED 2 (D27302) - System indicators (can be user-controlled):
    - red:panic → GPIO_39
    - green:wlan → GPIO_40
    - blue:bt → GPIO_47

PWM frequency is approximately 2 kHz for smooth color transitions.
Brightness values: 0-255.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

LED_BASE = "/sys/class/leds"

# LED 1 paths (user-controlled)
LED1_RED = f"{LED_BASE}/red:user/brightness"
LED1_GREEN = f"{LED_BASE}/green:user/brightness"
LED1_BLUE = f"{LED_BASE}/blue:user/brightness"

# LED 2 paths (system indicators, can override)
LED2_RED = f"{LED_BASE}/red:panic/brightness"
LED2_GREEN = f"{LED_BASE}/green:wlan/brightness"
LED2_BLUE = f"{LED_BASE}/blue:bt/brightness"

# Track if LEDs are available
_leds_available: Optional[bool] = None


def _check_leds_available() -> bool:
    """Check if sysfs LED interface is available."""
    global _leds_available
    if _leds_available is None:
        try:
            # Try to read LED 1 red channel
            with open(LED1_RED, "r") as f:
                f.read()
            _leds_available = True
        except (IOError, FileNotFoundError, PermissionError):
            _leds_available = False
            logger.debug("Linux LEDs not available (not running on Arduino Uno Q)")
    return _leds_available


def _write_brightness(path: str, value: int) -> bool:
    """Write brightness value to sysfs LED file.

    Args:
        path: Full path to brightness file
        value: Brightness value 0-255

    Returns:
        True if write succeeded, False otherwise
    """
    if not _check_leds_available():
        return False

    try:
        with open(path, "w") as f:
            f.write(str(max(0, min(255, value))))
        return True
    except (IOError, PermissionError) as e:
        logger.debug(f"Failed to write LED: {e}")
        return False


def set_led1(r: int, g: int, b: int) -> bool:
    """Set LED 1 color (user-controlled LED).

    Used for API call activity indicator.

    Args:
        r: Red brightness 0-255
        g: Green brightness 0-255
        b: Blue brightness 0-255

    Returns:
        True if all writes succeeded
    """
    success = True
    success &= _write_brightness(LED1_RED, r)
    success &= _write_brightness(LED1_GREEN, g)
    success &= _write_brightness(LED1_BLUE, b)
    return success


def set_led2(r: int, g: int, b: int) -> bool:
    """Set LED 2 color (system indicator LED).

    Used for web request activity indicator.
    Note: This overrides system indicators (panic, wlan, bt).

    Args:
        r: Red brightness 0-255
        g: Green brightness 0-255
        b: Blue brightness 0-255

    Returns:
        True if all writes succeeded
    """
    success = True
    success &= _write_brightness(LED2_RED, r)
    success &= _write_brightness(LED2_GREEN, g)
    success &= _write_brightness(LED2_BLUE, b)
    return success


def led1_off() -> bool:
    """Turn LED 1 off."""
    return set_led1(0, 0, 0)


def led2_off() -> bool:
    """Turn LED 2 off."""
    return set_led2(0, 0, 0)


# --- Activity indicator helpers ---

_led1_timer: Optional[threading.Timer] = None
_led2_timer: Optional[threading.Timer] = None


def flash_led1_blue(duration: float = 0.3) -> None:
    """Flash LED 1 blue briefly for API call activity.

    Args:
        duration: How long to keep LED on (seconds)
    """
    global _led1_timer

    # Cancel any pending off timer
    if _led1_timer is not None:
        _led1_timer.cancel()

    # Turn on blue
    set_led1(0, 0, 255)

    # Schedule turn off
    _led1_timer = threading.Timer(duration, led1_off)
    _led1_timer.daemon = True
    _led1_timer.start()


def flash_led2_cyan(duration: float = 0.15) -> None:
    """Flash LED 2 cyan briefly for web request activity.

    Args:
        duration: How long to keep LED on (seconds)
    """
    global _led2_timer

    # Cancel any pending off timer
    if _led2_timer is not None:
        _led2_timer.cancel()

    # Turn on cyan (green + blue)
    set_led2(0, 255, 255)

    # Schedule turn off
    _led2_timer = threading.Timer(duration, led2_off)
    _led2_timer.daemon = True
    _led2_timer.start()


def pulse_led1_blue(active: bool) -> None:
    """Set LED 1 to steady blue when active, off when not.

    For longer-running API calls where a flash isn't appropriate.

    Args:
        active: True to turn on, False to turn off
    """
    global _led1_timer

    # Cancel any pending timer
    if _led1_timer is not None:
        _led1_timer.cancel()
        _led1_timer = None

    if active:
        set_led1(0, 0, 255)
    else:
        led1_off()
