"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "./auth-provider";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status, sessionExpired } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(sessionExpired ? "/login?reason=expired" : "/login");
    }
  }, [router, sessionExpired, status]);

  if (status === "checking") {
    return (
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12" aria-live="polite">
        <p className="page-description">Checking your session…</p>
      </main>
    );
  }
  if (status !== "authenticated") {
    return (
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12" aria-live="polite">
        <p className="page-description">Redirecting to sign in…</p>
      </main>
    );
  }
  return <>{children}</>;
}
