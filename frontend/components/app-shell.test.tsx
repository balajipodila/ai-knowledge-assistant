import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";
import { AuthProvider } from "./auth-provider";

describe("app shell navigation", () => {
  it("provides a keyboard-operable native mobile navigation menu", () => {
    render(
      <AuthProvider>
        <AppShell>
          <main id="main-content">Page content</main>
        </AppShell>
      </AuthProvider>,
    );

    const menu = screen.getByText("Menu");
    expect(menu.tagName).toBe("SUMMARY");
    fireEvent.click(menu);

    const mobileNav = screen.getByRole("navigation", {
      name: "Mobile navigation",
    });
    expect(within(mobileNav).getByRole("link", { name: "Sign up" })).toBeTruthy();
  });
});
