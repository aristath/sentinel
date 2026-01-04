# Arduino Trader Deployment Scripts

Quick and easy deployment and management scripts for Arduino Uno Q.

## Configuration

Set environment variables to customize (optional):

```bash
export ARDUINO_HOST=192.168.1.11        # Arduino IP address
export ARDUINO_USER=arduino             # SSH user
export ARDUINO_DEPLOY_PATH=/opt/arduino-trader  # Deployment path
```

Or edit `config.sh` to change defaults.

## Quick Start

### Full Deployment (Most Common)

Build, deploy, and restart everything:

```bash
./scripts/deploy-full.sh
```

### Individual Operations

**Build for ARM64:**
```bash
./scripts/build.sh
```

**Deploy to Arduino:**
```bash
./scripts/deploy.sh
```

**Restart services:**
```bash
./scripts/restart.sh              # Restart all
./scripts/restart.sh trader-go    # Restart trader-go only
```

**Check status:**
```bash
./scripts/status.sh
```

**View logs:**
```bash
./scripts/logs.sh trader-go       # Last 50 lines
./scripts/logs.sh trader-go 50 -f # Follow logs
```

## Scripts Reference

See individual script files for detailed documentation.
