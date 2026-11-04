"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useAuth } from "./auth-provider";

export function AppShell({ children }: { children: ReactNode }) {
  const { status, user, signOut } = useAuth();

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Link
            href="/"
            className="text-lg font-bold tracking-tight text-slate-950"
          >
            AI Knowledge Assistant
          </Link>
          <nav aria-label="Main navigation" className="flex items-center gap-4 text-sm">
            {status === "authenticated" ? (
              <>
                <Link className="font-medium text-slate-700 hover:text-cyan-800" href="/documents">
                  Documents
                </Link>
                <Link className="font-medium text-slate-700 hover:text-cyan-800" href="/chat">
                  Chat
                </Link>
                <span className="hidden text-slate-500 sm:inline">{user?.email}</span>
                <button
                  type="button"
                  className="rounded-md border border-slate-300 px-3 py-2 font-semibold text-slate-800 hover:bg-slate-50"
                  onClick={signOut}
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link className="font-medium text-slate-700 hover:text-cyan-800" href="/login">
                  Log in
                </Link>
                <Link
                  className="rounded-md bg-slate-950 px-3 py-2 font-semibold text-white hover:bg-slate-800"
                  href="/signup"
                >
                  Sign up
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      {children}
    </>
  );
}
