import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

/**
 * Safely extract a message string from an unknown caught value.
 * Use inside `catch (e)` so we can drop the `: any` annotation while
 * still reading `e.message` semantics. TMX-3614-types.
 */
export function getErrMessage(e: unknown, fallback = "Unknown error"): string {
    if (e instanceof Error) return e.message
    if (typeof e === "string") return e
    if (e && typeof e === "object" && "message" in e) {
        const msg = (e as { message: unknown }).message
        if (typeof msg === "string") return msg
    }
    return fallback
}
