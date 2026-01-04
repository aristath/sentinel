# Arduino Trader - Deployment Guide

This guide walks you through deploying the Arduino Trader application to your Arduino Uno Q device.

## Prerequisites

1. **Arduino Uno Q device** powered on and accessible on your network
2. **SSH access** to the Arduino device (user: `arduino`, default IP: `192.168.1.11`)
3. **Docker** installed on the Arduino device (for microservices)
4. **Go 1.22+** installed on your development machine (for building)
5. **Tradernet API credentials** configured

## Quick Start

For the fastest deployment:

```bash
# From the project root
./scripts/deploy-full.sh
```

This will:
1. Build Go binaries for ARM64
2. Deploy binaries to Arduino via SSH
3. Restart services

## Step-by-Step Deployment

### Step 1: Configure Connection

Edit `scripts/config.sh` or set environment variables:

```bash
export ARDUINO_HOST=192.168.1.11    # Your Arduino IP
export ARDUINO_USER=arduino          # SSH user (default)
export ARDUINO_DEPLOY_PATH=/opt/arduino-trader  # Deployment path
```

**Verify SSH connection:**
```bash
ssh arduino@192.168.1.11 "echo 'Connection successful'"
```

### Step 2: Initial Setup on Arduino (First Time Only)

**On the Arduino device**, perform initial setup:

```bash
# SSH into Arduino
ssh arduino@192.168.1.11

# Create deployment directory
sudo mkdir -p /opt/arduino-trader
sudo chown arduino:arduino /opt/arduino-trader

# Create data directory (adjust path as needed)
sudo mkdir -p /home/arduino/arduino-trader/data
sudo chown arduino:arduino /home/arduino/arduino-trader/data

# Verify Docker is installed and running
docker --version
sudo systemctl status docker
```

### Step 3: Setup Systemd Services (First Time Only)

**On the Arduino device**, install systemd service files:

#### 3a. Create trader.service

```bash
sudo nano /etc/systemd/system/trader.service
```

Paste this content (adjust paths as needed):

```ini
[Unit]
Description=Arduino Trader Go Service
Documentation=https://github.com/aristath/arduino-trader
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=arduino
Group=arduino
WorkingDirectory=/opt/arduino-trader
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=-/opt/arduino-trader/.env
ExecStart=/opt/arduino-trader/trader
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=trader

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

# Resource limits (adjust as needed)
MemoryMax=2G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
```

#### 3b. Create display-bridge.service

```bash
sudo nano /etc/systemd/system/display-bridge.service
```

Copy the content from `display/bridge/display-bridge.service` or create it manually.

#### 3c. Reload systemd and enable services

```bash
sudo systemctl daemon-reload
sudo systemctl enable trader
sudo systemctl enable display-bridge
```

### Step 4: Setup Microservices (Docker)

**On the Arduino device**, set up microservices:

#### Option A: Using Docker Compose (Recommended)

Create `/opt/arduino-trader/docker-compose.yml`:

```yaml
version: '3.8'

services:
  pypfopt:
    build:
      context: /opt/arduino-trader/microservices/pypfopt
      dockerfile: Dockerfile
    container_name: pypfopt-service
    ports:
      - "9001:9001"
    environment:
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  tradernet:
    build:
      context: /opt/arduino-trader/microservices/tradernet
      dockerfile: Dockerfile
    container_name: tradernet-service
    ports:
      - "9002:9002"
    environment:
      - PORT=9002
      - LOG_LEVEL=INFO
      - TRADERNET_API_KEY=${TRADERNET_API_KEY}
      - TRADERNET_API_SECRET=${TRADERNET_API_SECRET}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:9002/health').raise_for_status()"]
      interval: 30s
      timeout: 3s
      retries: 3
```

Create `/opt/arduino-trader/.env` for Docker Compose:

```bash
TRADERNET_API_KEY=your_api_key_here
TRADERNET_API_SECRET=your_api_secret_here
```

**Deploy microservices code:**
```bash
# From your development machine
scp -r microservices arduino@192.168.1.11:/opt/arduino-trader/
```

**Build and start microservices:**
```bash
# On Arduino device
cd /opt/arduino-trader
docker-compose build
docker-compose up -d
docker-compose ps  # Verify services are running
```

#### Option B: Individual Docker Compose Files

Deploy each microservice separately:

```bash
# Deploy microservices
scp -r microservices/pypfopt arduino@192.168.1.11:/opt/arduino-trader/microservices/
scp -r microservices/tradernet arduino@192.168.1.11:/opt/arduino-trader/microservices/

# On Arduino, start each service
cd /opt/arduino-trader/microservices/pypfopt
docker-compose up -d

cd /opt/arduino-trader/microservices/tradernet
docker-compose up -d
```

### Step 5: Configure Environment Variables

**On the Arduino device**, create `/opt/arduino-trader/.env`:

```bash
# Database paths
STATE_DB_PATH=/home/arduino/arduino-trader/data/state.db
PORTFOLIO_DB_PATH=/home/arduino/arduino-trader/data/portfolio.db
LEDGER_DB_PATH=/home/arduino/arduino-trader/data/ledger.db
SATELLITES_DB_PATH=/home/arduino/arduino-trader/data/satellites.db

# Microservice URLs
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API (if not using docker-compose .env)
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Server
PORT=8080
LOG_LEVEL=info

# Background Jobs
ENABLE_SCHEDULER=true

# Display (LED Matrix)
DISPLAY_HOST=localhost
DISPLAY_PORT=5555
```

### Step 6: Deploy Databases (If Needed)

If you're deploying for the first time or need to sync databases:

```bash
# Backup existing databases first!
# Then deploy (WARNING: This will overwrite existing databases)
DEPLOY_DATA=yes ./scripts/deploy.sh
```

**Note:** Only deploy databases if you're certain about what you're doing. Usually, databases should stay on the device.

### Step 7: Build and Deploy Application

**From your development machine:**

```bash
# Build ARM64 binaries
./scripts/build.sh

# Deploy binaries to Arduino
./scripts/deploy.sh

# Verify deployment
ssh arduino@192.168.1.11 "ls -lh /opt/arduino-trader/"
```

### Step 8: Start Services

**Option A: Using deployment scripts (from development machine):**

```bash
./scripts/restart.sh all
```

**Option B: Manually on Arduino:**

```bash
# Start microservices
cd /opt/arduino-trader
docker-compose up -d

# Start main application
sudo systemctl start trader

# Start display bridge (if needed)
sudo systemctl start display-bridge
```

### Step 9: Verify Deployment

**Check service status:**

```bash
# From development machine
./scripts/status.sh

# Or manually
ssh arduino@192.168.1.11 "sudo systemctl status trader display-bridge"
ssh arduino@192.168.1.11 "docker-compose -f /opt/arduino-trader/docker-compose.yml ps"
```

**Check health endpoints:**

```bash
# Main app
curl http://192.168.1.11:8080/health

# Microservices
curl http://192.168.1.11:9001/health  # pypfopt
curl http://192.168.1.11:9002/health  # tradernet
```

**View logs:**

```bash
# From development machine
./scripts/logs.sh trader 100 -f

# Or manually
ssh arduino@192.168.1.11 "sudo journalctl -u trader -f"
ssh arduino@192.168.1.11 "docker-compose -f /opt/arduino-trader/docker-compose.yml logs -f"
```

## Common Deployment Tasks

### Full Deployment (Build + Deploy + Restart)

```bash
./scripts/deploy-full.sh
```

### Deploy Only Binaries (No Build)

```bash
./scripts/deploy.sh
```

### Restart Services Only

```bash
./scripts/restart.sh all           # All services
./scripts/restart.sh trader        # Trader only
./scripts/restart.sh display-bridge # Display bridge only
```

### Check Status

```bash
./scripts/status.sh
```

### View Logs

```bash
./scripts/logs.sh trader 50        # Last 50 lines
./scripts/logs.sh trader 100 -f    # Follow last 100 lines
```

## Troubleshooting

### Cannot Connect to Arduino

```bash
# Test SSH connection
ssh -o ConnectTimeout=5 arduino@192.168.1.11 "echo 'OK'"

# Check if device is on network
ping 192.168.1.11

# Verify SSH is enabled on Arduino
```

### Services Won't Start

```bash
# Check service status
sudo systemctl status trader

# Check logs for errors
sudo journalctl -u trader -n 50

# Verify binary exists and is executable
ls -lh /opt/arduino-trader/trader
file /opt/arduino-trader/trader

# Check environment file
cat /opt/arduino-trader/.env
```

### Microservices Not Starting

```bash
# Check Docker is running
sudo systemctl status docker

# Check container status
docker ps -a
docker-compose -f /opt/arduino-trader/docker-compose.yml ps

# Check container logs
docker logs pypfopt-service
docker logs tradernet-service

# Rebuild containers
cd /opt/arduino-trader
docker-compose build --no-cache
docker-compose up -d
```

### Health Checks Failing

```bash
# Test endpoints manually
curl -v http://localhost:8080/health
curl -v http://localhost:9001/health
curl -v http://localhost:9002/health

# Check if ports are listening
netstat -tlnp | grep -E '8080|9001|9002'
ss -tlnp | grep -E '8080|9001|9002'
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R arduino:arduino /opt/arduino-trader
sudo chmod +x /opt/arduino-trader/trader
sudo chmod +x /opt/arduino-trader/display-bridge
```

## Maintenance

### Backup Databases

```bash
# Create backup directory
mkdir -p backups/arduino_backup_$(date +%Y%m%d_%H%M%S)

# Backup databases
scp arduino@192.168.1.11:/home/arduino/arduino-trader/data/*.db backups/arduino_backup_*/
```

### Update Application

```bash
# Standard update process
./scripts/deploy-full.sh

# Or step by step
./scripts/build.sh
./scripts/deploy.sh
./scripts/restart.sh all
```

### Update Microservices

```bash
# On Arduino device
cd /opt/arduino-trader

# Pull latest code (if using git)
# Or scp updated files from development machine

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## Security Notes

1. **SSH Keys**: Use SSH key authentication instead of passwords
2. **Firewall**: Restrict access to necessary ports only
3. **API Keys**: Store API credentials securely, never commit to git
4. **Service User**: Run services as non-root user (`arduino`)
5. **File Permissions**: Restrict file permissions appropriately

## Next Steps

After successful deployment:

1. Verify all health checks pass
2. Check system status endpoint: `curl http://192.168.1.11:8080/api/system/status`
3. Verify background jobs are scheduled: `curl http://192.168.1.11:8080/api/system/jobs`
4. Monitor logs for 24 hours to ensure stability
5. Verify first sync cycle completes successfully
6. Check that trading mode is set appropriately (research/live)

For more information, see the main [README.md](README.md).
