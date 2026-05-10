/**
 * TMX-3050 — Tiptap RichTextEditor egress sanitisation.
 *
 * These tests are the G2 reproduce-the-failure gate for audit finding F-H03.
 * Every NEGATIVE test below corresponds to a real stored-XSS vector that
 * survived `editor.getHTML()` in the unsanitised code path.
 */
import { describe, it, expect } from "vitest"
import { sanitizeRichTextHtml } from "@/lib/sanitizeHtml"

describe("sanitizeRichTextHtml — XSS vectors stripped", () => {
  it("strips <img onerror=...> event handler", () => {
    const malicious = '<p>hello</p><img src=x onerror="alert(1)">'
    const out = sanitizeRichTextHtml(malicious)
    expect(out).not.toMatch(/onerror/i)
    expect(out).not.toMatch(/<img/i)
    expect(out).toContain("<p>hello</p>")
  })

  it('strips javascript: URLs from <a href>', () => {
    const malicious = '<a href="javascript:alert(1)">click</a>'
    const out = sanitizeRichTextHtml(malicious)
    expect(out.toLowerCase()).not.toContain("javascript:")
  })

  it("strips <script> tags and their content", () => {
    // The security-critical assertions: no script tag, no script body.
    // (We don't assert what surrounding markup survives because HTML5
    // parsing rules around <script> are gnarly and DOMParser-implementation
    // dependent — the security property is what matters here.)
    const malicious = "<script>alert(1)</script>"
    const out = sanitizeRichTextHtml(malicious)
    expect(out).not.toMatch(/<script/i)
    expect(out).not.toContain("alert(1)")
  })

  it("preserves surrounding text when an inline tag is stripped", () => {
    const malicious = "<p>before</p><b>middle</b><p>after</p>"
    // <b> is NOT in our allowlist (we use <strong>); KEEP_CONTENT keeps "middle".
    const out = sanitizeRichTextHtml(malicious)
    expect(out).toContain("<p>before</p>")
    expect(out).toContain("middle")
    expect(out).toContain("<p>after</p>")
    expect(out).not.toMatch(/<b>/i)
  })

  it("strips <iframe> tags", () => {
    // No src= — happy-dom eagerly fetches iframe[src] in a way that triggers
    // unhandled-rejection noise even after DOMPurify strips the element. The
    // sanitiser still strips iframes regardless of attributes; this test
    // confirms the tag itself is gone.
    const malicious = "<iframe></iframe>"
    const out = sanitizeRichTextHtml(malicious)
    expect(out).not.toMatch(/<iframe/i)
  })

  it("strips inline event handlers on otherwise-allowed tags", () => {
    const malicious = '<p onclick="alert(1)">hi</p>'
    const out = sanitizeRichTextHtml(malicious)
    expect(out).not.toMatch(/onclick/i)
    // The <p> body itself should survive.
    expect(out).toContain("hi")
  })

  it("strips data: URIs on <a href> (potential XSS / phishing carrier)", () => {
    const malicious = '<a href="data:text/html,<script>alert(1)</script>">x</a>'
    const out = sanitizeRichTextHtml(malicious)
    expect(out.toLowerCase()).not.toContain("data:")
  })
})

describe("sanitizeRichTextHtml — legitimate Tiptap markup survives", () => {
  it("preserves paragraphs, basic marks, and https links", () => {
    const safe =
      '<p><strong>hi</strong> <em>there</em> <a href="https://example.com">link</a></p>'
    const out = sanitizeRichTextHtml(safe)
    expect(out).toContain("<strong>hi</strong>")
    expect(out).toContain("<em>there</em>")
    expect(out).toMatch(/<a [^>]*href="https:\/\/example\.com"/)
    expect(out).toContain(">link</a>")
  })

  it("preserves bullet lists", () => {
    const safe = "<ul><li>one</li><li>two</li></ul>"
    const out = sanitizeRichTextHtml(safe)
    expect(out).toContain("<ul>")
    expect(out).toContain("<li>one</li>")
    expect(out).toContain("<li>two</li>")
  })

  it("preserves ordered lists", () => {
    const safe = "<ol><li>first</li><li>second</li></ol>"
    const out = sanitizeRichTextHtml(safe)
    expect(out).toContain("<ol>")
    expect(out).toContain("<li>first</li>")
  })

  it("preserves tables (Tiptap default markup)", () => {
    const safe =
      "<table><tbody><tr><th>h</th></tr><tr><td>c</td></tr></tbody></table>"
    const out = sanitizeRichTextHtml(safe)
    expect(out).toContain("<table>")
    expect(out).toContain("<th>h</th>")
    expect(out).toContain("<td>c</td>")
  })

  it("preserves mailto: links", () => {
    const safe = '<a href="mailto:a@b.com">email</a>'
    const out = sanitizeRichTextHtml(safe)
    expect(out).toContain('href="mailto:a@b.com"')
  })
})

describe("sanitizeRichTextHtml — edge cases", () => {
  it("returns empty string for empty input", () => {
    expect(sanitizeRichTextHtml("")).toBe("")
  })

  it("handles text with no HTML", () => {
    const out = sanitizeRichTextHtml("just text")
    expect(out).toBe("just text")
  })

  it("strips <object> and <embed>", () => {
    const malicious =
      '<object data="evil.swf"></object><embed src="evil.swf">'
    const out = sanitizeRichTextHtml(malicious)
    expect(out).not.toMatch(/<object/i)
    expect(out).not.toMatch(/<embed/i)
  })
})
