/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/**/*.js"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Light mode colors
        primary: '#94A3B8',      // Soft slate blue
        secondary: '#E2E8F0',    // Light gray-blue
        accent: '#CBD5E1',       // Subtle blue-gray
        highlight: '#BFDBFE',    // Soft pastel blue
        background: '#F8FAFC',   // Off-white
        surface: '#F1F5F9',      // Subtle gray
        text: '#334155',         // Dark slate

        // Dark Mode colors - flattened structure for easier use with Tailwind
        'dark-primary': '#64748B',    // Lightened primary
        'dark-secondary': '#475569',  // Lightened secondary
        'dark-accent': '#94A3B8',     // Brightened accent
        'dark-highlight': '#93C5FD',  // Brighter highlight
        'dark-background': '#0F172A', // Deep navy blue
        'dark-surface': '#1E293B',    // Dark blue-gray
        'dark-text': '#F1F5F9',       // Much lighter text (almost white)
      },
    },
  },
  plugins: [],
}