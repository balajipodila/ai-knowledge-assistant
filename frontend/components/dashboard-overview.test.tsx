import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardOverview } from "./dashboard-overview";
import { saveSession } from "@/lib/session";

const documents = [
  {
    id: "doc-1",
    filename: "ready.pdf",
    status: "ready",
    page_count: 7,
    created_at: "2026-10-12T10:30:00Z",
    failure_reason: null,
  },
  {
    id: "doc-2",
    filename: "failed.pdf",
    status: "failed",
    page_count: 2,
    created_at: "2026-10-13T10:30:00Z",
    failure_reason: "Text extraction failed.",
  },
  {
    id: "doc-3",
    filename: "embedding-failed.pdf",
    status: "embedding_failed",
    page_count: 4,
    created_at: "2026-10-14T10:30:00Z",
    failure_reason: "Embedding service unavailable.",
  },
  {
    id: "doc-4",
    filename: "processing.pdf",
    status: "processing",
    page_count: 1,
    created_at: "2026-10-11T10:30:00Z",
    failure_reason: null,
  },
];

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

function renderDashboard() {
  saveSession({
    access_token: "dashboard-test-token",
    expires_in: 1800,
    user: {
      id: "user-1",
      email: "person@example.test",
      created_at: "2026-01-01T00:00:00Z",
    },
  });
  return render(<DashboardOverview />);
}

describe("dashboard overview", () => {
  it("calculates document totals from the API list and shows newest uploads first", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, documents),
    );
    renderDashboard();

    await screen.findByText("embedding-failed.pdf");
    const overview = screen.getByRole("region", { name: "Document overview" });
    expect(within(overview).getByText("Total documents").nextElementSibling?.textContent)
      .toBe("4");
    expect(within(overview).getByText("Ready").nextElementSibling?.textContent).toBe("1");
    expect(
      within(overview).getByText("Failed or embedding failed").nextElementSibling?.textContent,
    ).toBe("2");
    expect(within(overview).getByText("Total pages").nextElementSibling?.textContent).toBe("14");

    const uploadList = screen.getByRole("list");
    const uploadNames = within(uploadList)
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(uploadNames).toEqual([
      "embedding-failed.pdf",
      "failed.pdf",
      "ready.pdf",
      "processing.pdf",
    ]);
    expect(within(uploadList).getByText("Embedding failed")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/documents");

    const actions = screen.getByRole("navigation", { name: "Quick actions" });
    expect(within(actions).getByRole("link", { name: "Upload a PDF" })).toBeTruthy();
    expect(within(actions).getByRole("link", { name: "Ask a question" })).toBeTruthy();
  });

  it("shows a real empty state for an account with no documents", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, []));
    renderDashboard();

    expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Upload your first PDF" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Document overview" })).toBeNull();
  });

  it("shows a loading state while the document request is pending", async () => {
    let resolveFetch!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );
    renderDashboard();

    expect(screen.getByRole("status").textContent).toContain("Loading your dashboard");
    resolveFetch(jsonResponse(200, []));
    expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeTruthy();
  });

  it("offers a retry after an API error", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse(503, { error: { code: "SERVICE_UNAVAILABLE" } }),
      )
      .mockResolvedValueOnce(jsonResponse(200, []));
    renderDashboard();

    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeTruthy();
  });
});
