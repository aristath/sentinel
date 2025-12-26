# Arduino Trader LED Display
# Simple text display - fetches current text from API and scrolls it

from arduino.app_utils import App, Bridge, Logger
import requests
import time

logger = Logger("trader-display")
API_URL = "http://172.17.0.1:8000"
_session = requests.Session()
_last_text = ""
_last_speed = 0
_last_brightness = 0


def set_text(text: str) -> bool:
    """Send text to MCU for scrolling."""
    try:
        Bridge.call("setText", text, timeout=5)
        return True
    except Exception as e:
        logger.debug(f"setText failed: {e}")
        return False


def set_speed(speed: int) -> bool:
    """Set scroll speed on MCU."""
    try:
        Bridge.call("setSpeed", speed, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setSpeed failed: {e}")
        return False


def set_brightness(brightness: int) -> bool:
    """Set LED brightness on MCU."""
    try:
        Bridge.call("setBrightness", brightness, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"setBrightness failed: {e}")
        return False


def loop():
    """Main loop - fetch display text from API, update MCU if changed."""
    global _last_text, _last_speed, _last_brightness

    try:
        resp = _session.get(f"{API_URL}/api/status/display/text", timeout=2)
        if resp.status_code != 200:
            set_text("API OFFLINE")
            time.sleep(5)
            return

        data = resp.json()
        text = data.get("text", "")
        speed = data.get("speed", 50)
        brightness = data.get("brightness", 150)

        # Update settings if changed
        if speed != _last_speed:
            set_speed(speed)
            _last_speed = speed
        if brightness != _last_brightness:
            set_brightness(brightness)
            _last_brightness = brightness

        # Update text if changed
        if text != _last_text:
            set_text(text)
            _last_text = text

        time.sleep(2)  # Poll every 2 seconds

    except Exception as e:
        logger.error(f"Loop error: {e}")
        time.sleep(5)


logger.info("LED Display starting...")
App.run(user_loop=loop)
