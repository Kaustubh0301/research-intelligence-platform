import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // ── InsightEngine design token palette ─────────────────────────────
      colors: {
        // shadcn/ui CSS-variable colours (kept for existing components)
        background:  "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        card: {
          DEFAULT:    "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT:    "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT:    "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT:    "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT:    "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT:    "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",

        // ── InsightEngine named tokens (direct hex) ───────────────────
        "surface-dim":              "#0b1326",
        "surface":                  "#0b1326",
        "surface-container-lowest": "#060e20",
        "surface-container-low":    "#131b2e",
        "surface-container":        "#171f33",
        "surface-container-high":   "#222a3d",
        "surface-container-highest":"#2d3449",
        "surface-variant":          "#2d3449",
        "surface-bright":           "#31394d",
        "surface-tint":             "#adc6ff",

        "on-surface":               "#dae2fd",
        "on-surface-variant":       "#c2c6d6",
        "on-background":            "#dae2fd",

        "im-primary":               "#adc6ff",
        "primary-container":        "#4d8eff",
        "primary-fixed":            "#d8e2ff",
        "primary-fixed-dim":        "#adc6ff",
        "on-primary":               "#002e6a",
        "on-primary-container":     "#00285d",
        "on-primary-fixed":         "#001a42",
        "on-primary-fixed-variant": "#004395",
        "inverse-primary":          "#005ac2",

        "im-secondary":             "#c0c1ff",
        "secondary-container":      "#3131c0",
        "secondary-fixed":          "#e1e0ff",
        "secondary-fixed-dim":      "#c0c1ff",
        "on-secondary":             "#1000a9",
        "on-secondary-container":   "#b0b2ff",
        "on-secondary-fixed":       "#07006c",
        "on-secondary-fixed-variant":"#2f2ebe",

        "im-tertiary":              "#ffb786",
        "tertiary-container":       "#df7412",
        "tertiary-fixed":           "#ffdcc6",
        "tertiary-fixed-dim":       "#ffb786",
        "on-tertiary":              "#502400",
        "on-tertiary-container":    "#461f00",
        "on-tertiary-fixed":        "#311400",
        "on-tertiary-fixed-variant":"#723600",

        "outline":                  "#8c909f",
        "outline-variant":          "#424754",

        "im-error":                 "#ffb4ab",
        "error-container":          "#93000a",
        "on-error":                 "#690005",
        "on-error-container":       "#ffdad6",

        "inverse-surface":          "#dae2fd",
        "inverse-on-surface":       "#283044",
      },

      // ── Border radius ───────────────────────────────────────────────
      borderRadius: {
        DEFAULT: "0.25rem",
        lg:      "0.5rem",
        xl:      "0.75rem",
        full:    "9999px",
        // shadcn radius var (kept for existing components)
        md:      "calc(var(--radius) - 2px)",
        sm:      "calc(var(--radius) - 4px)",
      },

      // ── Spacing tokens ──────────────────────────────────────────────
      spacing: {
        xs:     "4px",
        sm:     "8px",
        md:     "16px",
        lg:     "24px",
        xl:     "40px",
        "2xl":  "64px",
        gutter: "24px",
        margin: "32px",
        base:   "4px",
      },

      // ── Font families ───────────────────────────────────────────────
      fontFamily: {
        "display-lg":         ["Geist", "system-ui", "sans-serif"],
        "headline-lg":        ["Geist", "system-ui", "sans-serif"],
        "headline-lg-mobile": ["Geist", "system-ui", "sans-serif"],
        "headline-md":        ["Geist", "system-ui", "sans-serif"],
        "label-md":           ["Geist", "system-ui", "sans-serif"],
        "body-lg":            ["Inter", "system-ui", "sans-serif"],
        "body-md":            ["Inter", "system-ui", "sans-serif"],
        "body-sm":            ["Inter", "system-ui", "sans-serif"],
        "code":               ["Geist Mono", "ui-monospace", "monospace"],
        sans:                 ["Inter", "system-ui", "sans-serif"],
      },

      // ── Type scale ──────────────────────────────────────────────────
      fontSize: {
        "display-lg":         ["48px", { lineHeight: "1.1",  letterSpacing: "-0.02em", fontWeight: "600" }],
        "headline-lg":        ["32px", { lineHeight: "1.2",  letterSpacing: "-0.02em", fontWeight: "600" }],
        "headline-lg-mobile": ["24px", { lineHeight: "1.2",  fontWeight: "600" }],
        "headline-md":        ["24px", { lineHeight: "1.3",  fontWeight: "500" }],
        "body-lg":            ["18px", { lineHeight: "1.6",  fontWeight: "400" }],
        "body-md":            ["16px", { lineHeight: "1.5",  fontWeight: "400" }],
        "body-sm":            ["14px", { lineHeight: "1.5",  fontWeight: "400" }],
        "label-md":           ["14px", { lineHeight: "1",    letterSpacing: "0.01em", fontWeight: "500" }],
        "code":               ["13px", { lineHeight: "1.5",  fontWeight: "400" }],
      },
    },
  },
  plugins: [],
};

export default config;
