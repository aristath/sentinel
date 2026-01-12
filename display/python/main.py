"""
Sentinel LED Display - Python App

Arduino App Lab application for controlling the LED display on Arduino Uno Q.
Exposes REST API endpoints via Web UI Brick for external communication.

Following Arduino Uno Q documentation:
https://docs.arduino.cc/tutorials/uno-q/user-manual/

Endpoints:
- POST /text - Scroll text across LED matrix
- POST /led3 - Set RGB LED 3 color (sync indicator)
- POST /led4 - Set RGB LED 4 color (processing indicator)
- POST /clear - Clear the LED matrix
- POST /brightness - Set matrix brightness
- POST /char - Display a single character
- POST /pixels - Set pixel count (for system stats mode)
- GET /health - Health check endpoint
"""

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from fastapi import Request

# Initialize Web UI Brick for REST API
ui = WebUI()


async def handle_set_text(request: Request):
    data = await request.json()
    text = data.get("text", "")
    speed = int(data.get("speed", 50))
    Bridge.call("scrollText", text, speed)
    return {"status": "ok", "text": text, "speed": speed}


async def handle_set_led3(request: Request):
    data = await request.json()
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB3", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_set_led4(request: Request):
    data = await request.json()
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB4", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_clear_matrix(request: Request):
    Bridge.call("clearMatrix")
    return {"status": "ok"}


async def handle_set_brightness(request: Request):
    data = await request.json()
    level = max(0, min(255, int(data.get("level", 128))))
    Bridge.call("setMatrixBrightness", level)
    return {"status": "ok", "level": level}


async def handle_display_char(request: Request):
    data = await request.json()
    char = str(data.get("char", " "))[:1] or " "
    Bridge.call("displayChar", char)
    return {"status": "ok", "char": char}


async def handle_set_pixels(request: Request):
    data = await request.json()
    count = max(0, min(104, int(data.get("count", 0))))
    Bridge.call("setPixelCount", count)
    return {"status": "ok", "count": count}


def handle_health():
    return {"status": "healthy", "service": "sentinel-display"}


ui.expose_api("POST", "/text", handle_set_text)
ui.expose_api("POST", "/led3", handle_set_led3)
ui.expose_api("POST", "/led4", handle_set_led4)
ui.expose_api("POST", "/clear", handle_clear_matrix)
ui.expose_api("POST", "/brightness", handle_set_brightness)
ui.expose_api("POST", "/char", handle_display_char)
ui.expose_api("POST", "/pixels", handle_set_pixels)
ui.expose_api("GET", "/health", handle_health)


if __name__ == "__main__":
    App.run()
