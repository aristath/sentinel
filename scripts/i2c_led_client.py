"""I2C client for communicating with Arduino Uno Q LED matrix MCU.

This module provides functions to send commands to the MCU via I2C,
bypassing Docker and Router Bridge.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# I2C configuration
I2C_BUS = 0  # I2C bus number (bus 0 on Arduino Uno Q)
I2C_SLAVE_ADDR = 0x08  # MCU I2C slave address

# Command codes (must match sketch.ino)
CMD_SCROLL_TEXT = 0x01
CMD_DRAW = 0x02
CMD_SET_RGB3 = 0x03
CMD_SET_RGB4 = 0x04
CMD_PRINT_TEXT = 0x05

# Global I2C bus instance (lazy initialization)
_i2c_bus: Optional[object] = None


def _get_i2c_bus():
    """Get or create I2C bus instance."""
    global _i2c_bus
    if _i2c_bus is None:
        try:
            from smbus2 import SMBus

            _i2c_bus = SMBus(I2C_BUS)
            logger.debug(f"I2C bus {I2C_BUS} opened successfully")
        except ImportError:
            logger.error("smbus2 module not available. Install with: pip install smbus2")
            raise
        except Exception as e:
            logger.error(f"Failed to open I2C bus {I2C_BUS}: {e}")
            raise
    return _i2c_bus


def scroll_text(text: str, speed: int = 50) -> bool:
    """Scroll text across LED matrix.

    Args:
        text: Text to scroll (ASCII only, Euro symbol will be replaced)
        speed: Milliseconds per scroll step (lower = faster)

    Returns:
        True if successful, False otherwise
    """
    if not text:
        return True

    try:
        bus = _get_i2c_bus()
        # Replace Euro symbol with EUR (Font_5x7 only has ASCII 32-126)
        text = text.replace("€", "EUR")
        text_bytes = text.encode("ascii", errors="ignore")
        text_len = min(len(text_bytes), 255)

        # Format: [CMD] [len_byte] [text_bytes...] [speed_low] [speed_high]
        # Note: Use i2c_rdwr for raw I2C write (Arduino Wire doesn't use register addresses)
        data = [CMD_SCROLL_TEXT, text_len] + list(text_bytes[:text_len])
        # Add speed (2 bytes, little-endian)
        data.append(speed & 0xFF)
        data.append((speed >> 8) & 0xFF)

        from smbus2 import i2c_msg

        write_msg = i2c_msg.write(I2C_SLAVE_ADDR, data)
        bus.i2c_rdwr(write_msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send scroll_text command: {e}")
        return False


def set_rgb3(r: int, g: int, b: int) -> bool:
    """Set RGB LED 3 color.

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    try:
        bus = _get_i2c_bus()
        # Format: [CMD] [R] [G] [B]
        data = [CMD_SET_RGB3, r & 0xFF, g & 0xFF, b & 0xFF]
        from smbus2 import i2c_msg

        write_msg = i2c_msg.write(I2C_SLAVE_ADDR, data)
        bus.i2c_rdwr(write_msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send set_rgb3 command: {e}")
        return False


def set_rgb4(r: int, g: int, b: int) -> bool:
    """Set RGB LED 4 color.

    Args:
        r: Red value (0-255, 0 = off, >0 = on)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True if successful, False otherwise
    """
    try:
        bus = _get_i2c_bus()
        # Format: [CMD] [R] [G] [B]
        data = [CMD_SET_RGB4, r & 0xFF, g & 0xFF, b & 0xFF]
        from smbus2 import i2c_msg

        write_msg = i2c_msg.write(I2C_SLAVE_ADDR, data)
        bus.i2c_rdwr(write_msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send set_rgb4 command: {e}")
        return False


def draw_frame(frame_data: bytes) -> bool:
    """Draw frame to LED matrix.

    Args:
        frame_data: 104 bytes (8x13) of frame data

    Returns:
        True if successful, False otherwise
    """
    if len(frame_data) != 104:
        logger.error(f"Frame data must be exactly 104 bytes, got {len(frame_data)}")
        return False

    try:
        bus = _get_i2c_bus()
        # Format: [CMD] [104 bytes of frame data]
        data = [CMD_DRAW] + list(frame_data)
        from smbus2 import i2c_msg

        write_msg = i2c_msg.write(I2C_SLAVE_ADDR, data)
        bus.i2c_rdwr(write_msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send draw_frame command: {e}")
        return False


def print_text(text: str, x: int = 0, y: int = 1) -> bool:
    """Display static text at position.

    Args:
        text: Text to display (ASCII only)
        x: X position
        y: Y position

    Returns:
        True if successful, False otherwise
    """
    if not text:
        return True

    try:
        bus = _get_i2c_bus()
        # Replace Euro symbol with EUR
        text = text.replace("€", "EUR")
        text_bytes = text.encode("ascii", errors="ignore")
        text_len = min(len(text_bytes), 255)

        # Format: [CMD] [len_byte] [text_bytes...] [x] [y]
        data = [CMD_PRINT_TEXT, text_len] + list(text_bytes[:text_len])
        data.append(x & 0xFF)
        data.append(y & 0xFF)

        from smbus2 import i2c_msg

        write_msg = i2c_msg.write(I2C_SLAVE_ADDR, data)
        bus.i2c_rdwr(write_msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send print_text command: {e}")
        return False
