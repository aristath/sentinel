"""LED display state management for Arduino Uno Q.

This module manages the display state that gets polled by the Arduino App.
- LED 1 & 2: Controlled via linux_leds.py (direct /sys/class/leds/)
- LED 3, 4 & Matrix: Controlled via Arduino App polling /api/status/led/display

Display modes:
- normal: Calm breathing wave (default)
- syncing: Faster wave during sync operations
- trade: Expanding ring celebration
- error: Scrolling error text
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.infrastructure.events import SystemEvent, subscribe
from app.infrastructure.hardware.linux_leds import (
    flash_led2_cyan,
    pulse_led1_blue,
)

logger = logging.getLogger(__name__)


@dataclass
class DisplayState:
    """Current display state for API polling."""

    mode: str = "normal"
    error_message: Optional[str] = None
    trade_is_buy: Optional[bool] = None
    since: float = field(default_factory=time.time)
    led3: list[int] = field(default_factory=lambda: [0, 0, 0])
    led4: list[int] = field(default_factory=lambda: [0, 0, 0])


_state = DisplayState()


def get_display_state() -> dict:
    """Get current display state for API endpoint."""
    return {
        "mode": _state.mode,
        "error_message": _state.error_message,
        "trade_is_buy": _state.trade_is_buy,
        "since": _state.since,
        "led3": _state.led3,
        "led4": _state.led4,
    }


def set_mode(mode: str, error_message: Optional[str] = None, trade_is_buy: Optional[bool] = None) -> None:
    """Set display mode."""
    _state.mode = mode
    _state.error_message = error_message if mode == "error" else None
    _state.trade_is_buy = trade_is_buy if mode == "trade" else None
    _state.since = time.time()
    logger.debug(f"Display mode: {mode}")


def set_led3(r: int, g: int, b: int) -> None:
    """Set LED 3 color (sync indicator)."""
    _state.led3 = [r, g, b]


def set_led4(r: int, g: int, b: int) -> None:
    """Set LED 4 color (processing indicator)."""
    _state.led4 = [r, g, b]


# Event handlers

def _on_sync_start(event: SystemEvent, **data) -> None:
    set_mode("syncing")
    set_led3(0, 0, 255)


def _on_sync_complete(event: SystemEvent, **data) -> None:
    set_mode("normal")
    set_led3(0, 0, 0)


def _on_api_call_start(event: SystemEvent, **data) -> None:
    pulse_led1_blue(True)


def _on_api_call_end(event: SystemEvent, **data) -> None:
    pulse_led1_blue(False)


def _on_processing_start(event: SystemEvent, **data) -> None:
    set_led4(255, 165, 0)


def _on_processing_end(event: SystemEvent, **data) -> None:
    set_led4(0, 0, 0)


def _on_web_request(event: SystemEvent, **data) -> None:
    flash_led2_cyan()


def _on_trade_executed(event: SystemEvent, is_buy: bool = True, **data) -> None:
    set_mode("trade", trade_is_buy=is_buy)


def _on_error_occurred(event: SystemEvent, message: str = "ERROR", **data) -> None:
    set_mode("error", error_message=message)


def _on_error_cleared(event: SystemEvent, **data) -> None:
    set_mode("normal")


def setup_event_subscriptions() -> None:
    """Subscribe to all system events. Call once during app startup."""
    subscribe(SystemEvent.SYNC_START, _on_sync_start)
    subscribe(SystemEvent.SYNC_COMPLETE, _on_sync_complete)
    subscribe(SystemEvent.API_CALL_START, _on_api_call_start)
    subscribe(SystemEvent.API_CALL_END, _on_api_call_end)
    subscribe(SystemEvent.PROCESSING_START, _on_processing_start)
    subscribe(SystemEvent.PROCESSING_END, _on_processing_end)
    subscribe(SystemEvent.WEB_REQUEST, _on_web_request)
    subscribe(SystemEvent.TRADE_EXECUTED, _on_trade_executed)
    subscribe(SystemEvent.ERROR_OCCURRED, _on_error_occurred)
    subscribe(SystemEvent.ERROR_CLEARED, _on_error_cleared)
    logger.info("LED display event subscriptions ready")
