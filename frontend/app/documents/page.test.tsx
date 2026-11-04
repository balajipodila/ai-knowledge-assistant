import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../components/auth-provider";
import DocumentsPage from "./page";
import { saveSession } from "../../lib/session";

const existingDocument = {
  id: "doc-1",
  filename: "guide.pdf",
  status: "ready",
  page_count: 4,
  created_at: "2026-10-12T10:30:00Z",
  failure_reason: null,
};

const failedEmbeddingDocument = {
  ...existingDocument,
  id: "doc-2",
  filename: "failed-embedding.pdf",
  status: "embedding_failed",
  failure_reason: "The embedding provider was unavailable.",
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

function noContentResponse(status = 204): Response {
  return { status, ok: true, json: async () => undefined } as Response;
}

function renderDocuments() {
  saveSession({
    access_token: "documents-test-token",
    expires_in: 1800,
    user: {
      id: "user-1",
      email: "person@example.test",
      created_at: "2026-01-01T00:00:00Z",
    },
  });
  return render(
    <AuthProvider>
      <DocumentsPage />
    </AuthProvider>,
  );
}

function pdfFile(name = "sample.pdf", data = "%PDF-1.7\nsample content") {
  return new File([data], name, { type: "application/pdf" });
}

function listResponse(documents: object[]) {
  return jsonResponse(200, documents);
}

describe("documents page", () => {
  it("accepts a dropped PDF and exposes the drag state accessibly", async () => {
    const uploaded = { ...existingDocument, status: "processing" };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(201, { ...uploaded, chunk_count: 2, duplicate: false }),
      )
      .mockResolvedValueOnce(listResponse([uploaded]));
    renderDocuments();
    await screen.findByText("No documents yet");

    const dropzone = screen.getByText(/Drag a PDF here/).closest(".upload-dropzone");
    expect(dropzone).not.toBeNull();
    fireEvent.dragOver(dropzone as HTMLElement);
    expect(dropzone?.getAttribute("data-drag-active")).toBe("true");
    fireEvent.drop(dropzone as HTMLElement, {
      dataTransfer: { files: [pdfFile()] },
    });

    expect(await screen.findByText("Selected: sample.pdf")).toBeTruthy();
    expect(dropzone?.getAttribute("data-drag-active")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
    await screen.findByText("Upload complete. Current status: Processing.");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("rejects a non-PDF file and a file over the backend's 10 MiB default", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      listResponse([]),
    );
    renderDocuments();
    await screen.findByText("No documents yet");

    const input = screen.getByLabelText("Choose a PDF");
    fireEvent.change(input, {
      target: { files: [new File(["not pdf"], "notes.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Choose a PDF file with a .pdf extension.",
    );

    const tooLarge = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "large.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(input, { target: { files: [tooLarge] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "The PDF must be 10 MiB or smaller.",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects a renamed non-PDF using its signature before upload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      listResponse([]),
    );
    renderDocuments();
    await screen.findByText("No documents yet");
    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
      target: { files: [pdfFile("fake.pdf", "not a pdf")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "This file does not appear to be a valid PDF.",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uploads a PDF with the extended timeout and highlights a duplicate", async () => {
    const returnedDocument = { ...existingDocument, status: "processing" };
    let resolveUpload!: (response: Response) => void;
    const pendingUpload = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([existingDocument]))
      .mockReturnValueOnce(pendingUpload)
      .mockResolvedValueOnce(listResponse([returnedDocument]));
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");
    renderDocuments();
    await screen.findByText("guide.pdf");

    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    const uploadButton = screen.getByRole("button", { name: "Uploading…" });
    expect((uploadButton as HTMLButtonElement).disabled).toBe(true);
    expect(
      screen.getByText(
        "Processing your PDF. This can take a minute; please keep this page open.",
      ),
    ).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    resolveUpload(
      jsonResponse(200, { ...returnedDocument, chunk_count: 3, duplicate: true }),
    );

    expect((await screen.findByRole("status")).textContent).toContain(
      "This PDF was already uploaded. Its existing document is highlighted below.",
    );
    expect((await screen.findByTestId("document-doc-1")).getAttribute("data-highlighted"))
      .toBe("true");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const uploadOptions = fetchMock.mock.calls[1][1];
    expect(uploadOptions?.signal).toBeDefined();
    expect(uploadOptions?.body).toBeInstanceOf(FormData);
    expect(setTimeoutSpy.mock.calls.some(([, delay]) => delay === 120_000)).toBe(true);
  });

  it("reports a duplicate whose existing extraction had failed without claiming it was reprocessed", async () => {
    const failed = { ...existingDocument, status: "failed" };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(200, { ...failed, chunk_count: 0, duplicate: true }),
      )
      .mockResolvedValueOnce(listResponse([failed]));
    renderDocuments();
    await screen.findByText("No documents yet");
    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect((await screen.findByRole("status")).textContent).toContain(
      "This PDF was already uploaded, but its previous processing attempt failed. Re-uploading did not restart it.",
    );
  });

  it("opens, cancels and closes the delete dialog with Escape", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      listResponse([existingDocument]),
    );
    renderDocuments();
    const deleteButton = await screen.findByRole("button", {
      name: "Delete guide.pdf",
    });
    fireEvent.click(deleteButton);
    let dialog = screen.getByRole("dialog", { name: "Delete document?" });
    expect(dialog.hasAttribute("open")).toBe(true);

    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(deleteButton);
    dialog = screen.getByRole("dialog", { name: "Delete document?" });
    fireEvent(
      dialog,
      new Event("cancel", { bubbles: false, cancelable: true }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("confirms delete and refreshes the list", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([existingDocument]))
      .mockResolvedValueOnce(noContentResponse())
      .mockResolvedValueOnce(listResponse([]));
    renderDocuments();
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete guide.pdf" }),
    );
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Delete document?" })).getByRole(
        "button",
        { name: "Delete document" },
      ),
    );

    expect(await screen.findByText("No documents yet")).toBeTruthy();
    expect((await screen.findByRole("status")).textContent).toContain(
      "Document deleted.",
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("refreshes without an error when the delete request returns 404", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([existingDocument]))
      .mockResolvedValueOnce(jsonResponse(404, { detail: "gone" }))
      .mockResolvedValueOnce(listResponse([]));
    renderDocuments();
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete guide.pdf" }),
    );
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Delete document?" })).getByRole(
        "button",
        { name: "Delete document" },
      ),
    );

    expect(await screen.findByText("No documents yet")).toBeTruthy();
    expect((await screen.findByRole("status")).textContent).toContain(
      "That document was already gone. The list has been refreshed.",
    );
  });

  it("shows retry only for embedding_failed and refreshes after retry", async () => {
    const updated = { ...failedEmbeddingDocument, status: "ready", failure_reason: null };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([existingDocument, failedEmbeddingDocument]))
      .mockResolvedValueOnce(jsonResponse(200, updated))
      .mockResolvedValueOnce(listResponse([existingDocument, updated]));
    renderDocuments();
    const retryButton = await screen.findByRole("button", {
      name: "Retry embedding for failed-embedding.pdf",
    });
    expect(
      screen.queryByRole("button", { name: "Retry embedding for guide.pdf" }),
    ).toBeNull();
    fireEvent.click(retryButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect((await screen.findByRole("status")).textContent).toContain(
      "Embedding retry finished. Current status: Ready.",
    );
    expect(screen.queryByRole("button", {
      name: "Retry embedding for failed-embedding.pdf",
    })).toBeNull();
  });

  it("keeps a pending retry state on its row only", async () => {
    const secondFailedDocument = {
      ...failedEmbeddingDocument,
      id: "doc-3",
      filename: "second-failed.pdf",
    };
    let resolveRetry!: (response: Response) => void;
    const pendingRetry = new Promise<Response>((resolve) => {
      resolveRetry = resolve;
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        listResponse([failedEmbeddingDocument, secondFailedDocument]),
      )
      .mockReturnValueOnce(pendingRetry)
      .mockResolvedValueOnce(
        listResponse([
          { ...failedEmbeddingDocument, status: "ready", failure_reason: null },
          secondFailedDocument,
        ]),
      );
    renderDocuments();
    const firstRetry = await screen.findByRole("button", {
      name: "Retry embedding for failed-embedding.pdf",
    });
    const secondRetry = screen.getByRole("button", {
      name: "Retry embedding for second-failed.pdf",
    });
    fireEvent.click(firstRetry);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect((firstRetry as HTMLButtonElement).disabled).toBe(true);
    expect((secondRetry as HTMLButtonElement).disabled).toBe(false);
    resolveRetry(jsonResponse(200, {
      ...failedEmbeddingDocument,
      status: "ready",
      failure_reason: null,
    }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it("shows a friendly list error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(503, { error: { code: "SERVICE_UNAVAILABLE" } }),
    );
    renderDocuments();

    expect((await screen.findByRole("alert")).textContent).toContain(
      "The service is temporarily unavailable. Please try again shortly.",
    );
  });

  it("shows a readable server-side PDF validation error", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(listResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(413, { error: { code: "FILE_TOO_LARGE", message: "private" } }),
      );
    renderDocuments();
    await screen.findByText("No documents yet");
    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "The PDF exceeds the server's configured size limit.",
    );
    expect(screen.queryByText("private")).toBeNull();
  });
});
