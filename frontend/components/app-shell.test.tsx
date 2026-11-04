import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";
import { AuthProvider } from "./auth-provider";
import { saveSession } from "@/lib/session";

function renderWorkspace(pathname = "/documents") {
  window.history.pushState({}, "", pathname);
  saveSession({
    access_token: "shell-test-token",
    expires_in: 1800,
    user: {
      id: "user-1",
      email: "person@example.test",
      created_at: "2026-01-01T00:00:00Z",
    },
  });
  return render(
    <AuthProvider>
      <AppShell>
        <main id="main-content">Page content</main>
      </AppShell>
    </AuthProvider>,
  );
}

describe("app shell navigation", () => {
  it("shows active desktop navigation and the existing signed-in email", async () => {
    renderWorkspace("/documents");

    const navigation = await screen.findByRole("navigation", {
      name: "Workspace navigation",
    });
    expect(within(navigation).getByRole("link", { name: "Dashboard" })).toBeTruthy();
    expect(
      within(navigation).getByRole("link", { name: "Documents" }).getAttribute("aria-current"),
    ).toBe("page");
    expect(within(navigation).getByRole("link", { name: "Chat" }).getAttribute("aria-current"))
      .toBeNull();
    expect(
      within(screen.getByRole("complementary")).getByText("person@example.test"),
    ).toBeTruthy();
  });

  it("opens the mobile menu with focus, traps keyboard focus, and closes on Escape", async () => {
    renderWorkspace("/chat");
    const menuButton = await screen.findByRole("button", { name: "Menu" });
    fireEvent.click(menuButton);

    const dialog = screen.getByRole("dialog", { name: "Workspace menu" });
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(document.activeElement).toBe(
      within(dialog).getByRole("button", { name: "Close menu" }),
    );
    expect(
      within(dialog).getByRole("link", { name: "Chat" }).getAttribute("aria-current"),
    ).toBe("page");

    const logout = within(dialog).getByRole("button", { name: "Log out" });
    logout.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(
      within(dialog).getByRole("button", { name: "Close menu" }),
    );

    fireEvent(dialog, new Event("cancel", { bubbles: false, cancelable: true }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(menuButton);
    expect(menuButton.getAttribute("aria-expanded")).toBe("false");
  });
});
