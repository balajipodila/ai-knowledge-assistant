import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../components/auth-provider";
import { ChatInterface } from "../../components/chat-interface";
import { saveSession } from "../../lib/session";

const readyDocument = {
  id: "doc-1",
  filename: "machine-learning.pdf",
  status: "ready",
  page_count: 7,
  created_at: "2026-10-12T10:30:00Z",
  failure_reason: null,
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

function renderChat(documents: object[] = [readyDocument]) {
  saveSession({
    access_token: "chat-test-token",
    expires_in: 1800,
    user: {
      id: "user-1",
      email: "person@example.test",
      created_at: "2026-01-01T00:00:00Z",
    },
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(200, documents),
  );
  render(
    <AuthProvider>
      <ChatInterface />
    </AuthProvider>,
  );
  return fetchMock;
}

function chatResponse(answer: string, citations: object[] = []) {
  return jsonResponse(200, { answer, citations });
}

async function submit(text: string, key = false) {
  const input = await screen.findByLabelText("Your question");
  fireEvent.change(input, { target: { value: text } });
  if (key) fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
  else fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("chat page", () => {
  it("validates an empty question and does not send it", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Enter a question.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not submit Enter during IME composition and supports Shift+Enter", async () => {
    const fetchMock = renderChat();
    const input = await screen.findByLabelText("Your question");
    fireEvent.change(input, { target: { value: "What is machine learning?" } });
    fireEvent.keyDown(input, { key: "Enter", isComposing: true, keyCode: 229 });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockResolvedValueOnce(chatResponse("Machine learning [1].", [
      {
        number: 1,
        document_id: readyDocument.id,
        filename: readyDocument.filename,
        page_number: 2,
        snippet: "A method for learning patterns.",
      },
    ]));
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText(/Machine learning/)).toBeTruthy();
  });

  it("sends selected ready document ids and uses a 45-second timeout", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");
    fetchMock.mockResolvedValueOnce(chatResponse("A short answer."));
    fireEvent.click(screen.getByLabelText("machine-learning.pdf"));
    await submit("Explain machine learning?");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({
      question: "Explain machine learning?",
      document_ids: [readyDocument.id],
    });
    expect(setTimeoutSpy.mock.calls.some(([, delay]) => delay === 45_000)).toBe(true);
  });

  it("omits document_ids when no documents are selected", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock.mockResolvedValueOnce(chatResponse("The context answer [1].", [
      {
        number: 1,
        document_id: readyDocument.id,
        filename: readyDocument.filename,
        page_number: 1,
        snippet: "Helpful content.",
      },
    ]));
    await submit("Tell me about this document?", true);
    await screen.findByText(/The context answer/);

    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({
      question: "Tell me about this document?",
    });
  });

  it("links only available citation labels in [n], adjacent, and comma-separated forms", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock.mockResolvedValueOnce(
      chatResponse("First [1], then [1][2], together [1, 2], invented [9].", [
        {
          number: 1,
          document_id: readyDocument.id,
          filename: readyDocument.filename,
          page_number: 2,
          snippet: "First evidence.",
        },
        {
          number: 2,
          document_id: readyDocument.id,
          filename: readyDocument.filename,
          page_number: 5,
          snippet: "Second evidence.",
        },
      ]),
    );
    await submit("What does the document say?");

    const citationLinks = await screen.findAllByRole("button", {
      name: "Jump to citation 2, machine-learning.pdf, page 5",
    });
    const citationLink = citationLinks.at(-1);
    if (!citationLink) throw new Error("Citation marker button was not rendered.");
    expect(screen.getAllByRole("button", {
      name: "Jump to citation 1, machine-learning.pdf, page 2",
    }).length).toBe(3);
    expect(screen.queryByRole("button", { name: /citation 9/i })).toBeNull();
    expect(screen.getByText(/invented \[9\]\./)).toBeTruthy();

    const card = document.getElementById("chat-citation-0-2");
    expect(card).not.toBeNull();
    fireEvent.click(citationLink);
    expect(document.activeElement).toBe(card);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("uses turn-specific citation anchors when the same citation number appears twice", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    const citation = {
      number: 1,
      document_id: readyDocument.id,
      filename: readyDocument.filename,
      page_number: 2,
      snippet: "Evidence.",
    };
    fetchMock
      .mockResolvedValueOnce(chatResponse("Answer one [1].", [citation]))
      .mockResolvedValueOnce(chatResponse("Answer two [1].", [citation]));
    await submit("First question");
    await screen.findByText(/Answer one/);
    await submit("Second question");
    await screen.findByText(/Answer two/);

    expect(document.getElementById("chat-citation-0-1")).not.toBeNull();
    expect(document.getElementById("chat-citation-1-1")).not.toBeNull();
    const markers = screen.getAllByRole("button", {
      name: "Jump to citation 1, machine-learning.pdf, page 2",
    });
    const newestMarker = markers.at(-1);
    if (!newestMarker) throw new Error("Latest citation marker was not rendered.");
    fireEvent.click(newestMarker);
    expect(document.activeElement?.id).toBe("chat-citation-1-1");
  });

  it("shows a clear not-found state and hint", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock.mockResolvedValueOnce(
      chatResponse("I could not find this in your documents."),
    );
    await submit("What is the capital of Australia?");

    expect(
      await screen.findByRole("heading", { name: "No matching information found" }),
    ).toBeTruthy();
    expect(screen.getByText("I could not find this in your documents.")).toBeTruthy();
    expect(screen.getByText(/rephrasing your question or upload more/i)).toBeTruthy();
  });

  it("shows an empty state and documents link when no ready documents exist", async () => {
    renderChat([{ ...readyDocument, status: "embedding_failed" }]);
    expect(await screen.findByText(/do not have any ready documents/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to Documents" }).getAttribute("href"))
      .toBe("/documents");
    expect((screen.getByRole("button", { name: "Ask" }) as HTMLButtonElement).disabled)
      .toBe(true);
  });

  it("drops selected document ids removed from the refreshed ready-document list", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fireEvent.click(screen.getByLabelText("machine-learning.pdf"));
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, [{
        ...readyDocument,
        id: "doc-2",
        filename: "new-ready-document.pdf",
      }]),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh ready documents" }));
    await waitFor(() =>
      expect(screen.queryByLabelText("machine-learning.pdf")).toBeNull(),
    );
    fetchMock.mockResolvedValueOnce(chatResponse("Answer.", []));
    await submit("Ask without stale restriction");
    await screen.findByText("Answer.");

    expect(JSON.parse(fetchMock.mock.calls[2][1]?.body as string)).toEqual({
      question: "Ask without stale restriction",
    });
  });

  it("cancels the request and explains that the backend may keep working", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock.mockImplementationOnce((_input, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("Aborted", "AbortError"));
        });
      }),
    );
    await submit("A question that will be cancelled");
    expect(
      await screen.findByText("Searching your documents and preparing a cited answer."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel response" }));

    expect(await screen.findByText(/server may continue processing/i)).toBeTruthy();
    expect(screen.getByText("A question that will be cancelled")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry this question" })).toBeNull();
  });

  it.each([
    ["422 validation", 422, "QUESTION_TOO_LONG", "Questions must be 2000 characters or shorter.", false],
    ["429 quota", 429, "CHAT_QUOTA_EXCEEDED", "The service is busy. Please try again in a minute.", true],
    ["503 search unavailable", 503, "CHAT_SEARCH_UNAVAILABLE", "Document search is temporarily unavailable. Please try again.", true],
    ["503 generation unavailable", 503, "CHAT_UNAVAILABLE", "Chat is temporarily unavailable. Please try again.", true],
  ])("shows a friendly %s message and retry state", async (_label, status, code, message, retryable) => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock.mockResolvedValueOnce(jsonResponse(status, {
      error: { code, message: "do not show this raw provider detail" },
    }));
    await submit("Ask a question");

    expect((await screen.findByRole("alert")).textContent).toContain(message);
    expect(screen.queryByText("do not show this raw provider detail")).toBeNull();
    expect(Boolean(screen.queryByRole("button", { name: "Retry this question" })))
      .toBe(retryable);
  });

  it("shows a friendly network error and can retry the same question", async () => {
    const fetchMock = renderChat();
    await screen.findByLabelText("machine-learning.pdf");
    fetchMock
      .mockRejectedValueOnce(new TypeError("private network error"))
      .mockResolvedValueOnce(chatResponse("Recovered answer [1].", [
        {
          number: 1,
          document_id: readyDocument.id,
          filename: readyDocument.filename,
          page_number: 1,
          snippet: "Recovered evidence.",
        },
      ]));
    await submit("Retry this exact question");
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Could not connect to the service. Check your connection and try again.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry this question" }));
    expect(await screen.findByText(/Recovered answer/)).toBeTruthy();
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual(
      JSON.parse(fetchMock.mock.calls[2][1]?.body as string),
    );
  });

  it("shows a friendly timeout error with retry", async () => {
    vi.useFakeTimers();
    const fetchMock = renderChat();
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    fetchMock.mockImplementationOnce((_input, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("Timed out", "AbortError"));
        });
      }),
    );
    const input = screen.getByLabelText("Your question");
    fireEvent.change(input, { target: { value: "This request will time out" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });
    expect(screen.getByRole("alert").textContent).toContain("That took longer than expected.");
    expect(screen.getByRole("button", { name: "Retry this question" })).toBeTruthy();
    vi.useRealTimers();
  });
});
