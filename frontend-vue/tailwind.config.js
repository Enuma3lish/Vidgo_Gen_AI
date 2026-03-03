/** @type {import("tailwindcss").Config} */
const colors = {
  primary: {
    50: "#f9ffe0",
    100: "#f0ffb3",
    200: "#e4ff80",
    300: "#d4f06b",
    400: "#c8e840",
    500: "#b8d400",
    600: "#9ab800",
    700: "#7a9200",
    800: "#5c6e00",
    900: "#3d4900",
  },
  light: {
    50: "#ffffff",
    100: "#fafff0",
    200: "#f5ffe0",
    300: "#edffc0",
    400: "#e4f5a0",
    500: "#d8ec80",
  },
  dark: {
    950: "#0a0a0a",
    900: "#111111",
    800: "#1a1a1a",
    700: "#222222",
    600: "#333333",
    500: "#444444",
    400: "#666666",
    300: "#888888",
    200: "#aaaaaa",
    100: "#cccccc",
  },
  accent: {
    purple: "#c4a8ff",
    "purple-light": "#ede0ff",
    "purple-bg": "#f0e8ff",
    orange: "#ff6b2b",
    "orange-light": "#fff0e8",
    cyan: "#00d4e8",
    green: "#00c48c",
    yellow: "#ffd600",
    pink: "#ff4d8d",
    red: "#ef4444",
    blue: "#3b82f6",
  },
  card: {
    yellow: "#d4f06b",
    purple: "#e8d5ff",
    orange: "#ffd4b3",
    blue: "#d0e8ff",
    pink: "#ffd0e8",
    white: "#ffffff",
    dark: "#1a1a1a",
  }
}

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors,
      ringColor: colors,
      ringOffsetColor: colors,
      fontFamily: {
        sans: ["Inter", "Noto Sans TC", "system-ui", "sans-serif"],
        zh: ["Noto Sans TC", "system-ui", "sans-serif"],
      },
      borderRadius: {
        "xl": "12px",
        "2xl": "16px",
        "3xl": "24px",
        "4xl": "32px",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "float": "float 6s ease-in-out infinite",
        "marquee": "marquee 30s linear infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      boxShadow: {
        "card": "0 4px 20px rgba(0, 0, 0, 0.08)",
        "card-hover": "0 8px 40px rgba(0, 0, 0, 0.15)",
        "btn": "0 4px 15px rgba(0, 0, 0, 0.2)",
        "glow-sm": "0 0 15px rgba(184, 212, 0, 0.3)",
        "glow": "0 0 30px rgba(184, 212, 0, 0.4)",
      },
    },
  },
  plugins: [],
}
