export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        'eve-deep': '#020810', 'eve-panel': '#0a1628', 'eve-card': 'rgba(10,22,40,0.7)',
        'eve-gold': '#c9a84c', 'eve-cyan': '#00b4d8', 'eve-profit': '#2ecc71',
        'eve-danger': '#e74c3c', 'eve-warning': '#f39c12',
      },
      fontFamily: { display: ['Orbitron', 'monospace'], body: ['Noto Sans SC', 'sans-serif'] },
    },
  },
  plugins: [],
}
