/** @type {import("tailwindcss").Config} */
const colors = {
  // Primary: Amber (Carbon & Ember brand)
  primary: {
    50:  "#fffbeb",
    100: "#fef3c7",
    200: "#fde68a",
    300: "#fcd34d",
    400: "#fbbf24",
    500: "#f59e0b",   // Main brand amber
    600: "#d97706",
    700: "#b45309",
    800: "#92400e",
    900: "#78350f",
  },
  // Warm charcoal dark theme
  dark: {
    950: "#080808",
    900: "#0c0c0c",   // Page bg
    850: "#111111",   // Section bg
    800: "#161616",   // Section alt
    750: "#1c1c1c",   // Card bg
    700: "#242424",   // Card hover
    600: "#2a2a2a",   // Elevated
    500: "#44403c",
    400: "#78716c",
    300: "#a8a29e",   // Muted text
    200: "#d6d3d1",   // Secondary text
    100: "#e7e5e4",
    50:  "#fafaf9",   // Headings / primary text
  },
  accent: {
    teal:           "#0d9488",
    "teal-light":   "#2dd4bf",
    "teal-bg":      "rgba(13,148,136,0.08)",
    amber:          "#f59e0b",
    "amber-light":  "#fbbf24",
    "amber-bg":     "rgba(245,158,11,0.10)",
    violet:         "#7c3aed",
    "violet-light": "#a78bfa",
    "violet-bg":    "rgba(124,58,237,0.10)",
    green:          "#10b981",
    orange:         "#f97316",
    red:            "#ef4444",
    sky:            "#38bdf8",
    pink:           "#ec4899",
  },
  card: {
    dark:   "#1c1c1c",
    darker: "#161616",
    warm:   "#1e1c18",
    amber:  "#1f1c14",
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
        sans:    ["DM Sans", "Noto Sans TC", "system-ui", "sans-serif"],
        display: ["Syne", "Noto Sans TC", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        zh:      ["Noto Sans TC", "system-ui", "sans-serif"],
      },
      borderRadius: {
        "xl":  "8px",
        "2xl": "8px",
        "3xl": "12px",
        "4xl": "16px",
      },
      animation: {
        "fade-in":    "fadeIn 0.3s ease-out",
        "slide-up":   "slideUp 0.4s ease-out",
        "float":      "float 6s ease-in-out infinite",
        "marquee":    "marquee 30s linear infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "shimmer":    "shimmer 2s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%":   { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-8px)" },
        },
        marquee: {
          "0%":   { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      boxShadow: {
        "card":       "0 4px 24px rgba(0,0,0,0.5)",
        "card-hover": "0 8px 40px rgba(245,158,11,0.12)",
        "btn":        "0 4px 15px rgba(245,158,11,0.30)",
        "glow-sm":    "0 0 15px rgba(245,158,11,0.25)",
        "glow":       "0 0 30px rgba(245,158,11,0.30)",
        "glow-lg":    "0 0 60px rgba(245,158,11,0.20)",
        "inner-glow": "inset 0 0 20px rgba(245,158,11,0.05)",
        "dark-lg":    "0 8px 32px rgba(0,0,0,0.65)",
        "dark-xl":    "0 16px 48px rgba(0,0,0,0.75)",
      },
      backgroundImage: {
        "hero-gradient":  "radial-gradient(ellipse at 50% -10%, rgba(245,158,11,0.06) 0%, transparent 65%), linear-gradient(180deg, #0c0c0c 0%, #0f0f0f 100%)",
        "card-gradient":  "linear-gradient(145deg, #1c1c1c 0%, #212121 100%)",
        "amber-gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "amber-teal":     "linear-gradient(135deg, #f59e0b 0%, #0d9488 100%)",
        "glow-gradient":  "radial-gradient(ellipse at center, rgba(245,158,11,0.10) 0%, transparent 70%)",
        "mesh-gradient":  "radial-gradient(at 30% 20%, rgba(245,158,11,0.04) 0px, transparent 50%), radial-gradient(at 80% 10%, rgba(13,148,136,0.03) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
}
