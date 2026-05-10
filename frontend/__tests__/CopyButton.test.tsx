import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

// TMX-3604-copy-toast — CopyButton silently swallowed clipboard
// failures with console.error. Real failure modes (HTTP context,
// denied permissions, sandboxed iframe) leave the icon grey with no
// error signal. Mocking sonner so we can assert toast.error fires
// without needing a Toaster portal in the test tree.

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

import { toast } from "sonner"
import { CopyButton } from "@/components/ui/CopyButton"

describe("<CopyButton>", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("fires toast.error when navigator.clipboard.writeText rejects", async () => {
        Object.defineProperty(navigator, "clipboard", {
            value: {
                writeText: vi.fn().mockRejectedValue(new Error("NotAllowedError: clipboard write denied")),
            },
            configurable: true,
        })

        render(<CopyButton text="hello" />)
        const button = screen.getByTitle("Copy to clipboard")
        fireEvent.click(button)

        await waitFor(() => {
            expect(toast.error).toHaveBeenCalled()
        })
        // Real server-rejected message must be the toast text — proves
        // we no longer just log to console.
        const callArg = (toast.error as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]
        expect(callArg).toMatch(/clipboard write denied|couldn't copy|copy failed/i)
    })

    it("does NOT fire toast.error on a successful copy", async () => {
        Object.defineProperty(navigator, "clipboard", {
            value: {
                writeText: vi.fn().mockResolvedValue(undefined),
            },
            configurable: true,
        })

        render(<CopyButton text="hello" />)
        const button = screen.getByTitle("Copy to clipboard")
        fireEvent.click(button)

        // Yield twice to settle the resolved promise + the setTimeout
        // that flips the green-check off.
        await waitFor(() => {
            expect((navigator.clipboard.writeText as unknown as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith("hello")
        })
        expect(toast.error).not.toHaveBeenCalled()
    })
})
