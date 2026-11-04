import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../components/auth-provider";
import { AuthForm } from "../components/auth-form";

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

function renderForm(mode: "signup" | "login" = "signup") {
  return render(
    <AuthProvider>
      <AuthForm mode={mode} />
    </AuthProvider>,
  );
}

describe("authentication form", () => {
  it("shows field errors for invalid signup without calling the API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderForm();
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "not-an-email" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("Enter a valid email address (maximum 320 characters)."),
    ).toBeTruthy();
    expect(screen.getByText("Use at least 12 characters.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stores the signup token and goes straight to the workspace", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(201, {
        access_token: "signup-test-token",
        token_type: "bearer",
        expires_in: 1800,
        user: {
          id: "user-1",
          email: "person@example.test",
          created_at: "2026-01-01T00:00:00Z",
        },
      }),
    );
    renderForm();
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "person@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "correct horse battery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(window.sessionStorage.length).toBe(1);
    });
    expect(window.sessionStorage.getItem("ai-knowledge-assistant.session"))
      .toContain("signup-test-token");
  });
});
