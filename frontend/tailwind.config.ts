import type { Config } from "tailwindcss";
// TMX-3006 (review F-H07): both plugins use ESM imports. Turbopack and
// ESLint reject `require()` in TypeScript config files.
import tailwindAnimate from "tailwindcss-animate";
import typography from "@tailwindcss/typography";

const config: Config = {
    darkMode: ["class"],
    content: [
        "./pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        container: {
            center: true,
            padding: "2rem",
            screens: {
                "2xl": "1400px",
            },
        },
        extend: {
            colors: {
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--primary-foreground))",
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))",
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))",
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))",
                },
                accent: {
                    DEFAULT: "hsl(var(--accent))",
                    foreground: "hsl(var(--accent-foreground))",
                },
                popover: {
                    DEFAULT: "hsl(var(--popover))",
                    foreground: "hsl(var(--popover-foreground))",
                },
                card: {
                    DEFAULT: "hsl(var(--card))",
                    foreground: "hsl(var(--card-foreground))",
                },
                "medical-green": "hsl(var(--medical-green))",
                "alert-red": "hsl(var(--alert-red))",
                // TMX-3601 design tokens — AI Moment, Provenance, Status Lifecycle, Agents.
                ai: {
                    from: "var(--ai-gradient-from)",
                    to: "var(--ai-gradient-to)",
                    tint: "var(--ai-tint)",
                    border: "var(--ai-border)",
                    spark: "var(--ai-spark)",
                },
                audit: {
                    chip: "var(--audit-chip-bg)",
                    "chip-fg": "var(--audit-chip-fg)",
                    "chip-border": "var(--audit-chip-border)",
                    hash: "var(--audit-hash-fg)",
                },
                status: {
                    "pending-bg": "var(--status-pending-bg)",
                    "pending-fg": "var(--status-pending-fg)",
                    "translating-bg": "var(--status-translating-bg)",
                    "translating-fg": "var(--status-translating-fg)",
                    "translated-bg": "var(--status-translated-bg)",
                    "translated-fg": "var(--status-translated-fg)",
                    "reviewed-bg": "var(--status-reviewed-bg)",
                    "reviewed-fg": "var(--status-reviewed-fg)",
                    "approved-bg": "var(--status-approved-bg)",
                    "approved-fg": "var(--status-approved-fg)",
                    "blocked-bg": "var(--status-blocked-bg)",
                    "blocked-fg": "var(--status-blocked-fg)",
                },
                agent: {
                    translator: "var(--agent-translator)",
                    reviewer: "var(--agent-reviewer)",
                    fixer: "var(--agent-fixer)",
                    auditor: "var(--agent-auditor)",
                },
            },
            backgroundImage: {
                "ai-gradient":
                    "linear-gradient(135deg, var(--ai-gradient-from) 0%, var(--ai-gradient-to) 100%)",
            },
            borderRadius: {
                lg: "var(--radius)",
                md: "calc(var(--radius) - 2px)",
                sm: "calc(var(--radius) - 4px)",
            },
            fontFamily: {
                sans: ["DM Sans", "Google Sans", "sans-serif"],
                mono: ["JetBrains Mono", "monospace"],
            }
        },
    },
    plugins: [tailwindAnimate, typography],
};
export default config;
