"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

export function LandingActions() {
  const { status } = useAuth();

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
      <Link className="button-primary" href="/signup">
        Create an account
      </Link>
      <Link className="button-secondary" href="/login">
        Log in
      </Link>
    </div>
  );
}
