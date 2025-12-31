"""Linux sysfs LED control for Arduino Uno Q RGB LEDs.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.display.external.linux_leds instead.
"""

# Backward compatibility re-exports (temporary - will be removed in Phase 5)
from app.modules.display.external.linux_leds import (
    flash_led1_blue,
    flash_led2_cyan,
    led1_off,
    led2_off,
    pulse_led1_blue,
    set_led1,
    set_led2,
)

__all__ = [
    "set_led1",
    "set_led2",
    "led1_off",
    "led2_off",
    "flash_led1_blue",
    "flash_led2_cyan",
    "pulse_led1_blue",
]
