/**
 * TMX-3618 — client-side file upload validation.
 *
 * Mirrors `app/services/file_validation.py` so the frontend rejects
 * invalid files before they hit the network. Backend re-validates
 * regardless (defence in depth, A3 — no silent fallbacks).
 *
 * Limits:
 *   - 50 MB max (matches backend MAX_UPLOAD_BYTES default)
 *   - Allowed extensions: .pdf, .docx, .txt
 *   - Magic-byte sniff on the first 8 bytes for .pdf / .docx
 *
 * The .txt case skips the magic check (text files have no signature
 * by definition) and only enforces extension + size.
 */

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024 // 50 MB

export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const
export type AllowedExtension = (typeof ALLOWED_EXTENSIONS)[number]

/**
 * Magic-byte signatures for the allowed extensions. Each value is the
 * sequence of bytes that the file must start with. .txt is null because
 * text files don't have a single canonical signature.
 */
const MAGIC_SIGNATURES: Record<AllowedExtension, Uint8Array | null> = {
  ".pdf": new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]),     // "%PDF-"
  ".docx": new Uint8Array([0x50, 0x4b, 0x03, 0x04]),          // "PK\x03\x04" — ZIP container
  ".txt": null,
}

export interface ValidationOk {
  ok: true
}
export interface ValidationFail {
  ok: false
  error: string
}
export type ValidationResult = ValidationOk | ValidationFail

function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".")
  if (dot < 0) return ""
  return name.slice(dot).toLowerCase()
}

function startsWith(haystack: Uint8Array, needle: Uint8Array): boolean {
  if (haystack.length < needle.length) return false
  for (let i = 0; i < needle.length; i++) {
    if (haystack[i] !== needle[i]) return false
  }
  return true
}

/**
 * Validate a File before upload. Returns ok or a single error string.
 *
 * Order of checks (cheapest first):
 *   1. Size cap (instant — no read).
 *   2. Extension whitelist (instant — string ops).
 *   3. Magic-byte signature on the first 8 bytes (one async slice read).
 */
export async function validateUpload(file: File): Promise<ValidationResult> {
  // 1. Size
  if (file.size === 0) {
    return { ok: false, error: "File is empty." }
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    const mb = (file.size / 1024 / 1024).toFixed(1)
    const cap = (MAX_UPLOAD_BYTES / 1024 / 1024).toFixed(0)
    return { ok: false, error: `File is ${mb} MB; the limit is ${cap} MB.` }
  }

  // 2. Extension
  const ext = fileExtension(file.name) as AllowedExtension
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) {
    return {
      ok: false,
      error: `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}.`,
    }
  }

  // 3. Magic-byte signature (only if the extension claims one).
  const signature = MAGIC_SIGNATURES[ext]
  if (signature) {
    const head = new Uint8Array(await file.slice(0, signature.length).arrayBuffer())
    if (!startsWith(head, signature)) {
      return {
        ok: false,
        error: `File contents don't match its ${ext} extension. Re-export and try again.`,
      }
    }
  }

  return { ok: true }
}
