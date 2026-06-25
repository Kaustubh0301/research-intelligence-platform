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

        // ── InsightEngine named tokens (CSS-var driven, dark-mode aware) ─
        "surface-dim":              "var(--ie-surface-dim)",
        "surface":                  "var(--ie-surface)",
        "surface-container-lowest": "var(--ie-surface-container-lowest)",
        "surface-container-low":    "var(--ie-surface-container-low)",
        "surface-container":        "var(--ie-surface-container)",
        "surface-container-high":   "var(--ie-surface-container-high)",
        "surface-container-highest":"var(--ie-surface-container-highest)",
        "surface-variant":          "var(--ie-surface-variant)",
        "surface-bright":           "var(--ie-surface-bright)",
        "surface-tint":             "#494bd6",

        "on-surface":               "var(--ie-on-surface)",
        "on-surface-variant":       "var(--ie-on-surface-variant)",
        "on-background":            "var(--ie-on-background)",

        "im-primary":               "#4648d4",
        "primary-container":        "#6063ee",
        "primary-fixed":            "#e1e0ff",
        "primary-fixed-dim":        "#c0c1ff",
        "on-primary":               "#ffffff",
        "on-primary-container":     "#fffbff",
        "on-primary-fixed":         "#07006c",
        "on-primary-fixed-variant": "#2f2ebe",
        "inverse-primary":          "#c0c1ff",

        "im-secondary":             "#565e74",
        "secondary-container":      "#dae2fd",
        "secondary-fixed":          "#dae2fd",
        "secondary-fixed-dim":      "#bec6e0",
        "on-secondary":             "#ffffff",
        "on-secondary-container":   "#5c647a",
        "on-secondary-fixed":       "#131b2e",
        "on-secondary-fixed-variant":"#3f465c",

        "im-tertiary":              "#5a5c5d",
        "tertiary-container":       "#737576",
        "tertiary-fixed":           "#e1e3e4",
        "tertiary-fixed-dim":       "#c5c7c8",
        "on-tertiary":              "#ffffff",
        "on-tertiary-container":    "#fcfdfe",
        "on-tertiary-fixed":        "#191c1d",
        "on-tertiary-fixed-variant":"#454748",

        "outline":                  "var(--ie-outline)",
        "outline-variant":          "var(--ie-outline-variant)",

        "im-error":                 "#ba1a1a",
        "error-container":          "#ffdad6",
        "on-error":                 "#ffffff",
        "on-error-container":       "#93000a",

        "inverse-surface":          "var(--ie-inverse-surface)",
        "inverse-on-surface":       "var(--ie-inverse-on-surface)",
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
