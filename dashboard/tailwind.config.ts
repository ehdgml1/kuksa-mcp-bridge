import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ivi: {
          dark: "#080c14",
          surface: "#0f1724",
          card: "#0d1117",
          border: "#1a1f2e",
          text: "#f1f5f9",
          muted: "#64748b",
          secondary: "#94a3b8",
        },
        gauge: {
          cyan: "#06b6d4",
          amber: "#f59e0b",
          red: "#ef4444",
          green: "#22c55e",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-in": "slideIn 0.3s ease-out",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        slideIn: {
          "0%": { transform: "translateY(-10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        glowPulse: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.6", transform: "scale(0.97)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
