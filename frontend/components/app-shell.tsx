"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useAuth } from "./auth-provider";

export function AppShell({ children }: { children: ReactNode }) {
  const { status, user, signOut } = useAuth();

  return (
    <>
      <header className="site-header">
        <div className="site-header-inner">
          <Link href="/" className="brand-link">
            AI Knowledge Assistant
          </Link>
          <nav aria-label="Main navigation" className="desktop-nav">
            {status === "authenticated" ? (
              <>
                <Link href="/documents">
                  Documents
                </Link>
                <Link href="/chat">
                  Chat
                </Link>
                <span className="account-email">{user?.email}</span>
                <button
                  type="button"
                  className="button-secondary"
                  onClick={signOut}
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link href="/login">
                  Log in
                </Link>
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
                <>
                  <Link href="/documents">Documents</Link>
                  <Link href="/chat">Chat</Link>
                  <button type="button" onClick={signOut}>
                    Log out
                  </button>
                </>
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
  );
}
