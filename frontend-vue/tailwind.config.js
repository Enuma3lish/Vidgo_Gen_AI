/** @type {import("tailwindcss").Config} */
const colors = {
  // Primary: Electric Cyan / Tech Blue
  primary: {
    50:  "#e0f8ff",
    100: "#b3eeff",
    200: "#80e2ff",
    300: "#4dd4f5",
    400: "#22c8f0",
    500: "#00b8e6",   // Main brand cyan
    600: "#0099cc",
    700: "#0077a8",
    800: "#005580",
    900: "#003350",
  },
  // Light tones
  light: {
    50:  "#ffffff",
    100: "#f0f8ff",
    200: "#e0f0ff",
    300: "#c8e4f8",
    400: "#a8ccec",
    500: "#88b4e0",
  },
  // Dark backgrounds (deep navy/charcoal)
  dark: {
    950: "#020817",   // Deepest navy
    900: "#0a1628",   // Deep navy
    800: "#0f1f3d",   // Navy
    700: "#162447",   // Dark navy
    600: "#1e3a5f",   // Medium navy
    500: "#2d5282",   // Blue-grey
    400: "#4a7bb5",   // Muted blue
    300: "#7aa8d4",   // Light blue-grey
    200: "#a8c8e8",   // Very light blue
    100: "#d0e4f5",   // Near white blue
  },
  accent: {
    cyan:          "#00d4f5",
    "cyan-light":  "#b3f0ff",
    "cyan-bg":     "#e0f8ff",
    blue:          "#3b82f6",
    "blue-light":  "#93c5fd",
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
    navy:   "#0f1f3d",
    blue:   "#162447",
    cyan:   "#0c2a3a",
    purple: "#1a1040",
    teal:   "#0c2a2a",
    dark:   "#0a1628",
    white:  "#ffffff",
    // Legacy aliases
    yellow: "#0f1f3d",
    orange: "#162447",
    pink:   "#1a1040",
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
        "card":       "0 4px 20px rgba(0,0,0,0.4)",
        "card-hover": "0 8px 40px rgba(0,184,230,0.25)",
        "btn":        "0 4px 15px rgba(0,184,230,0.35)",
        "glow-sm":    "0 0 15px rgba(0,184,230,0.4)",
        "glow":       "0 0 30px rgba(0,184,230,0.5)",
        "glow-lg":    "0 0 60px rgba(0,184,230,0.4)",
        "inner-glow": "inset 0 0 20px rgba(0,184,230,0.1)",
      },
      backgroundImage: {
        "tech-grid":     "linear-gradient(rgba(0,184,230,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(0,184,230,0.06) 1px, transparent 1px)",
        "hero-gradient": "linear-gradient(135deg, #020817 0%, #0a1628 40%, #0f1f3d 70%, #162447 100%)",
        "card-gradient": "linear-gradient(135deg, #0f1f3d 0%, #162447 100%)",
        "cyan-gradient": "linear-gradient(135deg, #00b8e6 0%, #0077a8 100%)",
        "blue-gradient": "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
        "glow-gradient": "radial-gradient(ellipse at center, rgba(0,184,230,0.15) 0%, transparent 70%)",
      },
    },
  },
  plugins: [],
}
