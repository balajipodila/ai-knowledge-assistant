"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError, apiRequest } from "@/lib/api";
import type { AuthResponse } from "@/lib/types";

export function LandingActions() {
  const { status, signIn } = useAuth();
  const router = useRouter();
  const [isStartingDemo, setIsStartingDemo] = useState(false);
  const [demoError, setDemoError] = useState("");

  if (status === "authenticated") {
    return (
      <div className="hero-actions">
        <Link className="button-primary" href="/dashboard">
          Go to your dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="hero-actions">
      <button
        className="button-primary"
        disabled={isStartingDemo}
        onClick={async () => {
          setDemoError("");
          setIsStartingDemo(true);
          try {
            const response = await apiRequest<AuthResponse>("/auth/demo", {
              method: "POST",
              auth: false,
            });
            signIn(response);
            router.push("/dashboard");
          } catch (error) {
            setDemoError(
              error instanceof ApiError
                ? error.message
                : "The demo is temporarily unavailable. Please try again later.",
            );
          } finally {
            setIsStartingDemo(false);
          }
        }}
        type="button"
      >
        {isStartingDemo ? "Starting demo…" : "Try demo"}
      </button>
      <Link className="button-primary" href="/signup">
        Create an account
      </Link>
      <Link className="button-secondary" href="/login">
        Log in
      </Link>
      {demoError && (
        <p className="notice notice-error" role="alert">
          {demoError}
        </p>
      )}
    </div>
  );
}
