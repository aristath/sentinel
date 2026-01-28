# Sentinel LED - Arduino App

Treemap portfolio visualization for Arduino UNO Q's 8x13 LED matrix.

## Visualization

Each security is a **rectangular region** sized by allocation percentage. All pixels oscillate continuously to prevent burn-in.

```
┌──────────┬─────────────────────┐
│  CAT     │                     │
│  23%     │       BYD           │
├──────────┤       17%           │
│  MOH 9%  │                     │
├────┬─────┼───────┬─────────────┤
│PPC │ AM  │ MEVA  │    TSM      │
│ 6% │ 6%  │  4%   │     4%      │
├────┴─────┴───────┴─────────────┤
│  smaller positions...          │
└────────────────────────────────┘
```

## Information Encoding

### Waveform → Planner Action

| Waveform | Action | Character |
|----------|--------|-----------|
| **Sine** | Hold / Accumulate | Smooth, calm breathing |
| **Sawtooth ↑** | Buy | Builds up, quick drop |
| **Sawtooth ↓** | Sell / Reduce | Quick rise, drains down |
| **Triangle** | Rebalance | Symmetric back-and-forth |
| **Pulse** | Urgent | Sharp spikes |

### Frequency → Urgency

| Period | Urgency |
|--------|---------|
| 4000ms | Low - watching |
| 2500ms | Normal |
| 1500ms | Elevated |
| 800ms | High priority |
| 300ms | Urgent - act now |

### Brightness → Profit/Loss

| Brightness Range | P/L Status |
|------------------|------------|
| 180-250 | > +20% |
| 150-220 | +10% to +20% |
| 120-190 | +5% to +10% |
| 100-170 | 0% to +5% |
| 80-150 | -5% to 0% |
| 60-130 | -10% to -5% |
| 40-110 | -20% to -10% |
| 25-95 | < -20% |

## Example Readings

| Visual | Meaning |
|--------|---------|
| Bright, slow sine | Profitable, hold calmly |
| Dim, slow sine | Underwater, hold patiently |
| Medium, fast sawtooth ↑ | Buy opportunity |
| Bright, medium sawtooth ↓ | Taking profits |
| Dim, fast pulse | Urgent exit signal |

## Architecture

```
Sentinel API (port 8000)
        │
        │  GET /api/portfolio
        │  GET /api/planner/actions
        ▼
sentinel-led App (Docker)
        │
        │  Bridge.call("updateTreemap", bytes)
        ▼
STM32U585 MCU (60fps render)
        │
        ▼
8x13 LED Matrix
```

## Wire Protocol

Treemap update: `[count, region0..., region1..., ...]`

Each region (11 bytes):
```
[x, y, w, h, min_bright, max_bright, period_hi, period_lo, waveform, phase_hi, phase_lo]
```

## Deployment

```bash
./scripts/deploy-led-app.sh
```

## Commands

```bash
# View logs
ssh arduino@192.168.1.11 'arduino-app-cli app logs user:sentinel-led'

# Restart
ssh arduino@192.168.1.11 'arduino-app-cli app restart user:sentinel-led'

# Stop
ssh arduino@192.168.1.11 'arduino-app-cli app stop user:sentinel-led'
```
