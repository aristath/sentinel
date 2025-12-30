# Arduino Trader LED Display

Displays portfolio information on the Arduino Uno Q's 8x13 LED matrix using a scrolling ticker.

## Display Layout

The display uses native ArduinoGraphics Font_5x7 that scrolls right-to-left across the 8x13 matrix. The ticker shows:
- Portfolio value (e.g., "Portfolio EUR12,345")
- Cash balance (e.g., "CASH EUR675")
- Trading recommendations (e.g., "BUY XIAO EUR855", "SELL ABC EUR200")

When no ticker text is available, the display remains blank.

## How It Works

```
Trading API (FastAPI) → /api/status/led/display → Docker Python App → Router Bridge → STM32 MCU → LED Matrix
```

1. Docker Python app (`arduino-app/python/main.py`) runs via Arduino App Framework
2. Polls `/api/status/led/display` endpoint every 2 seconds
3. Receives display state with priority: error_message > activity_message > ticker_text
4. Calls MCU functions via Router Bridge (msgpack RPC over Unix socket):
   - `scrollText(text, speed)` - Scroll text across LED matrix using native Font_5x7
   - `setRGB3(r, g, b)` - Set RGB LED 3 color
   - `setRGB4(r, g, b)` - Set RGB LED 4 color
5. MCU receives commands via Router Bridge and renders scrolling text using native Font_5x7

## Display Priority System (3-Pool)

The display uses a 3-pool priority system:

1. **Error Pool** (highest priority): Error messages like "BACKUP FAILED", "ORDER PLACEMENT FAILED"
2. **Processing Pool** (medium priority): Activity messages like "SYNCING...", "BUY AAPL €500"
3. **Next Actions Pool** (lowest priority, default): Portfolio value, cash balance, recommendations

The display automatically shows the highest priority non-empty text.

## Files

- `python/main.py` - Docker Python app for LED display (Arduino App Framework)
- `app.yaml` - Arduino App configuration
- `sketch/sketch.ino` - STM32 sketch for LED matrix control (uses Router Bridge)
- `sketch/sketch.yaml` - Sketch configuration (Arduino CLI)
- `deploy/auto-deploy.sh` - Auto-deployment script (handles sketch compilation)

---

## Setup on New Board

The LED display is automatically set up by the main deployment script:

```bash
# Run main setup script (installs both main app and LED display)
sudo /home/arduino/repos/autoTrader/deploy/setup.sh
```

This will:
1. Deploy the Docker LED display app via Arduino App Framework
2. Compile and upload the Arduino sketch to the MCU
3. The Docker app automatically starts via Arduino App Framework

### Manual Sketch Compilation

If you need to compile and upload the sketch manually:

```bash
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

### Docker App Management

The LED display runs as a Docker app managed by Arduino App Framework. The app automatically starts when the board boots and restarts if it crashes.

To check the app status, use the Arduino App Framework tools or check Docker containers.

---

## Auto-Deployment

The system uses Python-based deployment infrastructure for reliable automatic updates:

Once set up, the board automatically:
1. Checks GitHub for updates every 5 minutes (configurable)
2. If changes detected, pulls and syncs files using staged deployment
3. If sketch files changed, compiles and uploads sketch automatically
4. Restarts services and verifies health checks
5. File-based locking prevents concurrent deployments

### Development Workflow

```bash
# Edit sketch locally
vim arduino-app/sketch/sketch.ino

# Commit and push
git add .
git commit -m "Update sketch"
git push

# Wait up to 5 minutes - Arduino deploys automatically
# The sketch will be compiled and uploaded, LED display service restarted
```

### Check Deployment Status

```bash
# Via API (recommended)
ssh arduino@<IP> "curl http://localhost:8000/api/status/deploy/status"

# Check application logs
ssh arduino@<IP> "sudo journalctl -u arduino-trader -f"
```

### Force Immediate Deploy

```bash
# Via API (recommended)
ssh arduino@<IP> "curl -X POST http://localhost:8000/api/status/deploy/trigger"
```

## Requirements

- Arduino Uno Q
- Arduino CLI installed (automatically installed by setup script)
- Arduino Trader API running on port 8000
- `arduino-router` service running (provides Router Bridge communication)
- Network access to GitHub (for auto-deploy)

**Note**: The display uses polling (every 2 seconds) to fetch display state from `/api/status/led/display`. The Docker app runs continuously and updates the display whenever the API state changes.
