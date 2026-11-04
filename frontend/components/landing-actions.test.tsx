import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "./auth-provider";
import { LandingActions } from "./landing-actions";
import { saveSession } from "@/lib/session";

describe("landing actions", () => {
  it("offers a dashboard link to signed-in users", async () => {
    saveSession({
      access_token: "landing-test-token",
      expires_in: 1800,
      user: {
        id: "user-1",
        email: "person@example.test",
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    render(
      <AuthProvider>
        <LandingActions />
      </AuthProvider>,
    );

    expect(await screen.findByRole("link", { name: "Go to your dashboard" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Create an account" })).toBeNull();
  });
});
