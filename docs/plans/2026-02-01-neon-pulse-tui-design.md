# Neon Pulse TUI Design
**Date:** 2026-02-01

## Overview

A cyber-retro terminal interface blending 80s futurism with modern terminal aesthetics. Combines TRON's clean lines, Cyberpunk's neon intensity, Synthwave's warm nostalgia, and retro-futuristic typography.

## Typography System

### Bold Retro Styling (Prominent Elements)
- Box-bracket layout for sections
- Monospace, styled display text
- Action items: "BUY $1000 AAPL.US", "SELL $700 IBM"
- Box-drawing characters for structure

### System Pixel Font (Normal Text)
- System monospace fonts
- Bold/italic variants for emphasis
- Clean, readable, authentic terminal feel

## Four Color Schemes

### Scheme 1: Synthwave Sunset
- Background: Deep purple (#1a0b2e)
- Primary accent: Hot pink (#ff00ff)
- Secondary: Electric cyan (#00ffff)
- Text: White with pink glow
- Vibe: Warm, dreamy, nostalgic

### Scheme 2: Cyberpunk Matrix
- Background: Almost black (#0a0a0a)
- Primary accent: Matrix green (#00ff41)
- Secondary: Magenta (#ff00ff)
- Text: Green with black halo
- Vibe: Hacker terminal, digital

### Scheme 3: Neon Tron
- Background: Deep blue (#0d1b2a)
- Primary accent: Cyan (#00f3ff)
- Secondary: Bright orange (#ff9d00)
- Text: White with cyan glow
- Vibe: Clean, digital, futuristic

### Scheme 4: Cyberpunk Night
- Background: Dark slate (#1a1a2e)
- Primary accent: Neon pink (#ff0099)
- Secondary: Electric blue (#00d4ff)
- Text: White with pink glow
- Vibe: Urban night, high contrast

## Visual Effects

### Scanlines
- Faint horizontal lines overlay
- CRT monitor feel
- 60-80% opacity, low intensity

### Glow Effects
- Text glow on metrics
- Border inner glow
- Selection with neon bloom

### Grid Backgrounds
- Subtle perspective grid
- Data points scattered
- Animated slow drift
- Low opacity

### Pixel Art Elements
- Small decorative pixel icons
- Status indicators as pixel blocks
- Buy/Sell signs as pixel symbols

## Layout Design

### Header Bar
```
[CONNECTED ●] MARKETS: OPEN  [PAUSE ▶] [INFO i]
```
- Status indicator with glow
- Market status with color coding
- Action buttons with pixel styling

### Main Display
```
┌──────────────────────────────────────────┐
│  PORTFOLIO: €123,456.78  P/L: +12.4%     │
│  ──────────────────────────────────────   │
│  ┌──────────┐  ┌──────────┐              │
│  │  PLANNER │  │  PLANNER │              │
│  │ RECOMMENDATIONS │                 │
│  │  [BUY]   │  │  [SELL]  │              │
│  └──────────┘  └──────────┘              │
└──────────────────────────────────────────┘
```

### Table Section
```
╔═══════════════╦═══════════╦═════════╗
║ SYMBOL       ║  VALUE   ║  P/L    ║
╠═══════════════╬═══════════╬═════════╣
║ AAPL.US   ●   ║ €45,000   ║  +5.2%  ║
║ TSLA.US      ║ €12,500   ║ -2.1%   ║
╚═══════════════╩═══════════╩═════════╝
```

## Interactive Elements

### Selection
- Highlight rows with neon glow
- Pixel cursor indicator
- Smooth transitions

### Hover Effects
- Row dims slightly
- Value brightens
- Tooltip shows details

### Hover Binding
- Press "SPACE" or "ENTER" to open details
- Shows selected security info
- Interactive chart display

## Animations

### Entrance Animation
- Elements fade in sequentially
- Glitch effect on title
- Smooth staggered reveal

### Updates
- Values animate when changing
- Flash effect on significant changes
- Pulse on new data arrival

### Transitions
- Smooth color scheme switch
- Fade in/out between colors
- Progress bar for loading

## Binding System

### Basic Navigation
- `q` - Quit
- `r` - Refresh
- `c` - Cycle color scheme
- `m` - Toggle mode (simple/light/dark variations)

### Selection
- `ENTER`/`SPACE` - Open detail view
- `↑`/`↓` - Navigate rows
- `HOME`/`END` - First/Last row

## Error States

**Disconnected**
```
┌────────────────────────────────────┐
│      ⚠ CONNECTION LOST              │
│                                     │
│  Unable to reach API at http://...  │
│                                     │
│  Press [R] to retry                 │
└────────────────────────────────────┘
```
- Red glow effect
- Glitch animation
- Retry prompt

## Implementation Priority

1. **Core Infrastructure**
   - Color scheme system with cycling
   - CSS variables and theme management
   - Scanline overlay component

2. **Typography System**
   - Bold retro styling for headers
   - System font stack configuration
   - Box-drawing character layouts

3. **Visual Effects**
   - Glow effect utilities
   - Grid background renderer
   - Pixel art icon set

4. **Main UI Components**
   - Header bar with status indicators
   - Portfolio display with metrics
   - Recommendation panel
   - Securities table with styling

5. **Interactivity**
   - Row selection with hover
   - Detail view integration
   - Smooth animations

6. **Polish**
   - Entrance animations
   - Error state styling
   - Responsive adjustments
