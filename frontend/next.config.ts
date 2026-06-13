import type { NextConfig } from "next";

// TMX-3600: canonical IA is /workspace/*. The redirects below preempt the
// legacy top-level routes that coexisted before. Per-page content migration
// (moving page.tsx bodies under /app/workspace/*) is out of scope for this
// ticket — these redirects keep external links / bookmarks / SDK pointers
// landing inside /workspace/* while page-level migration tickets follow.
//
// permanent: true  -> 308 — destination is canonical forever
// permanent: false -> 307 — destination will tighten when a per-page migration
//                            ticket lands; search engines should re-fetch
//
// See .context/loops/TMX-3600.md and docs/ia_migration.md for the full rationale.

// TMX-3615: security headers applied to every response. CSP is the load-
// bearing one — it's the platform's defence-in-depth against XSS, click-
// jacking, and data exfiltration to a third-party origin.
//
// `connect-src` includes the backend API base so fetch / WebSocket calls
// to it aren't blocked. Pulled from NEXT_PUBLIC_API_URL at build time so
// staging / Railway / prod each get the right origin baked in.
//
// `script-src 'self' 'unsafe-inline'` is wider than ideal but is what
// Next.js currently needs for its inline runtime bootstrapping. A future
// ticket can move to nonce-based CSP once we have a hosting layer that
// supports per-request nonce injection (TMX-3615-nonce).
const API_ORIGIN = (() => {
  const raw = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  try {
    return new URL(raw).origin
  } catch {
    return raw
  }
})()

const CSP_DIRECTIVES = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  // Next.js inline bootstrap + framer-motion need 'unsafe-inline'. Fonts
  // come from googleapis (fonts.googleapis.com / fonts.gstatic.com).
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' data: blob:",
  `connect-src 'self' ${API_ORIGIN}`,
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "upgrade-insecure-requests",
].join("; ")

const SECURITY_HEADERS = [
  // Content-Security-Policy — the big one.
  { key: "Content-Security-Policy", value: CSP_DIRECTIVES },
  // HSTS — force HTTPS for 1 year, include subdomains, preload-eligible.
  // Only meaningful when served over HTTPS (Railway / prod); harmless on
  // localhost.
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
  // Clickjacking — frame-ancestors in CSP is the modern equivalent, but
  // we set X-Frame-Options too for older browsers.
  { key: "X-Frame-Options", value: "DENY" },
  // MIME-type sniffing.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Referrer policy: send only the origin on cross-origin nav.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Disable browser features we don't use. Add to this list when we
  // intentionally adopt a feature (e.g. future microphone/clipboard
  // integrations).
  {
    key: "Permissions-Policy",
    value: [
      "camera=()",
      "microphone=()",
      "geolocation=()",
      "payment=()",
      "usb=()",
      "magnetometer=()",
      "accelerometer=()",
      "gyroscope=()",
      "fullscreen=(self)",
    ].join(", "),
  },
]

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // Apply to every route, including the redirects above (the headers
        // ride along on the 308 / 307 responses too).
        source: "/:path*",
        headers: SECURITY_HEADERS,
      },
    ]
  },

  async redirects() {
    return [
      // ── Unambiguous one-to-one (308) ──────────────────────────────────
      {
        source: "/document/:docId",
        destination: "/workspace/documents/:docId",
        permanent: true,
      },
      {
        source: "/new",
        destination: "/workspace/upload",
        permanent: true,
      },
      {
        source: "/dashboard",
        destination: "/workspace",
        permanent: true,
      },
      // TMX-3604: legacy /design-system page deleted; canonical lives
      // under /workspace/design-system (TMX-3602-patterns demo page).
      {
        source: "/design-system",
        destination: "/workspace/design-system",
        permanent: true,
      },

      // TMX-3603-jobs-id: /workspace/jobs/[id] now exists (Loop 27 fire 7).
      // Tightened from 307 → 308; destination is canonical.
      {
        source: "/translate/:jobId",
        destination: "/workspace/jobs/:jobId?mode=translate",
        permanent: true,
      },
      {
        source: "/review/:jobId",
        destination: "/workspace/jobs/:jobId?mode=review",
        permanent: true,
      },

      // /knowledge is the Black Book (rules + glossaries), which lives in the
      // Trust Center. (Was wrongly pointing at /workspace/tools, the Toolkit.)
      {
        source: "/knowledge",
        destination: "/workspace/trust",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
