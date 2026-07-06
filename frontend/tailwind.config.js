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
        ring: "#fafafa", 
        background: "#0a0a0b",
        foreground: "#f8fafc",
        // درجات تفاعلية للخلفيات المخصصة لتعطي عمق ثلاثي الأبعاد
        surface: {
          DEFAULT: "#111317",
          soft: "#181a20",
          bright: "#22262f",
        },
        primary: {
          DEFAULT: "#fafafa", // الأبيض العاجي الفخم للـ UI العام
          foreground: "#0a0a0b",
        },
        // درجات فضية ملكية هادئة (مستخدمة بدل الذهبي للأوسمة والعناصر المميزة)
        royalGold: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#b8c3d1",
          500: "#d7e0ea",
          600: "#a8b4c4",
          700: "#7f8da0",
          800: "#5f6b7d",
          900: "#424b58",
          low: "rgba(203, 213, 225, 0.08)", // لمسة فضية خفيفة جداً للخلفيات
          muted: "#a4b0bf",                 // درجة مطفية للحدود والنصوص الثانوية
          DEFAULT: "#d7e0ea",               // فضي فاتح أساسي
          bright: "#eef3f8",                // إبراز بسيط جداً للـ Hover
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
          DEFAULT: "#fafafa", 
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
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e5ebf2",
          300: "#d6dee8",
          400: "#c6d0dc",
          500: "#e8edf3",
          600: "#c2ccd8",
          700: "#94a1b2",
        },
      },
      borderRadius: {
        lg: "0.625rem",
        md: "calc(0.625rem - 2px)",
        sm: "calc(0.625rem - 4px)",
      },
      // التأثيرات الحركية والتفاعلية المنوعة لتعطي المنصة حياة وحماس
      keyframes: {
        // 1. تأثير توهج نبضي مخصص للبطاقات الذهبية والرتب المتميزة
        royalGlow: {
          "0%, 100%": {
            "box-shadow": "0 0 0 1px rgba(203,213,225,0.24), 0 0 10px rgba(203,213,225,0.05)",
          },
          "50%": {
            "box-shadow": "0 0 0 2px rgba(203,213,225,0.4), 0 0 14px rgba(203,213,225,0.16)",
          },
        },
        // 2. توهج نيون أبيض عاجي ناعم للعناصر والأزرار العامة
        goldGlow: {
          "0%, 100%": {
            "box-shadow": "0 0 0 2px rgba(250,250,250,0.15), 0 0 10px rgba(250,250,250,0.05)",
          },
          "50%": {
            "box-shadow": "0 0 0 2px rgba(250,250,250,0.8), 0 0 20px rgba(250,250,250,0.35), 0 0 40px rgba(250,250,250,0.15)",
          },
        },
        // 3. نبض تدريجي للحدود والإطارات المتوهجة
        goldBorder: {
          "0%, 100%": { "border-color": "rgba(250,250,250,0.2)" },
          "50%": { "border-color": "rgba(250,250,250,0.8)" },
        },
        // 4. نبض وميض حي مخصص للأشياء المباشرة أو الجارية (LIVE) في المباريات
        pulseGlow: {
          "0%, 100%": { opacity: "0.6", transform: "scale(0.98)" },
          "50%": { opacity: "1", transform: "scale(1)" },
        },
        // 5. تأثير دخول صاعد وانسيابي مريح للعين عند تحميل البطاقات
        floatUp: {
          "0%": { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        }
      },
      animation: {
        "royal-glow": "royalGlow 3s ease-in-out infinite",
        "gold-glow": "goldGlow 3s ease-in-out infinite",
        "gold-border": "goldBorder 3s ease-in-out infinite",
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "float-up": "floatUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};