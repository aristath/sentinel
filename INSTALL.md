# Arduino Trader - Installation Guide

Complete installation guide for the Arduino Trader microservices architecture.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Fresh Installation](#fresh-installation)
4. [Modifying Existing Installation](#modifying-existing-installation)
5. [Distributed Deployment](#distributed-deployment)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

## Prerequisites

### Hardware
- **Arduino Uno Q** (for production deployment)
- **Minimum 2GB free disk space**
- **Network connection** (for distributed deployments)

### Software
- **Python 3.10+** - Application runtime
- **Docker** - Container runtime
- **Docker Compose** - Multi-container orchestration
- **Git** - Version control (for updates)
- **Arduino CLI** - For LED display (optional)

### API Credentials
- **Tradernet (Freedom24) API Key** - Required for trading
- **Tradernet API Secret** - Required for trading

## Quick Start

For most users, a single-device installation is recommended:

```bash
# 1. Clone repository
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# 2. Run installer
sudo ./install.sh

# 3. Select "all" when prompted for services
# 4. Enter your Tradernet API credentials
# 5. Wait for installation to complete (~15 minutes)

# 6. Access the dashboard
open http://localhost:8000
```

## Fresh Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/aristath/autoTrader.git
cd autoTrader
```

### Step 2: Run Interactive Installer

```bash
sudo ./install.sh
```

The installer will guide you through 9 phases:

**Phase 1**: Detect Existing Installation
- Checks for existing installation
- For fresh installs, proceeds automatically

**Phase 2**: Check Prerequisites
- Validates Python, Docker, disk space
- Offers to install missing tools

**Phase 3**: Service Selection
- Choose which services to run on this device
- Select "all" for single-device deployment
- Or select specific services for distributed deployment

**Phase 4**: Device Addresses (Distributed Only)
- Enter IP addresses for remote services
- Tests connectivity to ensure services are reachable

**Phase 5**: Configuration
- Enter Tradernet API credentials
- All other settings use sensible defaults

**Phase 6**: Generate Config Files
- Creates .env, device.yaml, services.yaml

**Phase 7**: Setup Microservices
- Builds Docker images
- Starts selected services
- Sets up systemd for auto-start

**Phase 8**: Health Checks
- Validates all services are running
- Tests connectivity

**Phase 9**: Installation Summary
- Displays access URLs
- Shows management commands

### Step 3: Access Dashboard

```bash
# Local access
http://localhost:8000

# API documentation
http://localhost:8000/docs
```

### Step 4: Verify Services

```bash
# Check service status
docker compose ps

# View logs
docker compose logs -f

# Check health
curl http://localhost:8000/health
```

## Modifying Existing Installation

The installer supports modifying existing installations, allowing you to:
- Change which services run on this device
- Migrate from single-device to distributed
- Update device IP addresses
- Change configuration

### Example: Migrate Single → Distributed

Currently running all services on one device, want to split across two devices:

```bash
# On Device 1 (192.168.1.100)
sudo ./install.sh

# When prompted:
# - Select: planning, scoring, universe, gateway (4 services)
# - Enter Device 2 IP for remaining services: 192.168.1.101

# On Device 2 (192.168.1.101)
sudo ./install.sh

# When prompted:
# - Select: optimization, portfolio, trading (3 services)
# - Enter Device 1 IP for planning, scoring, universe, gateway
```

### Example: Update Device Addresses

Change the IP address of a remote device:

```bash
sudo ./install.sh

# Installer detects existing installation
# Select same services as before
# Enter new IP addresses when prompted
```

## Distributed Deployment

### Planning Your Deployment

**Recommended Service Distribution:**

**Device 1 (Core Services):**
- Planning
- Scoring
- Universe
- Gateway (required on at least one device)

**Device 2 (Execution Services):**
- Optimization
- Portfolio
- Trading

### Network Requirements

- All devices must be on the same network
- Services communicate via HTTP (ports 8000-8007)
- Gateway device accessible from your web browser

### Installation Steps

1. **Install on first device**:
   - Select core services
   - Note device IP address

2. **Install on second device**:
   - Select execution services
   - Enter first device IP for core services

3. **Verify connectivity**:
   - Installer tests connections automatically
   - Check health via gateway: `http://[gateway-ip]:8000/health`

### Managing Distributed Services

```bash
# On each device, manage local services
docker compose ps          # Status
docker compose logs -f     # Logs
docker compose restart     # Restart

# Access centralized dashboard from any device
http://[gateway-device-ip]:8000
```

## Troubleshooting

### Installation Fails: Prerequisites Check

**Problem**: Python version too old

```bash
# Update Python
sudo apt update
sudo apt install python3.10 python3-pip
```

**Problem**: Docker not found

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Problem**: Insufficient disk space

```bash
# Check available space
df -h

# Clean Docker
docker system prune -a
```

### Services Not Starting

**Check service status**:
```bash
docker compose ps
```

**View logs for errors**:
```bash
docker compose logs [service-name]

# Example
docker compose logs planning
```

**Restart services**:
```bash
docker compose down
docker compose up -d
```

### Health Checks Failing

**Test individual service**:
```bash
curl http://localhost:8000/health  # Gateway (exposed on 8000)
curl http://localhost:8006/health  # Planning
curl http://localhost:8004/health  # Scoring
curl http://localhost:8001/health  # Universe
```

**Check if ports are in use**:
```bash
lsof -i :8000
```

**Kill conflicting processes**:
```bash
sudo kill -9 [PID]
```

### Distributed: Cannot Connect to Remote Services

**Test network connectivity**:
```bash
ping [remote-device-ip]
curl http://[remote-device-ip]:8000/health
```

**Check firewall**:
```bash
# Allow Docker network traffic
sudo ufw allow 8000:8007/tcp
```

**Verify services.yaml**:
```bash
cat app/config/services.yaml
# Check remote service addresses are correct
```

### Configuration Errors

**Reset configuration**:
```bash
# Backup first
cp app/config/device.yaml app/config/device.yaml.backup
cp app/config/services.yaml app/config/services.yaml.backup

# Run installer again
sudo ./install.sh
```

**Manual configuration editing**:
```bash
nano app/config/device.yaml      # Device roles
nano app/config/services.yaml    # Service addresses
nano .env                          # API credentials
```

## FAQ

### Q: Can I change services later?

**A**: Yes! Just run `sudo ./install.sh` again and select different services.

### Q: Do I need to run all services?

**A**: No. You can run any subset of services, but at least one device must run the Gateway service.

### Q: Can I run services on more than 2 devices?

**A**: Yes. The installer supports any number of devices. Just select appropriate services for each device.

### Q: How do I update to the latest version?

**A**: Pull latest changes and restart services:
```bash
git pull origin micro-services
docker compose down
docker compose build
docker compose up -d
```

### Q: Can I mix Docker and non-Docker services?

**A**: No. All services must run via Docker for the microservices architecture.

### Q: What if I forget my API credentials?

**A**: Run installer again and enter new credentials when prompted. Old credentials will be backed up.

### Q: How do I backup my installation?

**A**: Backup these directories:
```bash
tar -czf arduino-trader-backup.tar.gz \
  /home/arduino/arduino-trader/data \
  /home/arduino/arduino-trader/app/config \
  /home/arduino/arduino-trader/.env
```

### Q: How do I restore from backup?

**A**: Extract backup and restart services:
```bash
tar -xzf arduino-trader-backup.tar.gz -C /
docker compose restart
```

### Q: Can I run this on macOS/Linux desktop?

**A**: Yes! The installer works on any Linux or macOS system with Docker. Just skip Arduino-specific steps (LED display).

### Q: Do services need to be on the same network?

**A**: Yes, services communicate via HTTP and must be able to reach each other's IP addresses.

### Q: What ports are used?

**A**:
- Universe: 8001
- Portfolio: 8002
- Trading: 8003
- Scoring: 8004
- Optimization: 8005
- Planning: 8006
- Gateway: 8007 (exposed on host port 8000 for web dashboard)

### Q: How do I monitor service health?

**A**:
```bash
# Check all services
curl http://localhost:8000/api/status/jobs

# Individual service health
docker compose ps
```

### Q: What if a service crashes?

**A**: Docker will automatically restart failed services. Check logs to diagnose:
```bash
docker compose logs [service-name]
```

## Additional Resources

- **Main README**: `README.md` - Architecture and features
- **Project Instructions**: `CLAUDE.md` - Development guidelines
- **API Documentation**: `http://localhost:8000/docs` - Interactive API docs
- **GitHub Issues**: https://github.com/aristath/autoTrader/issues

## Support

For issues or questions:
1. Check this INSTALL.md
2. Review logs: `docker compose logs`
3. Check GitHub issues
4. Create new issue with logs and error messages

---

**Installation complete!** Access your dashboard at `http://localhost:8000`
