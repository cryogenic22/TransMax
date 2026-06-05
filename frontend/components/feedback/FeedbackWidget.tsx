"use client";

import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import {
  feedbackApi,
  type FeedbackCategory,
  type FeedbackPriority,
  type FeedbackAttachment,
} from "@/lib/feedbackApi";

/**
 * TMX-FEEDBACK-2 — chat-style in-app feedback widget.
 *
 * Ported from market_zero's FeedbackWidget, adapted to TransMax: Next.js
 * App Router, design tokens, sonner toasts, and the TMX-FEEDBACK-1 backend
 * (`POST /api/feedback`). Opens on the `tmx:open-feedback` window event
 * dispatched by <FeedbackButton>.
 *
 * State machine:
 *   greeting → category_selected → description_provided
 *            → priority_selected → submitted | error
 *
 * The in-progress draft persists to sessionStorage so an accidental
 * Esc/refresh doesn't lose work.
 */

type ChatState =
  | "greeting"
  | "category_selected"
  | "description_provided"
  | "priority_selected"
  | "submitted"
  | "error";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  bug: "Bug",
  issue: "Issue",
  enhancement: "Enhancement",
  feature: "Feature",
  data_quality: "Data quality",
  data_request: "Data request",
};

const CATEGORY_GLYPHS: Record<FeedbackCategory, string> = {
  bug: "🐞",
  issue: "⚠️",
  enhancement: "✨",
  feature: "🚀",
  data_quality: "📊",
  data_request: "🔍",
};

const CATEGORY_PROMPTS: Record<FeedbackCategory, string> = {
  bug: "Describe the bug. What happened, what did you expect, and how can we reproduce it? You can paste a screenshot (Ctrl+V).",
  issue: "Describe the issue you're hitting and how it impacts your workflow.",
  enhancement: "Which feature would you like improved, and how would the improvement help?",
  feature: "Describe the new capability you'd like and the use case it would solve.",
  data_quality: "Which translation / number / term is wrong? Pasting a screenshot helps a lot.",
  data_request: "What are you missing? Which language pair, glossary, or source?",
};

const PRIORITY_GLYPHS: Record<FeedbackPriority, string> = {
  low: "◯",
  medium: "◐",
  high: "◑",
  critical: "●",
};

const MAX_ATTACHMENTS = 5;
const MAX_ATTACHMENT_SIZE = 2 * 1024 * 1024;
const DRAFT_KEY = "tmx_feedback_draft_v1";

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function collectDiagnostics(): Record<string, unknown> {
  if (typeof window === "undefined") return {};
  return {
    user_agent: navigator.userAgent,
    viewport: { w: window.innerWidth, h: window.innerHeight },
    path: window.location.pathname,
    referrer: document.referrer || null,
  };
}

export default function FeedbackWidget() {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [state, setState] = useState<ChatState>("greeting");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [category, setCategory] = useState<FeedbackCategory | null>(null);
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState("");
  const [priority, setPriority] = useState<FeedbackPriority>("medium");
  const [attachments, setAttachments] = useState<FeedbackAttachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);

  // Open on `tmx:open-feedback`, restoring any saved draft.
  useEffect(() => {
    const handler = () => {
      if (typeof window !== "undefined" && window.localStorage.getItem("tmx_feedback_disabled") === "true") {
        return;
      }
      setOpen(true);
      const saved = typeof window !== "undefined" ? window.sessionStorage.getItem(DRAFT_KEY) : null;
      if (saved) {
        try {
          const d = JSON.parse(saved);
          setState(d.state ?? "greeting");
          setMessages(d.messages ?? [{ role: "assistant", content: "What kind of feedback do you have?" }]);
          setCategory(d.category ?? null);
          setDescription(d.description ?? "");
          setDraft(d.draft ?? "");
          setPriority(d.priority ?? "medium");
          setAttachments(d.attachments ?? []);
          setError(null);
          setResultId(null);
          return;
        } catch {
          /* corrupted draft — fall through to a fresh start */
        }
      }
      setState("greeting");
      setMessages([{ role: "assistant", content: "What kind of feedback do you have?" }]);
      setCategory(null);
      setDescription("");
      setDraft("");
      setPriority("medium");
      setAttachments([]);
      setError(null);
      setResultId(null);
    };
    window.addEventListener("tmx:open-feedback", handler);
    return () => window.removeEventListener("tmx:open-feedback", handler);
  }, []);

  // Persist the in-flight draft so accidental close preserves work.
  useEffect(() => {
    if (!open || state === "submitted" || state === "error") return;
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ state, messages, category, description, draft, priority, attachments }),
      );
    } catch {
      /* storage quota exceeded — skip persistence */
    }
  }, [open, state, messages, category, description, draft, priority, attachments]);

  // Esc closes; focus the close button on open; trap Tab inside the dialog.
  useEffect(() => {
    if (!open) return;
    const restoreFocus = (document.activeElement as HTMLElement) ?? null;
    closeBtnRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      if (e.key === "Tab") {
        const root = dialogRef.current;
        if (!root) return;
        const focusables = root.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      restoreFocus?.focus?.();
    };
  }, [open]);

  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  if (!open) return null;

  const appendMessage = (role: "user" | "assistant", content: string) =>
    setMessages((prev) => [...prev, { role, content }]);

  const handleCategory = (cat: FeedbackCategory) => {
    setCategory(cat);
    appendMessage("user", `${CATEGORY_GLYPHS[cat]} ${CATEGORY_LABELS[cat]}`);
    appendMessage("assistant", CATEGORY_PROMPTS[cat]);
    setState("category_selected");
  };

  const handleSendDescription = () => {
    if (!draft.trim()) return;
    setDescription(draft.trim());
    appendMessage("user", draft.trim());
    appendMessage("assistant", "How urgent is this?");
    setState("description_provided");
    setDraft("");
  };

  const handlePriority = (p: FeedbackPriority) => {
    setPriority(p);
    appendMessage("user", `${PRIORITY_GLYPHS[p]} ${p}`);
    appendMessage("assistant", `Ready to submit a ${CATEGORY_LABELS[category!]} at ${p} priority. Looks right?`);
    setState("priority_selected");
  };

  const addAttachment = async (file: File) => {
    if (attachments.length >= MAX_ATTACHMENTS) {
      appendMessage("assistant", `Maximum ${MAX_ATTACHMENTS} attachments.`);
      return;
    }
    if (file.size > MAX_ATTACHMENT_SIZE) {
      appendMessage("assistant", "Attachment too large (max 2 MB).");
      return;
    }
    if (!file.type.startsWith("image/")) {
      appendMessage("assistant", "Only images are accepted as screenshots.");
      return;
    }
    try {
      const dataUri = await fileToDataUri(file);
      const attachment: FeedbackAttachment = {
        data: dataUri,
        filename: file.name || `pasted-${attachments.length + 1}.png`,
        mime_type: file.type,
        size_bytes: file.size,
      };
      setAttachments((prev) => [...prev, attachment]);
      appendMessage("user", `📎 ${attachment.filename}`);
    } catch {
      appendMessage("assistant", "Could not read the image.");
    }
  };

  const handlePaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of Array.from(items)) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) await addAttachment(file);
        return;
      }
    }
  };

  const removeAttachment = (idx: number) => setAttachments((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async () => {
    if (!category) return;
    setBusy(true);
    setError(null);
    appendMessage("user", "Submit it!");
    try {
      const firstSentence = description.split(/[.!?\n]/)[0]?.trim() || description;
      const title = firstSentence.length > 120 ? firstSentence.slice(0, 117) + "…" : firstSentence;

      const r = await feedbackApi.submit({
        category,
        title,
        description,
        priority,
        page_url: typeof window !== "undefined" ? window.location.pathname : undefined,
        diagnostic_context: collectDiagnostics(),
        attachments,
      });

      const id = r.feedback.id;
      setResultId(id);
      appendMessage("assistant", `Recorded! ID: ${id.slice(0, 12)}…\nWe'll triage it shortly.`);
      setState("submitted");
      toast.success("Feedback submitted — thank you!");
      if (typeof window !== "undefined") {
        try {
          window.sessionStorage.removeItem(DRAFT_KEY);
        } catch {
          /* ignore */
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      appendMessage("assistant", `Submission failed: ${msg}`);
      setState("error");
      toast.error(`Feedback failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed bottom-6 right-6 z-50 flex w-[min(420px,92vw)] max-h-[min(640px,80vh)] flex-col overflow-hidden rounded-2xl border shadow-2xl"
      style={{ background: "var(--bg-elevated, #fff)", borderColor: "var(--neutral-200, #dadce0)" }}
    >
      <header
        className="flex items-center justify-between border-b px-5 py-3"
        style={{ borderColor: "var(--neutral-200, #dadce0)" }}
      >
        <h3 id={titleId} className="m-0 text-base font-semibold" style={{ color: "var(--neutral-900, #171717)" }}>
          Feedback
        </h3>
        <button
          ref={closeBtnRef}
          type="button"
          aria-label="close"
          onClick={() => setOpen(false)}
          className="rounded px-2 py-1 text-lg leading-none hover:bg-black/5"
          style={{ color: "var(--neutral-600, #5f6368)" }}
        >
          ×
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto px-5 py-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className="max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-[13px]"
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              background: m.role === "user" ? "var(--brand-50, #e8f0fe)" : "var(--bg-secondary, #f8f9fa)",
              color: "var(--neutral-800, #202124)",
            }}
          >
            {m.content}
          </div>
        ))}
        {busy && (
          <div className="self-start text-xs italic" style={{ color: "var(--neutral-500, #80868b)" }}>
            Submitting…
          </div>
        )}
        {error && state === "error" && (
          <div
            role="alert"
            className="self-stretch rounded-xl px-3 py-2 text-xs"
            style={{ background: "var(--error-50, #fce8e6)", color: "var(--error-600, #c5221f)" }}
          >
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {attachments.length > 0 && state !== "submitted" && state !== "error" && (
        <div
          className="flex gap-2 overflow-x-auto border-t px-5 py-2"
          style={{ borderColor: "var(--neutral-200, #dadce0)" }}
        >
          {attachments.map((a, i) => (
            <div key={i} className="relative flex-shrink-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={a.data}
                alt={a.filename}
                className="h-14 w-14 rounded border object-cover"
                style={{ borderColor: "var(--neutral-200, #dadce0)" }}
              />
              <button
                type="button"
                aria-label={`remove ${a.filename}`}
                onClick={() => removeAttachment(i)}
                className="absolute -right-1.5 -top-1.5 flex h-[18px] w-[18px] items-center justify-center rounded-full text-[11px] leading-none text-white"
                style={{ background: "var(--error-500, #d93025)" }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <footer className="border-t px-5 py-3" style={{ borderColor: "var(--neutral-200, #dadce0)" }}>
        {state === "greeting" && (
          <div className="grid grid-cols-2 gap-2">
            {(Object.keys(CATEGORY_LABELS) as FeedbackCategory[]).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => handleCategory(cat)}
                className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm hover:bg-black/5"
                style={{ borderColor: "var(--neutral-200, #dadce0)", color: "var(--neutral-800, #202124)" }}
              >
                <span aria-hidden="true">{CATEGORY_GLYPHS[cat]}</span>
                <span>{CATEGORY_LABELS[cat]}</span>
              </button>
            ))}
          </div>
        )}

        {state === "category_selected" && (
          <div className="flex gap-2">
            <textarea
              aria-label="describe your feedback"
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onPaste={(e) => void handlePaste(e)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  handleSendDescription();
                }
              }}
              placeholder="Describe… (Ctrl+V to paste a screenshot)"
              className="flex-1 resize-y rounded-xl border px-3 py-2 text-[13px] outline-none"
              style={{
                background: "var(--bg-secondary, #f8f9fa)",
                borderColor: "var(--neutral-200, #dadce0)",
                color: "var(--neutral-900, #171717)",
              }}
              autoFocus
            />
            <button
              type="button"
              onClick={handleSendDescription}
              disabled={!draft.trim()}
              className="rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--brand-500, #1a73e8)" }}
            >
              Send
            </button>
          </div>
        )}

        {state === "description_provided" && (
          <div className="grid grid-cols-4 gap-1.5">
            {(Object.keys(PRIORITY_GLYPHS) as FeedbackPriority[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => handlePriority(p)}
                className="flex flex-col items-center gap-0.5 rounded-lg border px-2 py-2 text-xs hover:bg-black/5"
                style={{ borderColor: "var(--neutral-200, #dadce0)", color: "var(--neutral-800, #202124)" }}
              >
                <span aria-hidden="true">{PRIORITY_GLYPHS[p]}</span>
                <span>{p}</span>
              </button>
            ))}
          </div>
        )}

        {state === "priority_selected" && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={busy}
              className="flex-1 rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--brand-500, #1a73e8)" }}
            >
              Submit feedback
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg border px-3 py-2 text-sm hover:bg-black/5"
              style={{ borderColor: "var(--neutral-200, #dadce0)", color: "var(--neutral-800, #202124)" }}
            >
              Start over
            </button>
          </div>
        )}

        {(state === "submitted" || state === "error") && (
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="w-full rounded-lg border px-3 py-2 text-sm hover:bg-black/5"
            style={{ borderColor: "var(--neutral-200, #dadce0)", color: "var(--neutral-800, #202124)" }}
          >
            {resultId ? "Close" : "Try again"}
          </button>
        )}
      </footer>
    </div>
  );
}
