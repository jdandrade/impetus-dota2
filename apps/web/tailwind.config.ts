import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        brand: {
          primary: "#A855F7",
          "primary-light": "#C084FC",
          "primary-dark": "#7C3AED",
          secondary: "#14B8A6",
          "secondary-light": "#2DD4BF",
          "secondary-dark": "#0D9488",
        },
        cyber: {
          bg: "#0A0A0F",
          surface: "#12121A",
          "surface-light": "#1A1A25",
          border: "#2A2A3A",
          text: "#E4E4E7",
          "text-muted": "#71717A",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(168, 85, 247, 0.3)",
        "glow-teal": "0 0 20px rgba(20, 184, 166, 0.3)",
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(168, 85, 247, 0.3)" },
          "50%": { boxShadow: "0 0 40px rgba(168, 85, 247, 0.6)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
