/** @type {import("tailwindcss").Config} */
const colors = {
  // Legacy amber brand — preserved so existing pages don't regress while
  // the dark-blue/violet brand below rolls out. New views should reach for
  // `brand-*` tokens; existing amber usages can migrate incrementally.
  primary: {
    50:  "#fffbeb",
    100: "#fef3c7",
    200: "#fde68a",
    300: "#fcd34d",
    400: "#fbbf24",
    500: "#f59e0b",
    600: "#d97706",
    700: "#b45309",
    800: "#92400e",
    900: "#78350f",
  },

  // ── 2026-05-25 brand refresh (piapi.ai + reroom.ai inspiration) ──
  // The site sells AI tools to small e-commerce / individual merchants;
  // the warm amber palette read as "consumer toy" rather than "pro SaaS
  // tool". Pricing.vue + RoomRedesign.vue were already using these
  // colours inline — promoting them to the config so every new view can
  // reach for the same tokens without re-hardcoding hex.
  brand: {
    blue:        "#1677ff",          // primary CTAs, links, focus rings
    "blue-soft": "#3b8aff",          // hover / lighter accents
    "blue-bg":   "rgba(22,119,255,0.10)", // subtle background tint
    violet:      "#7c3aed",          // secondary accent — premium tier badges
    "violet-soft": "#a78bfa",
    "violet-bg": "rgba(124,58,237,0.10)",
    gradient:    "linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)",
  },

  // Cool dark UI surface — replaces the warm-charcoal grays for any view
  // that opts into the brand refresh. Keeps the original `dark.*` ramp
  // for backward compat with the amber theme.
  surface: {
    page:     "#09090b",   // body bg
    section:  "#0c0c12",   // section bg
    panel:    "#141420",   // card / panel bg (matches Pricing.vue)
    "panel-hover": "#1a1a28",
    elevated: "#1f1f30",   // hover / elevated surfaces
    border:   "rgba(255,255,255,0.06)",  // subtle hairline
    "border-strong": "rgba(255,255,255,0.12)",
  },
  text: {
    primary: "#f5f5fa",    // headings + body
    secondary: "#c2c2d5",  // softer body
    muted:   "#9494b0",    // labels / captions
    subtle:  "#6b6b8a",    // section-eyebrow text (matches ProductScene hub)
  },

  // Warm charcoal dark theme (legacy — kept for backward compat).
  dark: {
    950: "#080808",
    900: "#0c0c0c",
    850: "#111111",
    800: "#161616",
    750: "#1c1c1c",
    700: "#242424",
    600: "#2a2a2a",
    500: "#44403c",
    400: "#78716c",
    300: "#a8a29e",
    200: "#d6d3d1",
    100: "#e7e5e4",
    50:  "#fafaf9",
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
    blue:           "#1677ff",
    "blue-light":   "#3b8aff",
    "blue-bg":      "rgba(22,119,255,0.10)",
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
    panel:  "#141420",   // brand-refresh card
    edge:   "rgba(255,255,255,0.06)",
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
        // Brand-refresh shadows (cool blue glow).
        "brand-card":       "0 8px 28px rgba(0,0,0,0.55)",
        "brand-card-hover": "0 12px 36px rgba(22,119,255,0.18)",
        "brand-btn":        "0 4px 16px rgba(22,119,255,0.35)",
        "brand-glow-sm":    "0 0 16px rgba(22,119,255,0.30)",
        "brand-glow":       "0 0 36px rgba(22,119,255,0.28)",
      },
      backgroundImage: {
        "hero-gradient":  "radial-gradient(ellipse at 50% -10%, rgba(245,158,11,0.06) 0%, transparent 65%), linear-gradient(180deg, #0c0c0c 0%, #0f0f0f 100%)",
        "card-gradient":  "linear-gradient(145deg, #1c1c1c 0%, #212121 100%)",
        "amber-gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "amber-teal":     "linear-gradient(135deg, #f59e0b 0%, #0d9488 100%)",
        "glow-gradient":  "radial-gradient(ellipse at center, rgba(245,158,11,0.10) 0%, transparent 70%)",
        "mesh-gradient":  "radial-gradient(at 30% 20%, rgba(245,158,11,0.04) 0px, transparent 50%), radial-gradient(at 80% 10%, rgba(13,148,136,0.03) 0px, transparent 50%)",
        // Brand-refresh gradients (cool blue + violet).
        "brand-hero":    "radial-gradient(ellipse at 50% -10%, rgba(22,119,255,0.10) 0%, transparent 65%), linear-gradient(180deg, #09090b 0%, #0c0c12 100%)",
        "brand-card":    "linear-gradient(145deg, #141420 0%, #1a1a28 100%)",
        "brand-cta":     "linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)",
        "brand-cta-hover": "linear-gradient(135deg, #3b8aff 0%, #a78bfa 100%)",
        "brand-mesh":    "radial-gradient(at 20% 10%, rgba(22,119,255,0.07) 0px, transparent 55%), radial-gradient(at 80% 30%, rgba(124,58,237,0.05) 0px, transparent 55%)",
      },
    },
  },
  plugins: [],
}
