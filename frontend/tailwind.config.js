/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: { "2xl": "1280px" },
    },
    extend: {
      fontFamily: {
        display: ['"Cairo"', "system-ui", "sans-serif"],
        body: ['"Tajawal"', "system-ui", "sans-serif"],
      },
      colors: {
        border: "rgba(255,255,255,0.06)",
        input: "#1a1d24",
        ring: "#d4af37",
        background: "#0a0a0b",
        foreground: "#f8fafc",
        primary: {
          DEFAULT: "#d4af37",
          foreground: "#0a0a0b",
        },
        secondary: {
          DEFAULT: "#1a1d24",
          foreground: "#f8fafc",
        },
        destructive: {
          DEFAULT: "#f43f5e",
          foreground: "#f8fafc",
        },
        muted: {
          DEFAULT: "#1a1d24",
          foreground: "#94a3b8",
        },
        accent: {
          DEFAULT: "#d4af37",
          foreground: "#0a0a0b",
        },
        popover: {
          DEFAULT: "#121418",
          foreground: "#f8fafc",
        },
        card: {
          DEFAULT: "#121418",
          foreground: "#f8fafc",
        },
        gold: {
          50: "#fff7d6",
          400: "#fde047",
          500: "#d4af37",
          600: "#b08a25",
        },
      },
      borderRadius: {
        lg: "0.625rem",
        md: "calc(0.625rem - 2px)",
        sm: "calc(0.625rem - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
