import { describe, it, expect } from "vitest"
import {
  validateUpload,
  MAX_UPLOAD_BYTES,
} from "@/lib/fileValidation"

function makeFile(name: string, content: Uint8Array | string, sizeOverride?: number): File {
  const blob =
    content instanceof Uint8Array
      ? new Blob([content])
      : new Blob([content], { type: "text/plain" })
  const file = new File([blob], name)
  if (sizeOverride !== undefined) {
    Object.defineProperty(file, "size", { value: sizeOverride, configurable: true })
  }
  return file
}

const PDF_HEADER = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34])  // "%PDF-1.4"
const DOCX_HEADER = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x14, 0x00])              // ZIP / OOXML
const NOT_PDF = new Uint8Array([0x68, 0x65, 0x6c, 0x6c, 0x6f])                         // "hello"

describe("validateUpload", () => {
  it("accepts a well-formed PDF", async () => {
    const result = await validateUpload(makeFile("doc.pdf", PDF_HEADER))
    expect(result.ok).toBe(true)
  })

  it("accepts a well-formed DOCX (ZIP container)", async () => {
    const result = await validateUpload(makeFile("doc.docx", DOCX_HEADER))
    expect(result.ok).toBe(true)
  })

  it("accepts a non-empty TXT (no magic-byte requirement)", async () => {
    const result = await validateUpload(makeFile("notes.txt", "hello world"))
    expect(result.ok).toBe(true)
  })

  it("rejects an empty file", async () => {
    const result = await validateUpload(makeFile("empty.pdf", new Uint8Array(0)))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/empty/i)
  })

  it("rejects a file over the size cap", async () => {
    const oversized = makeFile("big.pdf", PDF_HEADER, MAX_UPLOAD_BYTES + 1)
    const result = await validateUpload(oversized)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/limit/i)
  })

  it("rejects an unsupported extension", async () => {
    const result = await validateUpload(makeFile("photo.png", new Uint8Array([0x89, 0x50, 0x4e, 0x47])))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/unsupported/i)
  })

  it("rejects a file with a mismatched magic signature (.pdf containing not-PDF)", async () => {
    const result = await validateUpload(makeFile("disguised.pdf", NOT_PDF))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/contents don't match/i)
  })

  it("rejects a file with a mismatched magic signature (.docx without ZIP header)", async () => {
    const result = await validateUpload(makeFile("disguised.docx", NOT_PDF))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/contents don't match/i)
  })

  it("treats extension matching as case-insensitive", async () => {
    const result = await validateUpload(makeFile("DOC.PDF", PDF_HEADER))
    expect(result.ok).toBe(true)
  })

  it("rejects a file with no extension", async () => {
    const result = await validateUpload(makeFile("noext", "hello"))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toMatch(/unsupported/i)
  })
})
