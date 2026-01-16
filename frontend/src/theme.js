/**
 * Mantine Theme Configuration
 *
 * Defines the visual theme for the Sentinel frontend application.
 * Uses the Catppuccin Mocha color palette for a cohesive dark theme.
 *
 * Theme Features:
 * - Catppuccin Mocha color palette (dark, warm, pastel colors)
 * - Monospace font stack (JetBrains Mono, Fira Code, etc.) for terminal aesthetic
 * - Dark theme optimized for long viewing sessions
 * - Semantic color mappings (blue=primary, green=success, red=error, etc.)
 *
 * Color Palette Reference:
 * https://catppuccin.com/palette
 */
import { createTheme } from '@mantine/core';

/**
 * Catppuccin Mocha color palette
 *
 * A warm, dark color scheme with pastel accents.
 * Provides a cohesive set of colors for backgrounds, text, and UI elements.
 *
 * @see https://catppuccin.com/palette
 */
const catppuccinMocha = {
  // Base colors - background layers (darkest to lightest)
  base: '#1e1e2e',      // Base background (main app background)
  mantle: '#181825',     // Secondary background (cards, panels)
  crust: '#11111b',      // Tertiary background (deepest layer)

  // Surface colors - interactive elements (lighter to darker)
  surface0: '#313244',   // Surface 0 (borders, dividers)
  surface1: '#45475a',   // Surface 1 (hover states)
  surface2: '#585b70',   // Surface 2 (active states)

  // Text colors - content hierarchy (lightest to darkest)
  text: '#cdd6f4',       // Primary text (main content)
  subtext1: '#bac2de',   // Secondary text (labels, captions)
  subtext0: '#a6adc8',   // Tertiary text (disabled, muted)

  // Overlay colors - semi-transparent overlays
  overlay0: '#6c7086',   // Overlay 0 (subtle overlays)
  overlay1: '#7f849c',   // Overlay 1 (medium overlays)
  overlay2: '#9399b2',   // Overlay 2 (strong overlays)

  // Accent colors - semantic and decorative colors
  blue: '#89b4fa',       // Blue (primary actions, links)
  green: '#a6e3a1',      // Green (success, positive)
  red: '#f38ba8',        // Red (error, danger, negative)
  yellow: '#f9e2af',     // Yellow (warning, caution)
  peach: '#fab387',      // Peach (warm accent)
  mauve: '#cba6f7',      // Mauve (purple accent)
  teal: '#94e2d5',       // Teal (info, cool accent)
  sky: '#89dceb',        // Sky (light blue)
  sapphire: '#74c7ec',   // Sapphire (bright blue)
  lavender: '#b4befe',   // Lavender (light purple)
  pink: '#f5c2e7',       // Pink (warm accent)
  rosewater: '#f5e0dc',  // Rosewater (warm neutral)
  flamingo: '#f2cdcd',   // Flamingo (warm pink)
  maroon: '#eba0ac',     // Maroon (dark red)
};

/**
 * Mantine theme configuration
 *
 * Creates a custom theme based on Catppuccin Mocha palette with:
 * - Monospace fonts for terminal/code aesthetic
 * - Dark color scheme optimized for financial data display
 * - Semantic color mappings for consistent UI patterns
 *
 * @type {Object} theme - Mantine theme object
 */
export const theme = createTheme({
  /**
   * Primary color used for main actions and links
   */
  primaryColor: 'blue',

  /**
   * Default border radius for components
   * Smaller radius ('sm') creates a more terminal/technical aesthetic
   */
  defaultRadius: 'sm',

  /**
   * Font family stack - monospace fonts for code/terminal aesthetic
   * Falls back through multiple monospace fonts for cross-platform compatibility
   */
  fontFamily: '"JetBrains Mono", "Fira Code", "IBM Plex Mono", "Source Code Pro", "Consolas", "Monaco", "Courier New", monospace',

  /**
   * Font size scale
   * Provides consistent typography sizing throughout the application
   */
  fontSizes: {
    xs: '0.875rem',   // 14px - small text, captions
    sm: '1rem',       // 16px - body text, default
    md: '1.125rem',   // 18px - emphasized text
    lg: '1.25rem',    // 20px - subheadings
    xl: '1.5rem',     // 24px - headings
  },

  /**
   * Heading font configuration
   * Uses same monospace font stack as body text for consistency
   */
  headings: {
    fontFamily: '"JetBrains Mono", "Fira Code", "IBM Plex Mono", "Source Code Pro", "Consolas", "Monaco", "Courier New", monospace',
  },

  /**
   * Default gradient for gradient components
   * Blue to mauve gradient at 45 degrees
   */
  defaultGradient: {
    from: catppuccinMocha.blue,
    to: catppuccinMocha.mauve,
    deg: 45,
  },
  /**
   * Color palette mappings
   *
   * Mantine uses arrays of 10 colors per palette, where:
   * - Index 0 is typically the lightest/most saturated
   * - Higher indices are darker/more muted
   * - Index 6-9 are commonly used for backgrounds and borders
   */
  colors: {
    /**
     * Dark theme color palette
     * Mapped from Catppuccin Mocha for consistent dark theme
     * Used for backgrounds, borders, and text in dark mode
     */
    dark: [
      catppuccinMocha.text,        // 0 - lightest text (primary content)
      catppuccinMocha.subtext1,    // 1 - secondary text
      catppuccinMocha.subtext0,    // 2 - tertiary text
      catppuccinMocha.overlay2,    // 3 - strong overlays
      catppuccinMocha.overlay1,    // 4 - medium overlays
      catppuccinMocha.overlay0,    // 5 - subtle overlays
      catppuccinMocha.surface0,    // 6 - borders, dividers
      catppuccinMocha.base,        // 7 - panels, cards
      catppuccinMocha.mantle,      // 8 - secondary background
      catppuccinMocha.crust,       // 9 - darkest background (main app background)
    ],
    /**
     * Blue color palette (primary color)
     * Used for primary actions, links, and important UI elements
     */
    blue: [
      catppuccinMocha.blue,      // 0 - primary blue
      catppuccinMocha.sapphire,  // 1 - bright blue variant
      catppuccinMocha.sky,       // 2 - light blue variant
      catppuccinMocha.blue,      // 3-9 - consistent blue for all shades
      catppuccinMocha.blue,
      catppuccinMocha.blue,
      catppuccinMocha.blue,
      catppuccinMocha.blue,
      catppuccinMocha.blue,
      catppuccinMocha.blue,
    ],

    /**
     * Green color palette (success)
     * Used for success messages, positive indicators, profitable trades
     */
    green: [
      catppuccinMocha.green,     // 0-9 - consistent green for all shades
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
      catppuccinMocha.green,
    ],

    /**
     * Red color palette (error/danger)
     * Used for errors, warnings, negative indicators, losses
     */
    red: [
      catppuccinMocha.red,       // 0 - primary red
      catppuccinMocha.maroon,    // 1 - dark red variant
      catppuccinMocha.red,       // 2-9 - consistent red for all shades
      catppuccinMocha.red,
      catppuccinMocha.red,
      catppuccinMocha.red,
      catppuccinMocha.red,
      catppuccinMocha.red,
      catppuccinMocha.red,
      catppuccinMocha.red,
    ],

    /**
     * Yellow color palette (warning)
     * Used for warnings, caution indicators, attention-grabbing elements
     */
    yellow: [
      catppuccinMocha.yellow,    // 0 - primary yellow
      catppuccinMocha.peach,      // 1 - warm peach variant
      catppuccinMocha.yellow,     // 2-9 - consistent yellow for all shades
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
      catppuccinMocha.yellow,
    ],

    /**
     * Gray color palette (neutral)
     * Used for neutral text, borders, and backgrounds
     * Mapped from text and surface colors for natural grays
     */
    gray: [
      catppuccinMocha.text,      // 0 - lightest (primary text)
      catppuccinMocha.subtext1,  // 1 - secondary text
      catppuccinMocha.subtext0,  // 2 - tertiary text
      catppuccinMocha.overlay2,  // 3 - strong overlay
      catppuccinMocha.overlay1,  // 4 - medium overlay
      catppuccinMocha.overlay0,  // 5 - subtle overlay
      catppuccinMocha.surface2,  // 6 - surface 2
      catppuccinMocha.surface1,  // 7 - surface 1
      catppuccinMocha.surface0,  // 8 - surface 0
      catppuccinMocha.base,      // 9 - base background
    ],

    /**
     * Teal color palette (info)
     * Used for informational messages and neutral accent colors
     */
    teal: [
      catppuccinMocha.teal,      // 0-9 - consistent teal for all shades
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
      catppuccinMocha.teal,
    ],

    /**
     * Violet color palette (special)
     * Used for special accents and decorative elements
     */
    violet: [
      catppuccinMocha.mauve,     // 0 - primary mauve
      catppuccinMocha.lavender,  // 1 - light lavender variant
      catppuccinMocha.mauve,     // 2-9 - consistent mauve for all shades
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
      catppuccinMocha.mauve,
    ],
  },

  /**
   * Custom theme properties
   * Additional properties accessible via theme.other
   */
  other: {
    /**
     * Direct access to Catppuccin Mocha color palette
     * Allows components to use specific Catppuccin colors directly
     * Usage: theme.other.catppuccin.blue, theme.other.catppuccin.mauve, etc.
     */
    catppuccin: catppuccinMocha,
  },
});
