/**
 * Mantine Theme Configuration
 *
 * Catppuccin color palettes with monospace fonts.
 * Switch flavors by changing the `activePalette` variable.
 *
 * Style Guide Reference (https://github.com/catppuccin/catppuccin/blob/main/docs/style-guide.md):
 *
 * Backgrounds:
 *   - Primary pane: Base
 *   - Secondary panes: Crust, Mantle
 *   - Surface elements: Surface 0/1/2
 *   - Overlay layers: Overlay 0/1/2
 *
 * Typography:
 *   - Body text & headlines: Text
 *   - Sub-headlines & labels: Subtext 0/1
 *   - Subtle/muted text: Overlay 1
 *   - Text on accent backgrounds: Base
 *
 * Semantic Colors:
 *   - Links & URLs: Blue
 *   - Success: Green
 *   - Warnings: Yellow
 *   - Errors: Red
 *   - Selection: Overlay 2 (20-30% opacity)
 *   - Cursor: Rosewater
 */
import { createTheme } from '@mantine/core';

// =============================================================================
// Catppuccin Palettes
// =============================================================================

const catppuccinLatte = {
  // Base colors (light theme)
  base: '#eff1f5',
  mantle: '#e6e9ef',
  crust: '#dce0e8',

  // Surface colors
  surface0: '#ccd0da',
  surface1: '#bcc0cc',
  surface2: '#acb0be',

  // Text colors
  text: '#4c4f69',
  subtext1: '#5c5f77',
  subtext0: '#6c6f85',

  // Overlay colors
  overlay0: '#9ca0b0',
  overlay1: '#8c8fa1',
  overlay2: '#7c7f93',

  // Accent colors
  blue: '#1e66f5',
  green: '#40a02b',
  red: '#d20f39',
  yellow: '#df8e1d',
  peach: '#fe640b',
  mauve: '#8839ef',
  teal: '#179299',
  sky: '#04a5e5',
  sapphire: '#209fb5',
  lavender: '#7287fd',
  pink: '#ea76cb',
  rosewater: '#dc8a78',
  flamingo: '#dd7878',
  maroon: '#e64553',
};

const catppuccinFrappe = {
  // Base colors
  base: '#303446',
  mantle: '#292c3c',
  crust: '#232634',

  // Surface colors
  surface0: '#414559',
  surface1: '#51576d',
  surface2: '#626880',

  // Text colors
  text: '#c6d0f5',
  subtext1: '#b5bfe2',
  subtext0: '#a5adce',

  // Overlay colors
  overlay0: '#737994',
  overlay1: '#838ba7',
  overlay2: '#949cbb',

  // Accent colors
  blue: '#8caaee',
  green: '#a6d189',
  red: '#e78284',
  yellow: '#e5c890',
  peach: '#ef9f76',
  mauve: '#ca9ee6',
  teal: '#81c8be',
  sky: '#99d1db',
  sapphire: '#85c1dc',
  lavender: '#babbf1',
  pink: '#f4b8e4',
  rosewater: '#f2d5cf',
  flamingo: '#eebebe',
  maroon: '#ea999c',
};

const catppuccinMacchiato = {
  // Base colors
  base: '#24273a',
  mantle: '#1e2030',
  crust: '#181926',

  // Surface colors
  surface0: '#363a4f',
  surface1: '#494d64',
  surface2: '#5b6078',

  // Text colors
  text: '#cad3f5',
  subtext1: '#b8c0e0',
  subtext0: '#a5adcb',

  // Overlay colors
  overlay0: '#6e738d',
  overlay1: '#8087a2',
  overlay2: '#939ab7',

  // Accent colors
  blue: '#8aadf4',
  green: '#a6da95',
  red: '#ed8796',
  yellow: '#eed49f',
  peach: '#f5a97f',
  mauve: '#c6a0f6',
  teal: '#8bd5ca',
  sky: '#91d7e3',
  sapphire: '#7dc4e4',
  lavender: '#b7bdf8',
  pink: '#f5bde6',
  rosewater: '#f4dbd6',
  flamingo: '#f0c6c6',
  maroon: '#ee99a0',
};

const catppuccinMocha = {
  // Base colors
  base: '#1e1e2e',
  mantle: '#181825',
  crust: '#11111b',

  // Surface colors
  surface0: '#313244',
  surface1: '#45475a',
  surface2: '#585b70',

  // Text colors
  text: '#cdd6f4',
  subtext1: '#bac2de',
  subtext0: '#a6adc8',

  // Overlay colors
  overlay0: '#6c7086',
  overlay1: '#7f849c',
  overlay2: '#9399b2',

  // Accent colors
  blue: '#89b4fa',
  green: '#a6e3a1',
  red: '#f38ba8',
  yellow: '#f9e2af',
  peach: '#fab387',
  mauve: '#cba6f7',
  teal: '#94e2d5',
  sky: '#89dceb',
  sapphire: '#74c7ec',
  lavender: '#b4befe',
  pink: '#f5c2e7',
  rosewater: '#f5e0dc',
  flamingo: '#f2cdcd',
  maroon: '#eba0ac',
};

// =============================================================================
// Active Palette Selection
// =============================================================================

// Change this to switch themes: catppuccinLatte, catppuccinFrappe, catppuccinMacchiato, catppuccinMocha
const activePalette = catppuccinMocha;

// Determine if this is a light theme (only Latte is light)
const isLightTheme = activePalette === catppuccinLatte;

// =============================================================================
// Theme Generator
// =============================================================================

const createCatppuccinTheme = (palette) => createTheme({
  primaryColor: 'blue',
  defaultRadius: 'sm',

  fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace',

  fontSizes: {
    xs: '0.75rem',
    sm: '0.875rem',
    md: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
  },

  headings: {
    fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace',
  },

  colors: {
    dark: [
      palette.text,
      palette.subtext1,
      palette.subtext0,
      palette.overlay2,
      palette.overlay1,
      palette.overlay0,
      palette.surface0,
      palette.base,
      palette.mantle,
      palette.crust,
    ],
    blue: [
      palette.blue,
      palette.sapphire,
      palette.sky,
      palette.blue,
      palette.blue,
      palette.blue,
      palette.blue,
      palette.blue,
      palette.blue,
      palette.blue,
    ],
    green: Array(10).fill(palette.green),
    red: [
      palette.red,
      palette.maroon,
      ...Array(8).fill(palette.red),
    ],
    yellow: [
      palette.yellow,
      palette.peach,
      ...Array(8).fill(palette.yellow),
    ],
    gray: [
      palette.text,
      palette.subtext1,
      palette.subtext0,
      palette.overlay2,
      palette.overlay1,
      palette.overlay0,
      palette.surface2,
      palette.surface1,
      palette.surface0,
      palette.base,
    ],
    teal: Array(10).fill(palette.teal),
    violet: [
      palette.mauve,
      palette.lavender,
      ...Array(8).fill(palette.mauve),
    ],
  },

  other: {
    palette,
  },

  components: {
    Card: {
      styles: {
        root: {
          // Style guide: secondary panes use Mantle
          backgroundColor: palette.mantle,
          borderColor: palette.surface0,
        },
      },
    },
    AppShell: {
      styles: {
        main: {
          // Style guide: primary background pane uses Base
          backgroundColor: palette.base,
        },
        header: {
          // Style guide: secondary panes use Crust/Mantle
          backgroundColor: palette.mantle,
          borderColor: palette.surface0,
        },
      },
    },
    // Style guide: selection backgrounds use Overlay 2 at 20-30% opacity
    // Style guide: text on accent backgrounds should use Base
  },
});

// =============================================================================
// Exports
// =============================================================================

export const theme = createCatppuccinTheme(activePalette);
export const colorScheme = isLightTheme ? 'light' : 'dark';

// Export active palette for direct color access in components
export { activePalette as catppuccin };

// Export all palettes for reference
export const palettes = {
  latte: catppuccinLatte,
  frappe: catppuccinFrappe,
  macchiato: catppuccinMacchiato,
  mocha: catppuccinMocha,
};
