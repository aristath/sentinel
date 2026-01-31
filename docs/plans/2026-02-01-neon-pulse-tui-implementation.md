# Neon Pulse TUI Implementation Plan
**Date:** 2026-02-01
**Based on:** docs/plans/2026-02-01-neon-pulse-tui-design.md

## Overview
Implement a cyber-retro terminal interface with neon aesthetics, blending TRON, Cyberpunk, Synthwave, and retro-futuristic elements.

---

## Phase 1: Core Infrastructure

### Task 1.1: Color Scheme System
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/theme.py` with color scheme definitions
2. Implement CSS class mappings for each of 4 schemes
3. Add theme management with current scheme tracking
4. Create color utility functions (glow effects, text colors)

**Files to create/modify:**
- `sentinel_tui/theme.py` (new)
- `sentinel_tui/app.py` (add theme import and management)
- `sentinel_tui/theme.tcss` (add neon CSS variables)

**Verification:**
- Run app, press "c" to cycle schemes
- Verify all 4 schemes render correctly
- Check color accuracy against design spec

---

### Task 1.2: Scanline Overlay Component
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/scanlines.py` widget
2. Add CSS scanline overlay with 60-80% opacity
3. Implement horizontal lines with subtle variation
4. Test on different terminal sizes

**Files to create:**
- `sentinel_tui/components/scanlines.py` (new)

**Verification:**
- Run app, verify scanlines appear
- Check opacity levels (subtle, not intrusive)
- Test resizing behavior

---

## Phase 2: Typography System

### Task 2.1: Bold Retro Styling
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/bold_retro.py` widget for headers
2. Add box-bracket layouts for sections
3. Style prominent metrics with retro formatting
4. Create action display components ("BUY $1000 AAPL.US")

**Files to create:**
- `sentinel_tui/components/bold_retro.py` (new)
- `sentinel_tui/theme.tcss` (add retro typography styles)

**Verification:**
- Create test display with portfolio hero
- Verify box-bracket layout renders correctly
- Check action items display with proper formatting

---

### Task 2.2: System Font Configuration
**Status:** PENDING

**Steps:**
1. Configure system monospace font stack
2. Add bold and italic variants
3. Test on different OS fonts
4. Ensure readability across all schemes

**Files to modify:**
- `sentinel_tui/theme.tcss` (add font configuration)

**Verification:**
- Test on macOS, Linux, Windows (if applicable)
- Verify font rendering for all text elements
- Check contrast ratios

---

## Phase 3: Visual Effects

### Task 3.1: Glow Effects
**Status:** PENDING

**Steps:**
1. Create CSS glow utility classes
2. Add text glow to metrics and important values
3. Add border inner glow for panels
4. Add selection glow for active rows

**Files to modify:**
- `sentinel_tui/theme.tcss` (add glow classes)

**Verification:**
- Test glow on all neon color schemes
- Check glow intensity (subtle, not overwhelming)
- Verify performance impact

---

### Task 3.2: Grid Background Renderer
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/grid_background.py` widget
2. Add perspective grid with data points
3. Implement slow drift animation
4. Keep low opacity for background

**Files to create:**
- `sentinel_tui/components/grid_background.py` (new)

**Verification:**
- Test grid animation smoothness
- Check opacity levels
- Verify grid doesn't interfere with readability

---

### Task 3.3: Pixel Art Icons
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/assets/pixel_icons.py` module
2. Add pixel art symbols for status indicators
3. Add Buy/Sell pixel signs
4. Create status dot indicators

**Files to create:**
- `sentinel_tui/assets/pixel_icons.py` (new)
- `sentinel_tui/theme.tcss` (add icon styles)

**Verification:**
- Test pixel art rendering on different terminals
- Verify icon clarity
- Check alignment with retro aesthetic

---

## Phase 4: Main UI Components

### Task 4.1: Header Bar Refactor
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/header_bar.py` widget
2. Add status indicator with pixel art
3. Add market status display
4. Add action buttons (Pause, Info)
5. Style with neon glow effects

**Files to create:**
- `sentinel_tui/components/header_bar.py` (new)

**Verification:**
- Test all header elements render correctly
- Check market status color coding
- Verify button interactivity

---

### Task 4.2: Portfolio Display
**Status:** PENDING

**Steps:**
1. Refactor `PortfolioSummary` to use bold retro styling
2. Add portfolio metrics with glow effects
3. Add P/L display with color coding
4. Style total value with larger retro font

**Files to modify:**
- `sentinel_tui/app.py` (PortfolioSummary class)
- `sentinel_tui/theme.tcss` (add portfolio styles)

**Verification:**
- Display portfolio data correctly
- Check P/L color accuracy
- Verify glow effects work

---

### Task 4.3: Recommendation Panel
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/recommendation_panel.py` widget
2. Style action items with bold retro layout
3. Add Buy/Sell visual distinction
4. Format amounts prominently
5. Add summary line with box-bracket styling

**Files to create:**
- `sentinel_tui/components/recommendation_panel.py` (new)

**Verification:**
- Display recommendations correctly
- Check Buy/Sell visual distinction
- Verify action item formatting

---

### Task 4.4: Securities Table Enhancement
**Status:** PENDING

**Steps:**
1. Add row selection with pixel cursor
2. Add hover effects (dim row, brighten values)
3. Add glow to selected row
4. Style table headers with retro layout
5. Add position indicator (pixel dot)

**Files to modify:**
- `sentinel_tui/app.py` (DataTable styling)
- `sentinel_tui/theme.tcss` (table styles)

**Verification:**
- Test row selection navigation
- Check hover effects
- Verify table styling matches design
- Test scrolling behavior

---

### Task 4.5: Status Bar Integration
**Status:** PENDING

**Steps:**
1. Integrate color scheme indicator
2. Add market status display
3. Style connection status with glow
4. Add theme scheme display (e.g., "SCHEME: 1/4")

**Files to modify:**
- `sentinel_tui/app.py` (status bar logic)
- `sentinel_tui/theme.tcss` (status bar styles)

**Verification:**
- Display connection status correctly
- Show market status with color coding
- Verify scheme indicator updates with "c" key
- Check glow effects

---

## Phase 5: Interactivity

### Task 5.1: Selection System
**Status:** PENDING

**Steps:**
1. Implement row selection tracking
2. Add keyboard navigation (↑/↓, HOME/END)
3. Create pixel cursor indicator
4. Add selection glow effects
5. Implement row click handler

**Files to modify:**
- `sentinel_tui/app.py` (selection logic)
- `sentinel_tui/theme.tcss` (cursor styles)

**Verification:**
- Test all navigation keys
- Verify pixel cursor appears on selected row
- Check selection glow
- Test row click opens detail view

---

### Task 5.2: Hover Effects
**Status:** PENDING

**Steps:**
1. Add hover event listener to table rows
2. Implement dimmed row on hover
3. Brighten values on hover
4. Add subtle pulse to row background
5. Test performance

**Files to modify:**
- `sentinel_tui/app.py` (hover logic)
- `sentinel_tui/theme.tcss` (hover styles)

**Verification:**
- Test hover on all rows
- Check dimming/brightening effects
- Verify performance (60fps)
- Test on different terminal sizes

---

### Task 5.3: Keyboard Binding
**Status:** PENDING

**Steps:**
1. Add "c" binding for color scheme cycling
2. Add "m" binding for mode toggle (simple/light/dark)
3. Add "SPACE"/"ENTER" for opening detail view
4. Update footer with key bindings display
5. Add key binding help modal

**Files to modify:**
- `sentinel_tui/app.py` (bindings)
- `sentinel_tui/theme.tcss` (binding styles)

**Verification:**
- Test "c" cycles through 4 schemes
- Test "m" toggles between modes
- Test SPACE/ENTER opens detail view
- Verify footer key display
- Check help modal

---

## Phase 6: Animations

### Task 6.1: Entrance Animation
**Status:** PENDING

**Steps:**
1. Add CSS keyframes for fade-in
2. Create staggered animation for elements
3. Add glitch effect to title
4. Implement sequential reveal
5. Test animation timing

**Files to modify:**
- `sentinel_tui/theme.tcss` (add keyframes)

**Verification:**
- Test app startup animation
- Check staggered reveal timing
- Verify glitch effect
- Test smooth transitions

---

### Task 6.2: Update Animations
**Status:** PENDING

**Steps:**
1. Add CSS transition for value changes
2. Implement flash effect on significant changes
3. Add pulse animation on new data
4. Test animation smoothness
5. Optimize for performance

**Files to modify:**
- `sentinel_tui/theme.tcss` (add transitions)
- `sentinel_tui/app.py` (update logic)

**Verification:**
- Test value update animations
- Check flash on significant changes
- Verify pulse effect
- Test performance impact

---

### Task 6.3: Color Scheme Transitions
**Status:** PENDING

**Steps:**
1. Add smooth color transition between schemes
2. Implement fade in/out effect
3. Test color transition timing
4. Optimize for performance

**Files to modify:**
- `sentinel_tui/theme.tcss` (add transition)

**Verification:**
- Test scheme transition smoothness
- Check fade timing
- Verify performance impact
- Test on different themes

---

## Phase 7: Error States

### Task 7.1: Disconnected State
**Status:** PENDING

**Steps:**
1. Create `sentinel_tui/components/error_display.py` widget
2. Add red glow effect
3. Implement glitch animation
4. Add retry prompt
5. Style with retro layout

**Files to create:**
- `sentinel_tui/components/error_display.py` (new)

**Verification:**
- Test with API disconnected
- Check error display styling
- Verify glitch animation
- Test retry prompt interaction

---

## Phase 8: Polish

### Task 8.1: Responsive Adjustments
**Status:** PENDING

**Steps:**
1. Test layout on different terminal sizes
2. Adjust spacing for small screens
3. Optimize for mobile terminals
4. Fix layout breaks

**Files to modify:**
- `sentinel_tui/theme.tcss` (responsive adjustments)
- `sentinel_tui/app.py` (layout adjustments)

**Verification:**
- Test on multiple terminal sizes
- Check layout integrity
- Verify text readability
- Test resize behavior

---

### Task 8.2: Accessibility Review
**Status:** PENDING

**Steps:**
1. Check color contrast ratios
2. Verify text size readability
3. Test keyboard navigation
4. Check focus indicators
5. Verify screen reader compatibility

**Files to modify:**
- `sentinel_tui/theme.tcss` (accessibility improvements)
- `sentinel_tui/app.py` (accessibility features)

**Verification:**
- Run accessibility tests
- Check WCAG compliance
- Verify keyboard navigation
- Test with screen reader (if available)

---

### Task 8.3: Performance Optimization
**Status:** PENDING

**Steps:**
1. Measure render performance
2. Optimize heavy animations
3. Reduce redundant renders
4. Test frame rate
5. Profile memory usage

**Files to modify:**
- `sentinel_tui/app.py`
- `sentinel_tui/theme.tcss`

**Verification:**
- Target 60fps during animations
- Measure memory usage
- Test performance on slower terminals
- Verify smooth scrolling

---

## Implementation Order

**Batch 1 (Core):**
1. Task 1.1: Color Scheme System
2. Task 1.2: Scanline Overlay Component
3. Task 2.1: Bold Retro Styling

**Batch 2 (Visual Effects):**
1. Task 3.1: Glow Effects
2. Task 3.2: Grid Background Renderer
3. Task 3.3: Pixel Art Icons

**Batch 3 (Main UI):**
1. Task 4.1: Header Bar Refactor
2. Task 4.2: Portfolio Display
3. Task 4.3: Recommendation Panel

**Batch 4 (Table & Status):**
1. Task 4.4: Securities Table Enhancement
2. Task 4.5: Status Bar Integration
3. Task 5.1: Selection System

**Batch 5 (Interactivity):**
1. Task 5.2: Hover Effects
2. Task 5.3: Keyboard Binding
3. Task 7.1: Disconnected State

**Batch 6 (Animations):**
1. Task 6.1: Entrance Animation
2. Task 6.2: Update Animations
3. Task 6.3: Color Scheme Transitions

**Batch 7 (Polish):**
1. Task 8.1: Responsive Adjustments
2. Task 8.2: Accessibility Review
3. Task 8.3: Performance Optimization

---

## Success Criteria

- All 4 color schemes render correctly
- "c" key cycles through schemes smoothly
- All visual effects (scanlines, glow, grid) appear
- Typography system displays correctly with bold retro elements
- Row selection and navigation work smoothly
- Hover effects enhance usability
- Animations are smooth and not distracting
- Error states display properly
- Performance meets 60fps target
- Layout remains intact on various terminal sizes
