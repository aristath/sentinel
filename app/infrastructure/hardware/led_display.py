"""LED matrix display service for Arduino Uno Q.

Communicates with the STM32U585 MCU via serial to control:
- 8x13 blue LED matrix
- 4 RGB LEDs

Display modes:
- idle: Subtle animation
- health: Portfolio allocation bars
- trading: Active trade animation
- error: Blinking error pattern
- balance: Abacus-style portfolio value display
- api_call: Scrolling dots during API calls
- syncing: Wave animation during sync
- no_wifi: Scrolling "NO WIFI" text
- heartbeat: Brief pulse animation
"""

import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from contextlib import contextmanager

try:
    import serial
except ImportError:
    serial = None

from app.config import settings

logger = logging.getLogger(__name__)


class DisplayMode(Enum):
    IDLE = "idle"
    HEALTH = "health"
    TRADING = "trading"
    ERROR = "error"
    SUCCESS = "success"
    BALANCE = "balance"       # Abacus-style portfolio value
    API_CALL = "api_call"     # Scrolling dots on matrix
    SYNCING = "syncing"       # Wave pattern on matrix
    NO_WIFI = "no_wifi"       # Scrolling "NO WIFI" text
    HEARTBEAT = "heartbeat"   # Brief pulse animation


@dataclass
class LEDState:
    """Current LED display state."""
    mode: DisplayMode
    geo_eu: float  # 0-1 allocation percentage
    geo_asia: float
    geo_us: float
    system_status: str  # ok, syncing, error
    message: str


class LEDDisplay:
    """Controller for Arduino Uno Q LED matrix display."""

    def __init__(self):
        self._serial: Optional[serial.Serial] = None
        self._connected = False
        self._current_state: Optional[LEDState] = None
        # For API-based display (Arduino Bridge apps)
        self._display_mode: DisplayMode = DisplayMode.BALANCE
        self._display_value: float = 0.0
        self._rgb_flash: Optional[list[int]] = None
        self._heartbeat_pending: bool = False
        # Status indicators for bottom rows
        self._web_request_time: float = 0.0  # Timestamp of last web request
        self._api_call_active: bool = False   # Currently making external API call
        # Error message for scrolling display
        self._error_message: str = ""
        self._system_status: str = "ok"  # ok, syncing, error

    def connect(self) -> bool:
        """Connect to MCU via serial."""
        if serial is None:
            logger.warning("pyserial not installed, LED display disabled")
            return False

        try:
            self._serial = serial.Serial(
                port=settings.led_serial_port,
                baudrate=settings.led_baud_rate,
                timeout=1
            )
            self._connected = True
            logger.info(f"Connected to LED display on {settings.led_serial_port}")

            # Send initial idle state
            self.set_mode(DisplayMode.IDLE)
            return True

        except serial.SerialException as e:
            logger.warning(f"Failed to connect to LED display: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from MCU."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._serial is not None

    def _send_command(self, command: dict) -> bool:
        """Send JSON command to MCU."""
        if not self.is_connected:
            return False

        try:
            data = json.dumps(command) + "\n"
            self._serial.write(data.encode())
            self._serial.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to send LED command: {e}")
            return False

    def set_mode(self, mode: DisplayMode) -> bool:
        """Set display mode."""
        return self._send_command({"cmd": "mode", "mode": mode.value})

    def update_allocation(self, eu: float, asia: float, us: float) -> bool:
        """
        Update geographic allocation display.

        Args:
            eu: EU allocation (0-1)
            asia: Asia allocation (0-1)
            us: US allocation (0-1)
        """
        # Store current state
        self._current_state = LEDState(
            mode=DisplayMode.HEALTH,
            geo_eu=eu,
            geo_asia=asia,
            geo_us=us,
            system_status="ok",
            message=""
        )

        return self._send_command({
            "cmd": "allocation",
            "eu": round(eu, 2),
            "asia": round(asia, 2),
            "us": round(us, 2)
        })

    def set_system_status(self, status: str) -> bool:
        """
        Set system status LED.

        Args:
            status: "ok", "syncing", "error"
        """
        self._system_status = status
        # Clear error message when status becomes ok
        if status == "ok":
            self._error_message = ""

        color_map = {
            "ok": [0, 255, 0],      # Green
            "syncing": [0, 0, 255],  # Blue
            "error": [255, 0, 0],    # Red
            "trading": [255, 165, 0] # Orange
        }
        color = color_map.get(status, [255, 255, 255])

        return self._send_command({
            "cmd": "status",
            "color": color
        })

    def show_trade_animation(self, symbol: str, side: str) -> bool:
        """Show trade execution animation."""
        return self._send_command({
            "cmd": "trade",
            "symbol": symbol[:6],  # Truncate for display
            "side": side
        })

    def show_error(self, message: str = "ERROR", speed_ms: int = None) -> bool:
        """Show error state with scrolling message."""
        self._error_message = message
        self._system_status = "error"
        self._display_mode = DisplayMode.ERROR
        self.set_mode(DisplayMode.ERROR)
        if speed_ms is None:
            speed_ms = settings.led_error_scroll_speed_ms
        return self._send_command({
            "cmd": "error",
            "message": message[:20],  # Truncate
            "speed": speed_ms
        })

    def clear_error(self) -> None:
        """Clear error state."""
        self._error_message = ""
        self._system_status = "ok"

    def show_success(self) -> bool:
        """Show success animation."""
        return self._send_command({"cmd": "success"})

    def scroll_text(self, text: str, speed_ms: int = None) -> bool:
        """Scroll text across matrix."""
        if speed_ms is None:
            speed_ms = settings.led_error_scroll_speed_ms
        return self._send_command({
            "cmd": "scroll",
            "text": text[:50],  # Limit length
            "speed": speed_ms
        })

    def clear(self) -> bool:
        """Clear display."""
        return self._send_command({"cmd": "clear"})

    def get_state(self) -> Optional[LEDState]:
        """Get current display state."""
        return self._current_state

    def show_balance(self, value: float) -> bool:
        """
        Display portfolio balance in abacus-style dots.

        Each row represents a digit place, with dots lit to show the digit value.
        Example: €20,520 → rows showing 2,0,5,2,0

        Args:
            value: Portfolio value in EUR
        """
        if self._current_state:
            self._current_state.mode = DisplayMode.BALANCE

        return self._send_command({
            "cmd": "balance",
            "value": int(value)
        })

    def show_heartbeat(self) -> bool:
        """
        Show brief heartbeat pulse animation.

        Called every 60 seconds to prove the app is alive.
        """
        return self._send_command({"cmd": "heartbeat"})

    def show_syncing(self) -> bool:
        """Show wave animation during sync operations."""
        return self._send_command({
            "cmd": "mode",
            "mode": DisplayMode.SYNCING.value
        })

    def show_api_call(self) -> bool:
        """Show scrolling dots animation during API calls."""
        return self._send_command({
            "cmd": "mode",
            "mode": DisplayMode.API_CALL.value
        })

    def show_no_wifi(self) -> bool:
        """Show scrolling 'NO WIFI' text when disconnected."""
        return self._send_command({
            "cmd": "scroll",
            "text": "NO WIFI",
            "loop": True,
            "speed": settings.led_error_scroll_speed_ms
        })

    def flash_rgb(self, color: list[int]) -> bool:
        """
        Flash RGB LEDs briefly without changing matrix display.

        Used for web request indication.

        Args:
            color: RGB color as [r, g, b] (0-255 each)
        """
        return self._send_command({
            "cmd": "flash",
            "color": color
        })

    def flash_web_request(self) -> bool:
        """Flash cyan on RGB LEDs to indicate web request."""
        return self.flash_rgb([0, 255, 255])  # Cyan

    @staticmethod
    def check_wifi() -> bool:
        """
        Check if we have network connectivity.

        Returns True if we can reach the internet.
        """
        try:
            # Try to connect to Google's DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def get_display_state(self) -> dict:
        """
        Get current display state for API-based display apps.

        Returns dict with mode, value, and any pending animations.
        """
        state = {
            "mode": self._display_mode.value,
            "value": self._display_value,
            "heartbeat": self._heartbeat_pending,
            "rgb_flash": self._rgb_flash,
            "system_status": self._system_status,
            "error_message": self._error_message,
            # Status indicators for bottom rows
            "web_request_active": (time.time() - self._web_request_time) < 0.5,
            "api_call_active": self._api_call_active,
        }
        # Clear one-time events after reading
        self._heartbeat_pending = False
        self._rgb_flash = None
        return state

    def set_display_value(self, value: float):
        """Set the portfolio value for balance display."""
        self._display_value = value
        self._display_mode = DisplayMode.BALANCE

    def set_display_mode(self, mode: DisplayMode):
        """Set the current display mode."""
        self._display_mode = mode

    def trigger_heartbeat(self):
        """Trigger a heartbeat animation on next poll."""
        self._heartbeat_pending = True

    def trigger_rgb_flash(self, color: list[int]):
        """Trigger an RGB flash on next poll."""
        self._rgb_flash = color

    def mark_web_request(self):
        """Mark that a web request was just served."""
        self._web_request_time = time.time()

    def set_api_call_active(self, active: bool):
        """Set whether an external API call is in progress."""
        self._api_call_active = active


# Singleton instance
_display: Optional[LEDDisplay] = None


def get_led_display() -> LEDDisplay:
    """Get or create the LED display singleton."""
    global _display
    if _display is None:
        _display = LEDDisplay()
    return _display


async def update_balance_display(position_repo) -> bool:
    """
    Update LED display with current portfolio balance in abacus style.

    Called after sync operations to show total portfolio value.

    Args:
        position_repo: PositionRepository instance

    Returns:
        True if update was successful
    """
    display = get_led_display()

    if not display.is_connected:
        return False

    try:
        # Get total portfolio value from positions
        positions = await position_repo.get_all()
        total_value = sum(pos.market_value_eur for pos in positions if pos.market_value_eur)

        if total_value:
            display.show_balance(total_value)
            return True

    except Exception as e:
        logger.error(f"Failed to update balance display: {e}")

    return False
