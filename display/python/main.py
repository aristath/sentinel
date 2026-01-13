"""
Sentinel LED Display - Python App

Arduino App Lab application for controlling the LED display on Arduino Uno Q.
Exposes REST API endpoints via Web UI Brick for external communication.

The MCU handles all rendering and scrolling - Python just passes commands.

Endpoints:
- POST /text - Set scrolling text (MCU handles rendering)
- POST /led3 - Set RGB LED 3 color (sync indicator)
- POST /led4 - Set RGB LED 4 color (processing indicator)
- POST /clear - Clear the LED matrix
- POST /pixels - Set pixel count (for system stats mode)
- GET /health - Health check endpoint
"""

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from fastapi import Request

# Initialize Web UI Brick for REST API
ui = WebUI()


async def handle_set_text(request: Request):
    """Set scrolling text - MCU handles rendering and scrolling."""
    data = await request.json()
    text = str(data.get("text", ""))
    # MCU handles all rendering - just pass the text
    Bridge.call("setText", text)
    return {"status": "ok", "text": text}


async def handle_set_led3(request: Request):
    """Set RGB LED 3 color (sync indicator)."""
    data = await request.json()
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB3", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_set_led4(request: Request):
    """Set RGB LED 4 color (processing indicator)."""
    data = await request.json()
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB4", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_clear_matrix(request: Request):
    """Clear the LED matrix."""
    Bridge.call("clearMatrix")
    return {"status": "ok"}


async def handle_set_pixels(request: Request):
    """Set pixel count for stats visualization."""
    data = await request.json()
    count = max(0, min(104, int(data.get("count", 0))))
    Bridge.call("setPixelCount", count)
    return {"status": "ok", "count": count}


def handle_health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "sentinel-display"}


# Register API endpoints
ui.expose_api("POST", "/text", handle_set_text)
ui.expose_api("POST", "/led3", handle_set_led3)
ui.expose_api("POST", "/led4", handle_set_led4)
ui.expose_api("POST", "/clear", handle_clear_matrix)
ui.expose_api("POST", "/pixels", handle_set_pixels)
ui.expose_api("GET", "/health", handle_health)


if __name__ == "__main__":
    App.run()
