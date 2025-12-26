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
Trading API (FastAPI) → Native Python Script (systemd) → Serial Port → STM32 MCU → LED Matrix
```

1. Native Python script (`scripts/led_display_native.py`) runs as a systemd service
2. Polls `/api/status/display/text` from the trading API every 2 seconds
3. Sends commands to MCU via serial port using simple text protocol:
   - `TEXT:<text>\n` - Set display text
   - `SPEED:<value>\n` - Set scroll speed
   - `BRIGHTNESS:<value>\n` - Set brightness
4. MCU receives commands and renders scrolling text using native Font_5x7

## Display Priority System (3-Pool)

The display uses a 3-pool priority system:

1. **Error Pool** (highest priority): Error messages like "BACKUP FAILED", "ORDER PLACEMENT FAILED"
2. **Processing Pool** (medium priority): Activity messages like "SYNCING...", "BUY AAPL €500"
3. **Next Actions Pool** (lowest priority, default): Portfolio value, cash balance, recommendations

The display automatically shows the highest priority non-empty text.

## Files

- `sketch/sketch.ino` - STM32 sketch for LED matrix control (uses serial communication)
- `sketch/sketch.yaml` - Sketch configuration (Arduino CLI)
- `deploy/auto-deploy.sh` - Auto-deployment script (handles sketch compilation)

**Note**: The Python script (`scripts/led_display_native.py`) is in the main repository, not in `arduino-app/`.

---

## Setup on New Board

The LED display is automatically set up by the main deployment script:

```bash
# Run main setup script (installs both main app and LED display)
sudo /home/arduino/repos/autoTrader/deploy/setup.sh
```

This will:
1. Install the LED display systemd service
2. Compile and upload the Arduino sketch to the MCU
3. Start the LED display service

### Manual Sketch Compilation

If you need to compile and upload the sketch manually:

```bash
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

### Service Management

```bash
# Check status
sudo systemctl status led-display

# View logs
sudo journalctl -u led-display -f

# Restart
sudo systemctl restart led-display
```

---

## Auto-Deployment

Once set up, the board automatically:
1. Checks GitHub for updates every 5 minutes
2. If changes detected, pulls and syncs files
3. If sketch files changed, compiles and uploads sketch automatically
4. Restarts services as needed

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

### Check Deploy Logs

```bash
ssh arduino@<IP> "cat /home/arduino/logs/auto-deploy.log"
```

### Force Immediate Deploy

```bash
ssh arduino@<IP> "/home/arduino/bin/auto-deploy.sh"
```

## Requirements

- Arduino Uno Q
- Arduino CLI installed (automatically installed by setup script)
- Arduino Trader API running on port 8000
- Serial port `/dev/ttyACM0` available for MCU communication
- Network access to GitHub (for auto-deploy)
