/** @type {import("tailwindcss").Config} */
const colors = {
  // Primary: Blue (PicCopilot accent on dark bg)
  primary: {
    50:  "#eff6ff",
    100: "#dbeafe",
    200: "#bfdbfe",
    300: "#93c5fd",
    400: "#60a5fa",
    500: "#1677ff",   // Main brand blue
    600: "#0958d9",
    700: "#1d4ed8",
    800: "#1e40af",
    900: "#1e3a8a",
  },
  // Dark theme palette
  dark: {
    950: "#09090b",   // Deepest bg
    900: "#0a0a0f",   // Page bg
    850: "#0f0f17",   // Section bg alt
    800: "#141420",   // Card bg
    750: "#18182a",   // Card bg hover
    700: "#1e1e32",   // Elevated surface
    600: "#2a2a42",   // Border
    500: "#3a3a55",   // Subtle border
    400: "#6b6b8a",   // Muted text
    300: "#9494b0",   // Secondary text
    200: "#c4c4d8",   // Primary text
    100: "#e8e8f0",   // Bright text
    50:  "#f5f5fa",   // Headings
  },
  accent: {
    cyan:          "#00d4f5",
    "cyan-light":  "#b3f0ff",
    "cyan-bg":     "rgba(0,212,245,0.08)",
    blue:          "#1677ff",
    "blue-light":  "#69b1ff",
    "blue-bg":     "rgba(22,119,255,0.12)",
    indigo:        "#6366f1",
    purple:        "#a855f7",
    "purple-light":"#d8b4fe",
    "purple-bg":   "rgba(168,85,247,0.1)",
    teal:          "#14b8a6",
    green:         "#10b981",
    orange:        "#f97316",
    "orange-light":"rgba(249,115,22,0.15)",
    red:           "#ef4444",
    yellow:        "#eab308",
    pink:          "#ec4899",
  },
  card: {
    dark:   "#141420",
    darker: "#0f0f17",
    navy:   "#0f1830",
    blue:   "#101828",
    purple: "#14102a",
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
        "shimmer": "shimmer 2s linear infinite",
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
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      boxShadow: {
        "card":       "0 4px 24px rgba(0,0,0,0.4)",
        "card-hover": "0 8px 40px rgba(22,119,255,0.2)",
        "btn":        "0 4px 15px rgba(22,119,255,0.35)",
        "glow-sm":    "0 0 15px rgba(22,119,255,0.3)",
        "glow":       "0 0 30px rgba(22,119,255,0.4)",
        "glow-lg":    "0 0 60px rgba(22,119,255,0.3)",
        "inner-glow": "inset 0 0 20px rgba(22,119,255,0.08)",
        "dark-lg":    "0 8px 32px rgba(0,0,0,0.6)",
        "dark-xl":    "0 16px 48px rgba(0,0,0,0.7)",
      },
      backgroundImage: {
        "hero-gradient":   "linear-gradient(135deg, #09090b 0%, #0a0a1a 40%, #0f1830 70%, #141420 100%)",
        "card-gradient":   "linear-gradient(135deg, #141420 0%, #18182a 100%)",
        "blue-gradient":   "linear-gradient(135deg, #1677ff 0%, #0958d9 100%)",
        "purple-gradient": "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
        "glow-gradient":   "radial-gradient(ellipse at center, rgba(22,119,255,0.12) 0%, transparent 70%)",
        "mesh-gradient":   "radial-gradient(at 40% 20%, rgba(22,119,255,0.08) 0px, transparent 50%), radial-gradient(at 80% 0%, rgba(99,102,241,0.06) 0px, transparent 50%), radial-gradient(at 0% 50%, rgba(22,119,255,0.04) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
}
