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

const nextConfig: NextConfig = {
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

      // ── Ambiguous (307) — destination will tighten in follow-up tickets ──
      // /translate/[jobId] and /review/[jobId]: no /workspace/jobs/[id] yet
      // (TMX-3603 builds it). Land on the jobs list with focus + action hints
      // so the user is one click from where they wanted to be.
      {
        source: "/translate/:jobId",
        destination: "/workspace/jobs?focus=:jobId&action=translate",
        permanent: false,
      },
      {
        source: "/review/:jobId",
        destination: "/workspace/jobs?focus=:jobId&action=review",
        permanent: false,
      },
      // /knowledge -> /workspace/tools per design v1; 307 because the IA may
      // split knowledge / glossary into separate workspace sections later.
      {
        source: "/knowledge",
        destination: "/workspace/tools",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
