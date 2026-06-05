"use client";

import { usePathname } from "next/navigation";

/**
 * TMX-FEEDBACK-2 — floating "Feedback" trigger.
 *
 * Renders a small pill bottom-right on every app surface except the
 * landing (`/`) and `/login`. Clicking dispatches `tmx:open-feedback`,
 * which `<FeedbackWidget>` listens for. Decoupled via a window event so
 * the trigger and the dialog don't need shared React state.
 */
export default function FeedbackButton() {
  const pathname = usePathname();

  // Hide on the public landing + login surfaces.
  if (pathname === "/" || pathname.startsWith("/login")) return null;

  return (
    <button
      type="button"
      aria-label="Send feedback"
      onClick={() => window.dispatchEvent(new CustomEvent("tmx:open-feedback"))}
      className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white shadow-lg transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-400"
      style={{ background: "var(--brand-500, #1a73e8)" }}
    >
      <span aria-hidden="true">💬</span>
      <span>Feedback</span>
    </button>
  );
}
