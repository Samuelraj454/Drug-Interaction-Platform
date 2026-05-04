/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0b",
        card: "#18181b",
        border: "#27272a",
        primary: "#3b82f6",
        secondary: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444",
        contraindicated: "#000000",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
