import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";

// Mock the API client + sonner before importing the components.
const submitMock = vi.fn();
vi.mock("@/lib/feedbackApi", () => ({
  feedbackApi: { submit: (...args: unknown[]) => submitMock(...args) },
}));
const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("sonner", () => ({ toast: { success: (m: string) => toastSuccess(m), error: (m: string) => toastError(m) } }));

// usePathname mock for the button visibility test.
const pathnameMock = vi.fn(() => "/workspace/jobs");
vi.mock("next/navigation", () => ({ usePathname: () => pathnameMock() }));

import FeedbackWidget from "@/components/feedback/FeedbackWidget";
import FeedbackButton from "@/components/feedback/FeedbackButton";

function openWidget() {
  act(() => {
    window.dispatchEvent(new CustomEvent("tmx:open-feedback"));
  });
}

describe("FeedbackButton", () => {
  beforeEach(() => pathnameMock.mockReturnValue("/workspace/jobs"));

  it("renders the trigger on app surfaces", () => {
    render(<FeedbackButton />);
    expect(screen.getByRole("button", { name: /send feedback/i })).toBeInTheDocument();
  });

  it("hides on landing and login", () => {
    pathnameMock.mockReturnValue("/login");
    const { container } = render(<FeedbackButton />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FeedbackWidget", () => {
  beforeEach(() => {
    submitMock.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    window.sessionStorage.clear();
  });

  it("is closed until the open event fires", () => {
    render(<FeedbackWidget />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    openWidget();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("walks category → description → priority → submit and posts the payload", async () => {
    submitMock.mockResolvedValue({
      feedback: { id: "fb-123456789012", category: "bug", title: "Login button does nothing", status: "new", priority: "high", created_at: null },
    });
    render(<FeedbackWidget />);
    openWidget();

    fireEvent.click(screen.getByRole("button", { name: /Bug/i }));
    const textarea = screen.getByLabelText(/describe your feedback/i);
    fireEvent.change(textarea, { target: { value: "Login button does nothing. Clicking it is a no-op." } });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/ }));

    fireEvent.click(screen.getByRole("button", { name: /high/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit feedback/i }));

    await waitFor(() => expect(submitMock).toHaveBeenCalledTimes(1));
    const payload = submitMock.mock.calls[0][0];
    expect(payload.category).toBe("bug");
    expect(payload.priority).toBe("high");
    expect(payload.title).toBe("Login button does nothing"); // first sentence becomes the title
    expect(payload.description).toContain("no-op");
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it("surfaces a failure (A3 — no silent swallow)", async () => {
    submitMock.mockRejectedValue(new Error("server exploded"));
    render(<FeedbackWidget />);
    openWidget();
    fireEvent.click(screen.getByRole("button", { name: /Feature/i }));
    fireEvent.change(screen.getByLabelText(/describe your feedback/i), { target: { value: "Add dark mode" } });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/ }));
    fireEvent.click(screen.getByRole("button", { name: /medium/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit feedback/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(screen.getByRole("alert")).toHaveTextContent("server exploded");
  });
});
