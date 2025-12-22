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
