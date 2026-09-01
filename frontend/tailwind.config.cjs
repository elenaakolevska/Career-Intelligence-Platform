/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        ink: '#1A2332',
        steel: '#2B5580',
        paper: '#FAFAF8',
        mist: '#EFF1EE',
        amber: '#C47B1A',
        coral: '#C45C4A',
      },
    },
  },
  plugins: [],
}
