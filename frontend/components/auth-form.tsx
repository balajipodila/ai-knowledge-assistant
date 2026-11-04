"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";
import type { AuthResponse } from "@/lib/types";

type Mode = "signup" | "login";
type FieldErrors = { email?: string; password?: string };

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function authFieldErrors(fields: Record<string, string>): FieldErrors {
  const errors: FieldErrors = {};
  if (fields.email) errors.email = fields.email;
  if (fields.password) errors.password = fields.password;
  return errors;
}

function validate(email: string, password: string, mode: Mode): FieldErrors {
  const errors: FieldErrors = {};
  const normalizedEmail = email.trim();
  if (!normalizedEmail) {
    errors.email = "Enter your email address.";
  } else if (normalizedEmail.length > 320 || !emailPattern.test(normalizedEmail)) {
    errors.email = "Enter a valid email address (maximum 320 characters).";
  }
  if (!password) {
    errors.password = "Enter your password.";
  } else if (mode === "signup" && password.length < 12) {
    errors.password = "Use at least 12 characters.";
  } else if (password.length > 128) {
    errors.password = "Use no more than 128 characters.";
  }
  return errors;
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const { signIn } = useAuth();
  const isSignup = mode === "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [expiredNotice, setExpiredNotice] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(
      () =>
        setExpiredNotice(
          new URLSearchParams(window.location.search).get("reason") === "expired",
        ),
      0,
    );
    return () => window.clearTimeout(timer);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    const errors = validate(email, password, mode);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsSubmitting(true);
    try {
      const response = await apiRequest<AuthResponse>(
        isSignup ? "/auth/signup" : "/auth/login",
        {
          auth: false,
          body: { email: email.trim(), password },
        },
      );
      signIn(response);
      router.replace("/documents");
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(authFieldErrors(error.fields));
        setFormError(error.message);
      } else {
        setFormError("Could not complete the request. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 items-start px-6 py-12 sm:py-16">
      <section className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-800">
          {isSignup ? "Get started" : "Welcome back"}
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
          {isSignup ? "Create your account" : "Log in"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {isSignup
            ? "Use a valid email address and a password between 12 and 128 characters."
            : "Sign in to access your documents and cited chat."}
        </p>
        {expiredNotice && (
          <p className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-950" role="status">
            Your session expired. Please log in again.
          </p>
        )}
        {formError && (
          <p className="mt-5 rounded-lg bg-rose-50 p-3 text-sm text-rose-800" role="alert">
            {formError}
          </p>
        )}
        <form className="mt-6 space-y-5" onSubmit={handleSubmit} noValidate>
          <div>
            <label className="block text-sm font-semibold text-slate-800" htmlFor="email">
              Email address
            </label>
            <input
              autoComplete="email"
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-950"
              id="email"
              maxLength={320}
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              value={email}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? "email-error" : undefined}
            />
            {fieldErrors.email && (
              <p className="mt-1 text-sm text-rose-700" id="email-error">
                {fieldErrors.email}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-800" htmlFor="password">
              Password
            </label>
            <input
              autoComplete={isSignup ? "new-password" : "current-password"}
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-950"
              id="password"
              maxLength={128}
              minLength={isSignup ? 12 : undefined}
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={fieldErrors.password ? "password-error" : "password-help"}
            />
            {fieldErrors.password ? (
              <p className="mt-1 text-sm text-rose-700" id="password-error">
                {fieldErrors.password}
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-500" id="password-help">
                {isSignup
                  ? "12–128 characters; spaces are allowed and are not trimmed."
                  : "Maximum 128 characters."}
              </p>
            )}
          </div>
          <button
            className="w-full rounded-lg bg-slate-950 px-4 py-3 font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting
              ? isSignup
                ? "Creating account…"
                : "Logging in…"
              : isSignup
                ? "Create account"
                : "Log in"}
          </button>
        </form>
        <p className="mt-6 text-sm text-slate-600">
          {isSignup ? "Already have an account?" : "New to the assistant?"}{" "}
          <Link
            className="font-semibold text-cyan-800 underline underline-offset-2"
            href={isSignup ? "/login" : "/signup"}
          >
            {isSignup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
