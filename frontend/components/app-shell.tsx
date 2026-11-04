"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { useAuth } from "./auth-provider";

const workspaceLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/chat", label: "Chat" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { status, user, signOut } = useAuth();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDialogRef = useRef<HTMLDialogElement>(null);
  const isWorkspaceRoute = workspaceLinks.some(
    ({ href }) => pathname === href || pathname.startsWith(`${href}/`),
  );

  useEffect(() => {
    const dialog = mobileDialogRef.current;
    if (!dialog) return;

    if (mobileMenuOpen && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLElement>("a, button")?.focus();
    } else if (!mobileMenuOpen && dialog.open) {
      dialog.close();
    }
  }, [mobileMenuOpen]);

  useEffect(() => {
    if (mobileDialogRef.current?.open) {
      mobileDialogRef.current.close();
      menuButtonRef.current?.focus();
    }
  }, [pathname]);

  function closeMobileMenu() {
    setMobileMenuOpen(false);
    if (mobileDialogRef.current?.open) mobileDialogRef.current.close();
    menuButtonRef.current?.focus();
  }

  function handleSignOut() {
    closeMobileMenu();
    signOut();
  }

  function handleMobileDialogKeyDown(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const dialog = mobileDialogRef.current;
    if (!dialog) return;
    const focusable = dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled])',
    );
    const first = focusable.item(0);
    const last = focusable.item(focusable.length - 1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <>
      {status === "authenticated" && isWorkspaceRoute ? (
        <div className="workspace-shell">
          <aside className="workspace-sidebar">
            <Link href="/dashboard" className="brand-link">
              AI Knowledge Assistant
            </Link>
            <nav aria-label="Workspace navigation" className="workspace-nav">
              {workspaceLinks.map(({ href, label }) => (
                <Link
                  aria-current={pathname === href ? "page" : undefined}
                  href={href}
                  key={href}
                >
                  {label}
                </Link>
              ))}
            </nav>
            <div className="workspace-account">
              {user?.email && <p className="account-email">{user.email}</p>}
              <button
                className="button-secondary workspace-logout"
                onClick={signOut}
                type="button"
              >
                Log out
              </button>
            </div>
          </aside>
          <div className="workspace-content">
            <header className="workspace-mobile-bar">
              <Link href="/dashboard" className="brand-link">
                AI Knowledge Assistant
              </Link>
              <button
                aria-controls="workspace-mobile-menu"
                aria-expanded={mobileMenuOpen}
                className="button-secondary"
                onClick={() => setMobileMenuOpen(true)}
                ref={menuButtonRef}
                type="button"
              >
                Menu
              </button>
            </header>
            <dialog
              aria-label="Workspace menu"
              className="workspace-mobile-dialog"
              id="workspace-mobile-menu"
              onCancel={(event) => {
                event.preventDefault();
                closeMobileMenu();
              }}
              onClose={() => setMobileMenuOpen(false)}
              onKeyDown={handleMobileDialogKeyDown}
              ref={mobileDialogRef}
            >
              <div className="workspace-mobile-dialog-inner">
                <div className="workspace-menu-heading">
                  <span className="section-subheading">Navigation</span>
                  <button
                    aria-label="Close menu"
                    className="button-secondary"
                    onClick={() => closeMobileMenu()}
                    type="button"
                  >
                    Close
                  </button>
                </div>
                {user?.email && <p className="account-email">{user.email}</p>}
                <nav aria-label="Mobile workspace navigation" className="workspace-nav">
                  {workspaceLinks.map(({ href, label }) => (
                    <Link
                      aria-current={pathname === href ? "page" : undefined}
                      href={href}
                      key={href}
                      onClick={closeMobileMenu}
                    >
                      {label}
                    </Link>
                  ))}
                </nav>
                <button
                  className="button-secondary workspace-logout"
                  onClick={handleSignOut}
                  type="button"
                >
                  Log out
                </button>
              </div>
            </dialog>
            {children}
          </div>
        </div>
      ) : (
        <>
          <header className="site-header">
            <div className="site-header-inner">
              <Link href="/" className="brand-link">
                AI Knowledge Assistant
              </Link>
              <nav aria-label="Main navigation" className="desktop-nav">
                {status === "authenticated" ? (
                  <Link href="/dashboard">Dashboard</Link>
                ) : (
                  <>
                    <Link href="/login">Log in</Link>
                    <Link className="button-primary" href="/signup">
                      Sign up
                    </Link>
                  </>
                )}
              </nav>
              <details className="mobile-nav">
                <summary>Menu</summary>
                <nav aria-label="Mobile navigation">
                  {status === "authenticated" ? (
                    <Link href="/dashboard">Dashboard</Link>
                  ) : (
                    <>
                      <Link href="/login">Log in</Link>
                      <Link href="/signup">Sign up</Link>
                    </>
                  )}
                </nav>
              </details>
            </div>
          </header>
          {children}
        </>
      )}
    </>
  );
}
