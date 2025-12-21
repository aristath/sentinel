# Arduino Trader LED Display

Displays portfolio value on the Arduino Uno Q's 8x13 LED matrix.

## Display Layout

```
Rows 0-4: Big digits showing thousands (e.g., "20" for €20K)
          + 1-column progress bar (col 12) showing €0-999 remainder
Row 5:    Empty separator
Row 6:    Empty
Row 7:    Heartbeat indicator (col 0) - blinks every 2 seconds
```

**Progress bar:** Each pixel = €200, with partial brightness for smooth transitions.

## How It Works

```
Trading API (FastAPI) → Python Script → Router Bridge → STM32 MCU → LED Matrix
```

1. Python script fetches `/api/status/led/display` from the trading API
2. Creates frame with big digits + progress bar
3. Sends frame data to STM32 via Router Bridge
4. STM32 renders the frame on the LED matrix

## Display Modes

- **balance**: Big digits + progress bar (default)
- **syncing**: Wave animation during data sync
- **api_call**: Wave animation during API calls
- **no_wifi**: Scrolling "NO WIFI" text
- **error**: X pattern when API unreachable

## Files

- `python/main.py` - Fetches API data and generates LED frames
- `sketch/sketch.ino` - STM32 sketch for LED matrix control
- `app.yaml` - App configuration
- `deploy/` - Auto-deployment scripts

---

## Setup on New Board

### Quick Setup (Automated)

SSH into the Arduino and run:

```bash
# Download and run setup script
curl -s https://raw.githubusercontent.com/aristath/autoTrader/main/arduino-app/deploy/setup.sh | bash
```

Or manually:

```bash
# Clone repo
mkdir -p /home/arduino/repos
cd /home/arduino/repos
git clone https://github.com/aristath/autoTrader.git

# Run setup
bash /home/arduino/repos/autoTrader/arduino-app/deploy/setup.sh
```

### What Setup Does

1. Creates required directories
2. Clones the GitHub repo
3. Copies deploy script to `/home/arduino/bin/`
4. Syncs app files to `/home/arduino/ArduinoApps/trader-display/`
5. Sets up cron job to check for updates every 5 minutes
6. Starts the app

### Manual Setup

If you prefer to set up manually:

```bash
# 1. Create directories
mkdir -p /home/arduino/repos /home/arduino/bin /home/arduino/logs

# 2. Clone repo
cd /home/arduino/repos
git clone https://github.com/aristath/autoTrader.git

# 3. Copy deploy script
cp /home/arduino/repos/autoTrader/arduino-app/deploy/auto-deploy.sh /home/arduino/bin/
chmod +x /home/arduino/bin/auto-deploy.sh

# 4. Sync app files
rsync -av --delete /home/arduino/repos/autoTrader/arduino-app/ /home/arduino/ArduinoApps/trader-display/

# 5. Set up cron (every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/arduino/bin/auto-deploy.sh") | crontab -

# 6. Start app
arduino-app-cli app restart user:trader-display
```

---

## Auto-Deployment

Once set up, the board automatically:
1. Checks GitHub for updates every 5 minutes
2. If changes detected, pulls and syncs files
3. Restarts the app

### Development Workflow

```bash
# Edit code locally
vim arduino-app/python/main.py

# Commit and push
git add .
git commit -m "Update display"
git push

# Wait up to 5 minutes - Arduino deploys automatically
```

### Check Deploy Logs

```bash
ssh arduino@<IP> "cat /home/arduino/logs/auto-deploy.log"
```

### Force Immediate Deploy

```bash
ssh arduino@<IP> "/home/arduino/bin/auto-deploy.sh"
```

---

## Commands

```bash
# View logs
arduino-app-cli app logs user:trader-display

# Restart
arduino-app-cli app restart user:trader-display

# Stop
arduino-app-cli app stop user:trader-display
```

## Requirements

- Arduino Uno Q with Arduino App framework
- Arduino Trader API running on port 8000
- Network access to GitHub (for auto-deploy)
