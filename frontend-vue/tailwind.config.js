/** @type {import('tailwindcss').Config} */
const colors = {
  // Primary Purple-Blue (from ARCHITECTURE_FINAL Dark Tech Theme)
  primary: {
    50: '#f5f3ff',
    100: '#ede9fe',
    200: '#ddd6fe',
    300: '#c4b5fd',
    400: '#a78bfa',
    500: '#8b5cf6',  // Main purple
    600: '#7c3aed',
    700: '#6d28d9',
    800: '#5b21b6',
    900: '#4c1d95',
  },
  // Dark backgrounds (from ARCHITECTURE_FINAL)
  dark: {
    950: '#0f172a',  // --bg-secondary
    900: '#1e1b4b',  // --bg-primary (Deep purple-blue)
    800: '#1e293b',  // Card backgrounds
    700: '#2d2a5e',  // --bg-card
    600: '#3d3a6e',  // --bg-card-hover
    500: '#475569',
  },
  // Accent colors (from ARCHITECTURE_FINAL)
  accent: {
    cyan: '#06b6d4',
    pink: '#ec4899',
    orange: '#f97316',
    green: '#10b981',
    red: '#ef4444',
    blue: '#3b82f6',
  },
  // Text colors (from ARCHITECTURE_FINAL)
  text: {
    primary: '#ffffff',
    secondary: '#a5a3c7',
    muted: '#6b6b8d',
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
        sans: ['Inter', 'Noto Sans TC', 'system-ui', 'sans-serif'],
        zh: ['Noto Sans TC', 'system-ui', 'sans-serif'],
        ja: ['Noto Sans JP', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      backgroundImage: {
        // Gradients from ARCHITECTURE_FINAL
        'gradient-hero': 'linear-gradient(135deg, #7c3aed 0%, #ec4899 50%, #06b6d4 100%)',
        'gradient-cta': 'linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)',
        'gradient-highlight': 'linear-gradient(90deg, #f97316 0%, #ec4899 100%)',
        'gradient-dark': 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)',
        'gradient-card': 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%)',
        // Feature card gradient bars
        'gradient-blue': 'linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%)',
        'gradient-orange': 'linear-gradient(90deg, #f97316 0%, #ea580c 100%)',
        'gradient-green': 'linear-gradient(90deg, #10b981 0%, #059669 100%)',
        'gradient-pink': 'linear-gradient(90deg, #ec4899 0%, #db2777 100%)',
        'gradient-cyan': 'linear-gradient(90deg, #06b6d4 0%, #0891b2 100%)',
        'gradient-red': 'linear-gradient(90deg, #ef4444 0%, #dc2626 100%)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(139, 92, 246, 0.2)' },
          '100%': { boxShadow: '0 0 40px rgba(139, 92, 246, 0.4)' },
        },
      },
      boxShadow: {
        'glow-sm': '0 0 15px rgba(139, 92, 246, 0.3)',
        'glow': '0 0 30px rgba(139, 92, 246, 0.4)',
        'glow-lg': '0 0 50px rgba(139, 92, 246, 0.5)',
      },
    },
  },
  plugins: [],
}
