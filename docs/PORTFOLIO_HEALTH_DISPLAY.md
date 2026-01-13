# Portfolio Health Display

An organic, evolving LED matrix visualization that shows the health of your portfolio securities in real-time.

## Overview

The portfolio health display is a new display mode that visualizes the health of each security in your portfolio using animated clusters on the 8x13 LED matrix. The animation is entirely handled by the Arduino MCU, with the Go backend calculating health scores every 15-30 minutes.

## Features

- **Organic Animation**: Clusters drift across the matrix using Perlin noise for natural, flowing motion
- **Burn-in Prevention**: Continuous movement ensures no pixel stays permanently lit
- **Health-Based Brightness**: Healthier securities appear brighter
- **All Holdings**: Displays up to 20 securities simultaneously
- **MCU-Driven**: All animation logic runs on the Arduino for smooth 60 FPS performance

## Architecture

```
Go Backend (MPU)                    Python App                  Arduino MCU
┌─────────────────┐                ┌──────────┐                ┌─────────────────┐
│ Health          │  Every 15-30   │          │   Bridge       │                 │
│ Calculator      │────────────────▶│  POST    │───────────────▶│  Perlin Noise   │
│                 │    minutes      │ /portfolio│   Call        │  Animation      │
│ - Score         │                 │ -health  │                │  (60 FPS)       │
│ - Performance   │                 │          │                │                 │
│ - Volatility    │                 └──────────┘                │  LED Matrix     │
└─────────────────┘                                             └─────────────────┘
```

## Health Calculation

Health for each security is calculated as a weighted average of three components:

1. **Security Score** (40% weight): Total score from scoring system (0-100 scale)
2. **Performance vs Target** (40% weight): Trailing 12mo CAGR compared to target annual return
3. **Volatility** (20% weight): Inverted volatility (lower volatility = higher health)

Formula:
```
health = (score/100 * 0.4) + (norm(perf_vs_target) * 0.4) + ((1-volatility) * 0.2)
```

Result is normalized to 0.0-1.0 where:
- `1.0` = Thriving (high score, beating target, stable)
- `0.5` = Neutral (on target, moderate volatility)
- `0.0` = Critical (low score, underperforming, volatile)

## Display Modes

The system supports three display modes:

### TEXT Mode (Default)
Scrolling ticker showing portfolio value, cash, and pending recommendations.

### HEALTH Mode
Organic health visualization with animated clusters representing each security.

### STATS Mode
System statistics visualization (existing pixel count mode).

## Usage

### Switching Modes via API

```bash
# Switch to health mode
curl -X POST http://localhost:8001/api/display/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "HEALTH"}'

# Switch back to text mode
curl -X POST http://localhost:8001/api/display/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "TEXT"}'

# Get current mode
curl http://localhost:8001/api/display/mode
```

### Preview Health Scores

```bash
# View current health scores for all holdings
curl http://localhost:8001/api/display/portfolio-health/preview
```

### Manually Trigger Update

```bash
# Force immediate health update (useful for testing)
curl -X POST http://localhost:8001/api/display/portfolio-health/trigger
```

## Configuration

All settings are in `config.db` with defaults in `internal/modules/settings/models.go`:

### Core Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `display_mode` | `"TEXT"` | Current display mode |
| `display_health_update_interval` | `1800` | Seconds between health updates (30 min) |
| `display_health_max_securities` | `20` | Max securities to display |

### Health Calculation Weights

| Setting | Default | Description |
|---------|---------|-------------|
| `display_health_score_weight` | `0.4` | Weight for security score |
| `display_health_performance_weight` | `0.4` | Weight for performance vs target |
| `display_health_volatility_weight` | `0.2` | Weight for volatility |

### Animation Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `display_health_animation_fps` | `60` | Frame rate (handled by MCU) |
| `display_health_drift_speed` | `0.5` | Cluster movement speed |
| `display_health_cluster_radius` | `2.5` | Cluster size in pixels |

### Brightness Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `display_health_min_brightness` | `100` | Minimum LED brightness |
| `display_health_max_brightness` | `180` | Maximum LED brightness |
| `display_background_brightness_min` | `80` | Background cluster min brightness |
| `display_background_brightness_max` | `120` | Background cluster max brightness |

### Performance Thresholds

| Setting | Default | Description |
|---------|---------|-------------|
| `display_performance_thriving_threshold` | `0.03` | +3% above target |
| `display_performance_on_target_threshold` | `0.00` | On target |
| `display_performance_below_threshold` | `-0.03` | -3% below target |

## Files

### Go Backend
- `internal/modules/display/health_calculator.go` - Health score calculation
- `internal/modules/display/health_updater.go` - Background updater service
- `internal/modules/display/mode_manager.go` - Display mode switching
- `internal/modules/display/handlers/handlers.go` - HTTP handlers
- `internal/modules/display/handlers/routes.go` - Route registration

### Arduino MCU
- `display/sketch/sketch.ino` - Enhanced with health animation logic
  - Perlin noise implementation
  - Cluster physics and rendering
  - JSON parsing for health data

### Python Bridge
- `display/python/main.py` - Added `/portfolio-health` endpoint

### Configuration
- `internal/modules/settings/models.go` - Default settings
- `internal/di/services.go` - Service initialization
- `internal/di/types.go` - Container types

## How It Works

### 1. Health Calculation (Go - Every 15-30 minutes)

```go
// Get all holdings
holdings := GetTopHoldings()

// For each holding
for _, holding := range holdings {
    // Calculate components
    scoreComponent := GetSecurityScore(holding)
    perfComponent := GetPerformanceVsTarget(holding)
    volComponent := GetVolatility(holding)

    // Weighted average
    health := (scoreComponent * 0.4) +
              (perfComponent * 0.4) +
              (volComponent * 0.2)
}

// Send to display
POST http://localhost:7000/portfolio-health
{
  "securities": [
    {"symbol": "AAPL", "health": 0.85},
    {"symbol": "GOOGL", "health": 0.72},
    ...
  ]
}
```

### 2. Data Transfer (Python Bridge)

```python
# Receive health data from Go
@app.post("/portfolio-health")
async def handle_set_portfolio_health(request):
    data = await request.json()
    json_str = json.dumps(data)

    # Pass to Arduino MCU via Bridge
    Bridge.call("setPortfolioHealth", json_str)
```

### 3. Animation (Arduino MCU - 60 FPS)

```cpp
// Parse JSON and initialize clusters
void setPortfolioHealth(String jsonData) {
    parseAndInitClusters(jsonData);
    healthMode = true;
}

// Animation loop (every 16ms)
void loop() {
    if (healthMode) {
        updateHealthClusters();  // Update positions with Perlin noise
        renderHealthFrame();     // Calculate brightness per pixel
    }
}

// Update cluster positions
void updateHealthClusters() {
    for (each cluster) {
        // Get Perlin noise values
        noiseX = perlinNoise(cluster.noiseOffsetX);
        noiseY = perlinNoise(cluster.noiseOffsetY);

        // Update velocity (smoothed)
        cluster.velocityX = cluster.velocityX * 0.9 + noiseX * 0.1;

        // Update position
        cluster.centerX += cluster.velocityX * 0.05;

        // Soft boundary bounce
        if (cluster.centerX < 0 || cluster.centerX > 12) {
            cluster.velocityX *= -0.5;
        }
    }
}

// Render frame
void renderHealthFrame() {
    for (each pixel) {
        // Find nearest cluster
        nearestCluster = findNearestCluster(pixel);

        // Calculate brightness based on distance and health
        distance = calculateDistance(pixel, nearestCluster);
        falloff = 1.0 - (distance / (radius * 2));
        brightness = falloff * health * 7; // 0-7 scale

        frame[pixel] = brightness;
    }
    matrix.draw(frame);
}
```

## Burn-in Prevention

The system prevents LED burn-in through multiple mechanisms:

1. **Continuous Motion**: Clusters never stay still, always drifting via Perlin noise
2. **Pixel Rotation**: Over ~30 minutes, clusters drift across the entire matrix
3. **Brightness Variation**: Health-based brightness (100-220 range) varies per cluster
4. **Distance Falloff**: Pixels at cluster edges are dimmer than centers
5. **Configurable Intensity**: Max brightness can be reduced if needed

## Troubleshooting

### Health mode not starting
- Check display is enabled: `curl http://localhost:7000/health`
- Verify mode manager initialized: Check logs for "Display mode manager initialized"
- Ensure portfolio has holdings: `curl http://localhost:8001/api/display/portfolio-health/preview`

### Animation looks jerky
- Check MCU is receiving updates: Look for "setPortfolioHealth" in Arduino serial output
- Verify frame rate: Should be ~60 FPS (16ms per frame)
- Reduce `display_health_drift_speed` if motion is too fast

### Clusters not moving
- Verify Perlin noise is working: Check `noiseOffsetX/Y` values are incrementing
- Check velocity values are non-zero
- Ensure `healthMode` flag is true

### LEDs too bright/dim
- Adjust `display_health_min_brightness` and `display_health_max_brightness`
- Check health scores are in 0-1 range
- Verify brightness calculation: `brightness = falloff * health * 7`

## Future Enhancements

Potential improvements for future versions:

- **Color Support**: Use RGB LEDs to show health with color (green=healthy, red=unhealthy)
- **Cluster Size**: Vary cluster size based on portfolio weight
- **Interaction**: Touch/button to show security details
- **Modes**: Add "pulse" mode where clusters breathe in/out
- **Alerts**: Flash clusters when significant events occur
- **History**: Show historical health trends with trailing effects

## Testing

```bash
# Build and test
cd /Users/aristath/sentinel
go build -o sentinel ./cmd/server

# Run server
./sentinel

# In another terminal, test health mode
curl -X POST http://localhost:8001/api/display/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "HEALTH"}'

# View health scores
curl http://localhost:8001/api/display/portfolio-health/preview

# Force update
curl -X POST http://localhost:8001/api/display/portfolio-health/trigger
```

## Credits

Designed and implemented for the Sentinel autonomous portfolio management system running on Arduino Uno Q.
