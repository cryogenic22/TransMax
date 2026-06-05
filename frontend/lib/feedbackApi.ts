/**
 * TMX-FEEDBACK-2 — frontend client for the in-app feedback API
 * (backend: TMX-FEEDBACK-1, `app/api/feedback.py`).
 *
 * Mirrors the auth-token + fetch idiom in `lib/api.ts` (cookie-based
 * `transmax_token` bearer). All calls hit `${NEXT_PUBLIC_API_URL}/api/feedback`.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export type FeedbackCategory =
  | "bug"
  | "issue"
  | "enhancement"
  | "feature"
  | "data_quality"
  | "data_request";

export type FeedbackPriority = "low" | "medium" | "high" | "critical";

export interface FeedbackAttachment {
  data: string; // data URI
  filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface FeedbackSubmitPayload {
  category: FeedbackCategory;
  title: string;
  description?: string;
  priority: FeedbackPriority;
  page_url?: string;
  session_id?: string;
  diagnostic_context?: Record<string, unknown>;
  attachments?: FeedbackAttachment[];
}

export interface FeedbackSubmitResult {
  feedback: {
    id: string;
    category: string;
    title: string;
    status: string;
    priority: string;
    created_at: string | null;
  };
}

function authToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(^| )transmax_token=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export const feedbackApi = {
  async submit(payload: FeedbackSubmitPayload): Promise<FeedbackSubmitResult> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = authToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
    } catch {
      throw new Error("Unable to reach the server. Please check your connection and try again.");
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Submission failed (${res.status})`);
    }
    return res.json();
  },
};
