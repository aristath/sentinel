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

    def show_error(self, message: str = "") -> bool:
        """Show error state."""
        self.set_mode(DisplayMode.ERROR)
        return self._send_command({
            "cmd": "error",
            "message": message[:20]  # Truncate
        })

    def show_success(self) -> bool:
        """Show success animation."""
        return self._send_command({"cmd": "success"})

    def scroll_text(self, text: str) -> bool:
        """Scroll text across matrix."""
        return self._send_command({
            "cmd": "scroll",
            "text": text[:50]  # Limit length
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
            "loop": True
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


# Singleton instance
_display: Optional[LEDDisplay] = None


def get_led_display() -> LEDDisplay:
    """Get or create the LED display singleton."""
    global _display
    if _display is None:
        _display = LEDDisplay()
    return _display


async def update_display_from_portfolio(db) -> bool:
    """
    Update LED display with current portfolio allocation.

    Called after portfolio sync to reflect current state.
    """
    display = get_led_display()

    if not display.is_connected:
        return False

    try:
        # Get current allocation
        cursor = await db.execute("""
            SELECT
                SUM(CASE WHEN s.geography = 'EU' THEN p.quantity * p.current_price ELSE 0 END) as eu,
                SUM(CASE WHEN s.geography = 'ASIA' THEN p.quantity * p.current_price ELSE 0 END) as asia,
                SUM(CASE WHEN s.geography = 'US' THEN p.quantity * p.current_price ELSE 0 END) as us,
                SUM(p.quantity * p.current_price) as total
            FROM positions p
            JOIN stocks s ON p.symbol = s.symbol
        """)
        row = await cursor.fetchone()

        if row and row[3] > 0:
            total = row[3]
            display.update_allocation(
                eu=row[0] / total,
                asia=row[1] / total,
                us=row[2] / total
            )
            display.set_system_status("ok")
            return True

    except Exception as e:
        logger.error(f"Failed to update LED display: {e}")
        display.set_system_status("error")

    return False


async def update_balance_display(db) -> bool:
    """
    Update LED display with current portfolio balance in abacus style.

    Called after sync operations to show total portfolio value.
    """
    display = get_led_display()

    if not display.is_connected:
        return False

    try:
        # Get total portfolio value in EUR
        cursor = await db.execute("""
            SELECT SUM(market_value_eur) as total
            FROM positions
        """)
        row = await cursor.fetchone()

        if row and row[0]:
            display.show_balance(row[0])
            return True

    except Exception as e:
        logger.error(f"Failed to update balance display: {e}")

    return False


@contextmanager
def led_api_call():
    """
    Context manager to show API call animation during external API requests.

    Usage:
        with led_api_call():
            response = requests.get(url)
    """
    display = get_led_display()
    previous_state = display.get_state()

    if display.is_connected:
        display.show_api_call()

    try:
        yield
    finally:
        if display.is_connected and previous_state:
            # Restore previous state
            if previous_state.mode == DisplayMode.HEALTH:
                display.update_allocation(
                    previous_state.geo_eu,
                    previous_state.geo_asia,
                    previous_state.geo_us
                )
            elif previous_state.mode == DisplayMode.BALANCE:
                # Re-show balance (value not stored in state, will need to refresh)
                display.set_mode(DisplayMode.IDLE)
            else:
                display.set_mode(DisplayMode.IDLE)


@contextmanager
def led_syncing():
    """
    Context manager to show syncing animation during sync operations.

    Usage:
        with led_syncing():
            await sync_portfolio()
    """
    display = get_led_display()

    if display.is_connected:
        display.show_syncing()
        display.set_system_status("syncing")

    try:
        yield
    finally:
        if display.is_connected:
            display.set_system_status("ok")
