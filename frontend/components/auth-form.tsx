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

function FormStatusIcon({ kind }: { kind: "error" | "info" }) {
  return (
    <svg aria-hidden="true" className="notice-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      {kind === "error" ? (
        <><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6m0-6-6 6" /></>
      ) : (
        <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></>
      )}
    </svg>
  );
}

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
  const [expiredReason, setExpiredReason] = useState<"demo" | "regular" | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(
      () =>
        setExpiredReason(
          new URLSearchParams(window.location.search).get("reason") === "demo-expired"
            ? "demo"
            : new URLSearchParams(window.location.search).get("reason") === "expired"
              ? "regular"
              : null,
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
      router.replace("/dashboard");
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
    <main className="auth-main" id="main-content">
      <section className="glass-panel glass-blur auth-card">
        <p className="eyebrow">
          {isSignup ? "Get started" : "Welcome back"}
        </p>
        <h1 className="metallic-heading">
          {isSignup ? "Create your account" : "Log in"}
        </h1>
        <p className="auth-description">
          {isSignup
            ? "Use a valid email address and a password between 12 and 128 characters."
            : "Sign in to access your documents and cited chat."}
        </p>
        {isSignup && (
          <p className="auth-help mt-2 text-xs">
            We do not keep your original PDF file. We store extracted text passages and numeric embeddings so we can search them, until you delete the document. Text from your documents is sent to the Google Gemini API to create embeddings and answers. Do not upload sensitive, confidential or personal documents.
          </p>
        )}
        {expiredReason && (
          <p className="notice notice-info auth-notice" role="status">
            <FormStatusIcon kind="info" />
            {expiredReason === "demo"
              ? "Demo session ended. Start a new demo from the home page."
              : "Your session expired. Please log in again."}
          </p>
        )}
        {formError && (
          <p className="notice notice-error auth-error" role="alert">
            <FormStatusIcon kind="error" />
            {formError}
          </p>
        )}
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label htmlFor="email">
              Email address
            </label>
            <input
              autoComplete="email"
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
              <p className="auth-field-error" id="email-error">
                <FormStatusIcon kind="error" />
                {fieldErrors.email}
              </p>
            )}
          </div>
          <div className="auth-field">
            <label htmlFor="password">
              Password
            </label>
            <input
              autoComplete={isSignup ? "new-password" : "current-password"}
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
              <p className="auth-field-error" id="password-error">
                <FormStatusIcon kind="error" />
                {fieldErrors.password}
              </p>
            ) : (
              <p className="auth-help" id="password-help">
                {isSignup
                  ? "12–128 characters; spaces are allowed and are not trimmed."
                  : "Maximum 128 characters."}
              </p>
            )}
          </div>
          <button
            className="button-primary auth-submit"
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
        <p className="auth-switch">
          {isSignup ? "Already have an account?" : "New to the assistant?"}{" "}
          <Link href={isSignup ? "/login" : "/signup"}>
            {isSignup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
