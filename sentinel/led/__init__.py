"""
LED visualization package for Arduino UNO Q orbital display.

Usage:
    from sentinel.led import LEDController

    led = LEDController()
    await led.start()
"""

from sentinel.led.controller import LEDController

__all__ = ['LEDController']
