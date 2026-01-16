"""
Sentinel LED Display - Python App

Arduino App Lab application for controlling the LED display on Arduino Uno Q.
This application runs on the Arduino Uno Q and exposes REST API endpoints via
Web UI Brick for communication with the main Sentinel Go application.

Architecture:
- The MCU (Arduino sketch) handles all rendering, scrolling, and LED control
- Python acts as a thin API layer that translates HTTP requests to MCU commands
- The main Sentinel application sends commands to this Python app via HTTP
- The Python app uses the Arduino Bridge to communicate with the MCU sketch

Endpoints:
- POST /text - Set scrolling text (MCU handles rendering and scrolling)
- POST /led3 - Set RGB LED 3 color (service health/sync indicator)
- POST /led4 - Set RGB LED 4 color (planner activity/processing indicator)
- POST /clear - Clear the LED matrix display
- POST /pixels - Set pixel count (for system stats visualization mode)
- POST /portfolio-health - Set portfolio health data (MCU handles animation)
- GET /health - Health check endpoint for monitoring

The display shows:
- LED Matrix: Scrolling text, portfolio health visualization, system stats
- RGB LED 3: Service health indicator (green=healthy, red=unhealthy, off=stopped)
- RGB LED 4: Planner activity indicator (blue=active, off=idle)
"""

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from fastapi import Request

# Initialize Web UI Brick for REST API
# The WebUI brick provides HTTP endpoints that can be called from external services.
# It uses FastAPI under the hood for request handling.
ui = WebUI()


async def handle_set_text(request: Request):
    """
    Set scrolling text on the LED matrix display.
    
    The MCU (Arduino sketch) handles all rendering and scrolling logic.
    This function simply extracts the text from the request and passes it
    to the MCU via the Bridge.
    
    Args:
        request: FastAPI request object containing JSON with "text" field
        
    Returns:
        dict: Status response with the text that was set
    """
    data = await request.json()
    text = str(data.get("text", ""))
    # MCU handles all rendering - just pass the text
    Bridge.call("setText", text)
    return {"status": "ok", "text": text}


async def handle_set_led3(request: Request):
    """
    Set RGB LED 3 color (service health/sync indicator).
    
    LED 3 is used to indicate the health status of the main Sentinel service.
    Colors typically used:
    - Green (0, 255, 0): Service is healthy and running
    - Red (255, 0, 0): Service is unhealthy or has errors
    - Off (0, 0, 0): Service is stopped
    
    Args:
        request: FastAPI request object containing JSON with "r", "g", "b" fields (0-255)
        
    Returns:
        dict: Status response with the RGB values that were set
    """
    data = await request.json()
    # Clamp RGB values to valid range (0-255) to prevent invalid values
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB3", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_set_led4(request: Request):
    """
    Set RGB LED 4 color (planner activity/processing indicator).
    
    LED 4 is used to indicate when the planning system is actively generating
    recommendations or evaluating trade sequences.
    Colors typically used:
    - Blue (0, 0, 255): Planner is actively processing
    - Off (0, 0, 0): Planner is idle
    
    Args:
        request: FastAPI request object containing JSON with "r", "g", "b" fields (0-255)
        
    Returns:
        dict: Status response with the RGB values that were set
    """
    data = await request.json()
    # Clamp RGB values to valid range (0-255) to prevent invalid values
    r = max(0, min(255, int(data.get("r", 0))))
    g = max(0, min(255, int(data.get("g", 0))))
    b = max(0, min(255, int(data.get("b", 0))))
    Bridge.call("setRGB4", r, g, b)
    return {"status": "ok", "r": r, "g": g, "b": b}


async def handle_clear_matrix(request: Request):
    """
    Clear the LED matrix display.
    
    This command turns off all pixels on the LED matrix, effectively
    clearing any text or graphics currently displayed.
    
    Args:
        request: FastAPI request object (no body required)
        
    Returns:
        dict: Status response indicating success
    """
    Bridge.call("clearMatrix")
    return {"status": "ok"}


async def handle_set_pixels(request: Request):
    """
    Set pixel count for system stats visualization mode.
    
    This is used to display system statistics as a bar graph on the LED matrix.
    The pixel count represents the value being visualized (e.g., portfolio value,
    number of positions, etc.). The MCU handles the actual rendering.
    
    Args:
        request: FastAPI request object containing JSON with "count" field (0-104)
                 The maximum value (104) corresponds to the number of pixels on the matrix
        
    Returns:
        dict: Status response with the pixel count that was set
    """
    data = await request.json()
    # Clamp count to valid range (0-104) - 104 is the total number of pixels on the matrix
    count = max(0, min(104, int(data.get("count", 0))))
    Bridge.call("setPixelCount", count)
    return {"status": "ok", "count": count}


async def handle_set_portfolio_health(request: Request):
    """
    Update portfolio health scores for securities.
    
    This endpoint receives portfolio health data from the main Sentinel application
    and passes it to the MCU for visualization. The MCU handles the animation
    and rendering of health scores for each security.
    
    The data structure expected:
    {
        "securities": [
            {"symbol": "AAPL", "health": 85},
            {"symbol": "MSFT", "health": 92},
            ...
        ]
    }
    
    Args:
        request: FastAPI request object containing JSON with portfolio health data
        
    Returns:
        dict: Status response with the number of securities processed
    """
    data = await request.json()
    
    # Convert to JSON string for Arduino
    # The Bridge.call() method requires string parameters, so we serialize
    # the JSON data to a string that the MCU can parse
    import json
    json_str = json.dumps(data)
    
    # Send to MCU via Bridge
    # The MCU will parse the JSON and handle the visualization
    Bridge.call("setPortfolioHealth", json_str)
    
    securities = data.get("securities", [])
    return {"status": "ok", "count": len(securities)}


def handle_health():
    """
    Health check endpoint for monitoring and service discovery.
    
    This endpoint is used by monitoring systems to verify that the display
    service is running and responsive. It does not check MCU connectivity,
    only that the Python application is running.
    
    Returns:
        dict: Health status response indicating the service is healthy
    """
    return {"status": "healthy", "service": "sentinel-display"}


# Register API endpoints with the WebUI brick
# Each endpoint is exposed via HTTP and can be called from external services.
# The WebUI brick handles routing, request parsing, and response formatting.
ui.expose_api("POST", "/text", handle_set_text)
ui.expose_api("POST", "/led3", handle_set_led3)
ui.expose_api("POST", "/led4", handle_set_led4)
ui.expose_api("POST", "/clear", handle_clear_matrix)
ui.expose_api("POST", "/pixels", handle_set_pixels)
ui.expose_api("POST", "/portfolio-health", handle_set_portfolio_health)
ui.expose_api("GET", "/health", handle_health)


if __name__ == "__main__":
    # Start the Arduino App Lab application
    # This initializes the WebUI brick, starts the HTTP server, and begins
    # listening for requests. The application runs until stopped.
    App.run()
