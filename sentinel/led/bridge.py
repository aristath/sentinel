"""
MCU communication bridge for LED trade display.

Wraps the Arduino UNO Q Bridge API to send trade text to the MCU.
The MCU displays scrolling text one trade at a time.
"""

import logging

logger = logging.getLogger(__name__)


class LEDBridge:
    """Communication bridge to Arduino UNO Q MCU.

    Sends trade text via Bridge RPC. The MCU scrolls each
    trade message one at a time.
    """

    def __init__(self):
        self._connected = False
        self._bridge = None

    async def connect(self) -> bool:
        """Attempt to connect to Arduino Bridge.

        Returns:
            True if connection successful, False otherwise.
            Returns False gracefully if not running on Arduino UNO Q.
        """
        try:
            from arduino.app_utils import Bridge

            self._bridge = Bridge
            self._connected = True
            logger.info("LED Bridge connected to Arduino MCU")
            return True
        except ImportError:
            logger.debug("Arduino Bridge not available (not on Arduino UNO Q)")
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Arduino Bridge: {e}")
            return False

    @property
    def connected(self) -> bool:
        """Check if bridge is connected."""
        return self._connected

    async def set_text(self, text: str) -> bool:
        """Send text to display on LED matrix.

        The MCU will scroll this text from right to left.
        This call blocks until the scroll completes.

        Args:
            text: Text to display (e.g., "SELL $1,874.62 (51%) BYD.285.AS")

        Returns:
            True if text sent successfully, False otherwise.
        """
        if not self._connected or self._bridge is None:
            return False

        try:
            # Timeout needs to be long enough for scroll to complete
            # Scroll takes ~5-7 seconds per message
            self._bridge.call("setText", text, timeout=15)
            logger.debug(f"Sent text to MCU: {text}")
            return True
        except Exception as e:
            logger.error(f"Failed to send text to MCU: {e}")
            return False

    async def clear(self) -> bool:
        """Clear the LED display.

        Returns:
            True if command sent successfully, False otherwise.
        """
        if not self._connected or self._bridge is None:
            return False

        try:
            self._bridge.call("clear", timeout=2)
            logger.debug("Cleared LED display")
            return True
        except Exception as e:
            logger.error(f"Failed to clear display: {e}")
            return False
