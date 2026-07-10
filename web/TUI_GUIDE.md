# TUI Style Guide

Terminal User Interface styling for Sentinel's web UI.

## Overview

The TUI theme transforms Mantine components into a terminal-like aesthetic with:

- **Sharp edges** - No rounded corners anywhere
- **High contrast borders** - Visible panel boundaries
- **Dense layout** - Tighter spacing, more information density
- **Flat design** - No shadows, gradients, or subtle effects
- **Monospace typography** - JetBrains Mono throughout

## Color Palette

Using **Catppuccin Mocha** dark theme:

| Purpose | Color | Usage |
|---------|-------|-------|
| `base` | `#1e1e2e` | Primary background |
| `mantle` | `#181825` | Secondary panels, cards |
| `crust` | `#11111b` | Code blocks, nested surfaces |
| `surface0` | `#313244` | Table headers, title bars |
| `surface1` | `#45475a` | Borders, dividers |
| `text` | `#cdd6f4` | Primary text |
| `subtext0` | `#a6adc8` | Labels, muted text |
| `overlay1` | `#7f849c` | Subtle metadata |

Accent colors:

- **Blue** (`#89b4fa`) - Links, info, forecasts
- **Green** (`#a6e3a1`) - Success, buys, profits
- **Red** (`#f38ba8`) - Errors, sells, losses
- **Yellow** (`#f9e2af`) - Warnings
- **Teal** (`#94e2d5`) - LED status, special states

## CSS Classes

### Layout & Containers

```jsx
// TUI Panel with border
<div className="tui-panel">
  <div className="tui-panel__header">Panel Title</div>
  Content here
</div>

// Panel with title bar (terminal window style)
<div className="tui-panel--titled">
  <div className="tui-panel__title-bar">
    <span>Window Title</span>
  </div>
  Content here
</div>
```

### Dividers

```jsx
// Single-line divider
<hr className="tui-divider" />

// Double-line divider (box-drawing style)
<hr className="tui-divider--double" />

// Vertical divider
<div className="tui-divider--vertical" />
```

### Tables

```jsx
<table className="tui-table tui-table--striped">
  <thead>
    <tr>
      <th>Column 1</th>
      <th>Column 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Data 1</td>
      <td>Data 2</td>
    </tr>
  </tbody>
</table>
```

Modifiers:

- `tui-table--striped` - Alternating row backgrounds
- `tui-table--hover` - Subtle hover effect on rows

### Buttons

```jsx
<button className="tui-button">Default</button>
<button className="tui-button tui-button--primary">Primary</button>
<button className="tui-button tui-button--success">Success</button>
<button className="tui-button tui-button--danger">Danger</button>
```

### Status Indicators

```jsx
<div className="tui-status">
  <span className="tui-status__indicator tui-status__indicator--success" />
  Running
</div>
```

Indicator variants:

- `--success` - Green
- `--error` - Red
- `--warning` - Yellow
- `--info` - Blue

### Code Blocks

```jsx
<pre className="tui-code">
  <code>Monospace code here</code>
</pre>
```

### Utility Classes

```jsx
// Sharp corners
<div className="tui-sharp">No border-radius</div>

// High contrast border
<div className="tui-border">1px solid surface1</div>

// Dense spacing
<div className="tui-dense">padding: 8px</div>

// Uppercase labels
<span className="tui-label">UPPERCASE TEXT</span>

// Monospace text
<span className="tui-mono">Monospace font</span>
```

## Component Styling

### Mantine Components (Auto-styled)

The following Mantine components are automatically styled with TUI aesthetics:

- **Card** - Sharp corners, mantle background, surface1 border
- **Paper** - Same as Card
- **Modal** - Sharp corners, mantle content, surface0 header
- **Drawer** - Same as Modal
- **Table** - Collapsed borders, surface0 headers, surface1 grid
- **Button** - Sharp corners, bold text
- **Input/Select** - Sharp corners, surface1 border
- **Switch** - Sharp thumb and track
- **Badge** - Sharp corners, bold text
- **Tooltip** - Sharp corners, crust background, bordered
- **Notification** - Sharp corners, bordered
- **Tabs** - Sharp corners, no gap between tabs

### AppShell (Auto-styled)

The main app shell has:

- Header with mantle background and surface1 bottom border
- Main content area with base background

## Animations

### Blink Cursor

```jsx
<span className="tui-blink">▊</span>
```

Useful for loading states or terminal cursor effects.

### Scanline Effect

```jsx
<div className="tui-scanline">
  Content with CRT scanline effect
</div>
```

Adds a subtle vertical scanline animation (optional, for extra TUI vibes).

## Custom Scrollbar

Apply `tui-scroll` class to enable TUI-styled scrollbars:

```jsx
<div className="tui-scroll" style={{ overflow: 'auto' }}>
  Scrollable content
</div>
```

## Design Principles

### 1. Information Density

Prefer showing more data in less space:

- Use 11-12px font for metadata
- Tight padding (4-8px)
- Minimal margins between related elements

### 2. Clear Hierarchy

Use color and weight to establish hierarchy:

- **Bold uppercase** for labels (0.75rem)
- Regular weight for body text (0.8125rem)
- Muted colors for secondary information

### 3. Visible Boundaries

Every panel, card, and section should have visible borders:

- Use `surface1` color for borders
- 1px solid style throughout
- No subtle or transparent borders

### 4. Consistent Spacing

Use the TUI spacing scale:

- `xs` (4px) - Tight inline spacing
- `sm` (8px) - Standard padding
- `md` (12px) - Section spacing
- `lg` (16px) - Large gaps
- `xl` (20px) - Major divisions

### 5. Monospace Throughout

Everything uses JetBrains Mono:

- Headings
- Body text
- Labels
- Data values

## Examples

### Status Bar

```jsx
<Group className="tui-panel" justify="space-between">
  <Group>
    <div className="tui-status">
      <span className="tui-status__indicator tui-status__indicator--success" />
      Market Open
    </div>
    <Text size="sm" className="tui-label">Portfolio: €125,432</Text>
  </Group>
  <Group>
    <Text size="xs" c="dimmed">Last sync: 2m ago</Text>
  </Group>
</Group>
```

### Data Table

```jsx
<table className="tui-table tui-table--striped">
  <thead>
    <tr>
      <th>Symbol</th>
      <th>Allocation</th>
      <th>Delta</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td className="tui-mono">AAPL</td>
      <td>12.5%</td>
      <td className="tui-label" style={{ color: 'var(--mantine-color-green-6)' }}>+2.3%</td>
    </tr>
  </tbody>
</table>
```

### Panel with Header

```jsx
<div className="tui-panel--titled">
  <div className="tui-panel__title-bar">
    <span>Portfolio Allocation</span>
  </div>
  <div style={{ padding: '12px' }}>
    Panel content here
  </div>
</div>
```

## Migration Notes

### Before → After

```jsx
// Before: Modern UI
<Card radius="sm" shadow="sm">
  <Text size="lg">Title</Text>
  <Group spacing="md">
    <Button radius="md">Action</Button>
  </Group>
</Card>

// After: TUI
<div className="tui-panel--titled">
  <div className="tui-panel__title-bar">
    <span>Title</span>
  </div>
  <div style={{ padding: '12px' }}>
    <Group gap="sm">
      <button className="tui-button tui-button--primary">Action</button>
    </Group>
  </div>
</div>
```

## Testing

To preview TUI styling:

```bash
cd web/
npm run dev
```

Visit <http://localhost:5173> to see the TUI theme in action.

## Future Enhancements

Potential additions:

- [ ] ASCII box-drawing character components
- [ ] CRT screen curvature effect (optional)
- [ ] Terminal color themes (Catppuccin Latte/Frappe/Macchiato)
- [ ] TUI form components (checkboxes, radio buttons)
- [ ] Progress bars with block characters
- [ ] Sparkline charts using Unicode blocks
