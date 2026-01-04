# Arduino Display Bridge (Go)

Go-based bridge service that connects the trader-go API to the Arduino Uno Q MCU via the arduino-router MessagePack RPC system.

## Why Go Instead of Python?

- **Lower memory footprint**: Arduino Uno Q has only 2GB RAM
- **Better performance**: Native binary vs interpreted Python
- **Consistency**: Entire stack in Go (trader-go + bridge-go + arduino-router)
- **Cleaner architecture**: Direct access to display logic without HTTP polling

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Arduino Uno Q (Linux MPU)                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  trader-go (API Server)                            │
│       ↓ HTTP                                        │
│  bridge-go (This Service)                          │
│       ↓ MessagePack RPC                            │
│  arduino-router (Hub)                              │
│       ↓ Serial                                      │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Arduino Uno Q (MCU - STM32U585)                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  sketch.ino                                         │
│  ├─ Portfolio mode (multi-cluster)                 │
│  ├─ Stats mode (CPU/RAM)                           │
│  └─ Ticker mode (scrolling text)                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Features

- **Portfolio Mode**: Sends cluster data for multi-cluster organic visualization
- **Stats Mode**: System resource visualization
- **Ticker Mode**: Scrolling text messages
- **RGB LED Control**: LED3 and LED4 status indicators
- **Auto-reconnect**: Resilient to arduino-router restarts
- **Structured logging**: Using zerolog for JSON/console output

## Configuration

Edit constants in `main.go`:

```go
const (
    APIURL       = "http://localhost:8000/api/status/led/display"
    RouterAddr   = "localhost:5555"  // arduino-router address
    PollInterval = 2 * time.Second   // API polling frequency
)
```

## Building

```bash
# For development (local machine)
go build -o bridge-go

# For Arduino Uno Q (ARM64 Linux)
GOOS=linux GOARCH=arm64 go build -o bridge-go
```

## Running Locally

```bash
# Install dependencies
go mod download

# Run
./bridge-go
```

Expected output:
```
INF Arduino Display Bridge (Go) starting...
INF Connecting to arduino-router addr=localhost:5555
INF Connected to arduino-router
INF Starting display client api_url=http://localhost:8000/api/status/led/display poll_interval=2s
DBG Sent portfolio mode num_clusters=6
```

## Deployment to Arduino Uno Q

### Prerequisites

1. **arduino-router** must be running on the Arduino Uno Q
2. **trader-go** must be running and serving on port 8000
3. **Arduino sketch** with portfolio mode must be flashed to MCU

### Steps

1. **Build for ARM64:**
   ```bash
   GOOS=linux GOARCH=arm64 go build -o bridge-go
   ```

2. **Deploy to Arduino:**
   ```bash
   scp bridge-go user@arduino-ip:/opt/arduino-trader/
   ```

3. **Create systemd service:**
   ```bash
   sudo cp bridge-go.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable bridge-go
   sudo systemctl start bridge-go
   ```

4. **Check logs:**
   ```bash
   sudo journalctl -u bridge-go -f
   ```

## Systemd Service

Create `/etc/systemd/system/bridge-go.service`:

```ini
[Unit]
Description=Arduino Display Bridge (Go)
After=network.target arduino-router.service trader-go.service
Requires=arduino-router.service

[Service]
Type=simple
User=arduino
WorkingDirectory=/opt/arduino-trader
ExecStart=/opt/arduino-trader/bridge-go
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### "Failed to connect to router"

arduino-router isn't running or listening on different port.

**Check if arduino-router is running:**
```bash
ps aux | grep arduino-router
```

**Check what port it's listening on:**
```bash
netstat -tlnp | grep arduino-router
```

**Start arduino-router if needed:**
```bash
arduino-router -p /dev/ttyACM0
```

### "RPC call failed"

The Arduino sketch hasn't registered the RPC method.

**Verify sketch registered methods:**
Check Arduino sketch setup() for:
```cpp
Bridge.provide("scrollText", scrollText);
Bridge.provide("setSystemStats", setSystemStats);
Bridge.provide("setPortfolioMode", setPortfolioMode);
```

### "API returned status 500"

trader-go has an error calculating display state.

**Check trader-go logs:**
```bash
docker logs trader-go 2>&1 | grep display
```

## Development

### Testing Locally

You can't run this on your development machine unless you have:
1. An Arduino Uno Q connected
2. arduino-router running
3. The bridge properly configured

For local development without hardware:
1. Mock the Bridge interface
2. Test API polling logic independently
3. Use integration tests on actual hardware

### Adding New Display Modes

1. **Add mode to DisplayState struct**
2. **Add handler method** (e.g., `HandleNewMode`)
3. **Update switch statement** in `UpdateDisplay()`
4. **Update Arduino sketch** to handle new RPC method
5. **Register method** in Arduino sketch's `setup()`

## Performance

**Memory usage**: ~10-15 MB (vs ~50-100 MB for Python)

**CPU usage**: Negligible (<1% on Arduino Uno Q)

**Network**: 1 HTTP request every 2 seconds

**RPC calls**: 1-3 per display update (depends on mode)

## References

- [Arduino Uno Q Documentation](https://docs.arduino.cc/hardware/uno-q)
- [arduino-router GitHub](https://github.com/arduino/arduino-router)
- [hashicorp/net-rpc-msgpackrpc](https://pkg.go.dev/github.com/hashicorp/net-rpc-msgpackrpc)
- [Portfolio Display Mode Documentation](../docs/portfolio-display-mode.md)
