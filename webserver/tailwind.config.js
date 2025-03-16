module.exports = {
  darkMode: 'class',
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        // Light mode colors remain the same
        primary: '#94A3B8',      // Soft slate blue
        secondary: '#E2E8F0',    // Light gray-blue
        accent: '#CBD5E1',       // Subtle blue-gray
        highlight: '#BFDBFE',    // Soft pastel blue
        background: '#F8FAFC',   // Off-white
        surface: '#F1F5F9',      // Subtle gray
        text: {
          primary: '#334155',    // Dark slate
          secondary: '#64748B',  // Medium slate
        },

        // Dark Mode - Adjusted for better readability
        dark: {
          primary: '#64748B',    // Lightened primary
          secondary: '#475569',  // Lightened secondary
          accent: '#94A3B8',     // Brightened accent
          highlight: '#93C5FD',  // Brighter highlight
          background: '#0F172A', // Deep navy blue (keep this)
          surface: '#1E293B',    // Dark blue-gray (keep this)
          text: {
            primary: '#F1F5F9',  // Much lighter text (almost white)
            secondary: '#CBD5E1', // Light gray-blue for secondary text
          },
          input: {
            background: '#334155', // Lighter background for input fields
            text: '#F8FAFC',      // Very light text for inputs
          }
        },
      },
    },
  },
  plugins: [],
};