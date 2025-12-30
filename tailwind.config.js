/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./static/*.html",
    "./static/**/*.html",
    "./static/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontSize: {
        'xs': ['0.875rem', { lineHeight: '1.5' }],    // 14px - minimum size
        'sm': ['0.9375rem', { lineHeight: '1.5' }],   // 15px
        'base': ['1rem', { lineHeight: '1.5' }],      // 16px
        'lg': ['1.125rem', { lineHeight: '1.5' }],   // 18px
        'xl': ['1.25rem', { lineHeight: '1.5' }],    // 20px
        '2xl': ['1.5rem', { lineHeight: '1.5' }],    // 24px
      },
      colors: {
        surface: { DEFAULT: '#1f2937', hover: '#374151' },
        eu: '#3b82f6',
        asia: '#ef4444',
        us: '#22c55e',
      }
    }
  },
  plugins: [],
}
