/**
 * TMX-3050 — egress-side HTML sanitisation for the reviewer surface.
 *
 * The Tiptap RichTextEditor calls `editor.getHTML()` and forwards the result
 * through `onChange` into persistence. Without sanitisation, a reviewer who
 * pastes attacker-controlled markup (`<img onerror=...>`, `<a href="javascript:...">`,
 * `<script>`, `<iframe>`, etc.) creates a stored-XSS that fires on every other
 * reviewer's page load — the worst-case failure mode in the most-regulated UI
 * in the platform (audit finding F-H03, 2026-05-09).
 *
 * Defence: explicit allowlist via DOMPurify. Never the loose default profile.
 *
 * ALLOWLIST (what TIPTAP-AUTHORED CONTENT actually uses today):
 *   Block:    p, br, hr, h1-h6, blockquote, ul, ol, li
 *   Inline:   strong, em, u, s, code, a (href: https?: | mailto: only)
 *   Tables:   table, thead, tbody, tr, th, td
 *   Attrs:    href (a only), colspan, rowspan, class (Tiptap emits class on lists/tables)
 *
 * STRIPPED:
 *   - <script>, <iframe>, <object>, <embed>, <link>, <meta>, <style>
 *   - All on* event handlers (onerror, onload, onclick, ...)
 *   - javascript:, data:, vbscript:, file:, blob: URIs
 *   - SVG, MathML (DOMPurify default behaviour with USE_PROFILES=html only)
 *
 * If a future ticket needs `target="_blank"` on links it MUST also add
 * `rel="noopener noreferrer"` in the same diff.
 *
 * A3 — no silent fallback. If DOMPurify is somehow unavailable at runtime
 * (e.g. dynamic-import edge), this throws. RichTextEditor must NOT pass
 * through raw HTML on import failure.
 */
import DOMPurify from "dompurify"

const ALLOWED_TAGS = [
  // block
  "p",
  "br",
  "hr",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "blockquote",
  "ul",
  "ol",
  "li",
  // inline marks
  "strong",
  "em",
  "u",
  "s",
  "code",
  "a",
  // tables
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
] as const

const ALLOWED_ATTR = ["href", "colspan", "rowspan", "class"] as const

// Belt-and-braces: explicit denylist for tags that ALSO have a "promote children
// to parent" hazard via KEEP_CONTENT. Some HTML parsers (notably happy-dom in
// our test env) park <embed>/<source>/etc. inside <object>'s fallback subtree.
// When DOMPurify removes <object> with KEEP_CONTENT, those children get promoted
// to body. FORBID_TAGS enforces removal in a second pass.
const FORBID_TAGS = [
  "script",
  "iframe",
  "object",
  "embed",
  "param",
  "source",
  "track",
  "video",
  "audio",
  "img",
  "svg",
  "math",
  "style",
  "link",
  "meta",
  "base",
  "form",
  "input",
  "button",
  "textarea",
  "select",
  "option",
] as const

// Permit only http/https/mailto. Strips javascript:, data:, vbscript:, file:, blob:.
const ALLOWED_URI_REGEXP = /^(?:https?|mailto):/i

export function sanitizeRichTextHtml(html: string): string {
  if (!html) return ""

  // DOMPurify reads from `window` for the browser DOM. In a non-browser context
  // (SSR, Node-only test) it will throw or return broken output. RichTextEditor
  // is configured with `immediatelyRender: false` so it never renders SSR-side,
  // which means egress sanitisation only runs in the browser. In tests, vitest
  // uses happy-dom so `window` is present.
  if (typeof window === "undefined") {
    throw new Error(
      "sanitizeRichTextHtml: no window context — sanitiser cannot run safely. " +
        "Refusing to pass HTML through unsanitised (A3).",
    )
  }

  // KEEP_CONTENT default = true: when DOMPurify drops a forbidden tag like
  // <a href="javascript:...">x</a>, the inner text "x" is kept while the
  // tag is unwrapped. This matches user expectation (don't lose their text)
  // while still neutralising the attack.
  //
  // We deliberately do NOT pass USE_PROFILES — it would expand the allowlist
  // back to DOMPurify's "all of HTML" defaults (including <img>, <embed>,
  // <object>, SVG/MathML). Our ALLOWED_TAGS is the ONLY source of truth.
  //
  // We sanitise TWICE. The second pass catches anything that was promoted to
  // the parent via KEEP_CONTENT during the first pass (e.g. <embed> nested
  // inside <object>'s fallback subtree, where some parsers re-locate the
  // <embed> as a child of <object> rather than a sibling). The cost is
  // negligible (sanitise is microseconds on the small payloads we see), the
  // safety win is "nested mutation XSS via non-conforming parsers".
  const config = {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR],
    FORBID_TAGS: [...FORBID_TAGS],
    ALLOWED_URI_REGEXP,
  }
  const firstPass = DOMPurify.sanitize(html, config)
  return DOMPurify.sanitize(firstPass, config)
}
