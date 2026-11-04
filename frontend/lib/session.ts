import type { User } from "./types";

const SESSION_KEY = "ai-knowledge-assistant.session";

export type AuthSession = {
  accessToken: string;
  expiresAt: number;
  user: User;
};

type AuthResponse = {
  access_token: string;
  expires_in: number;
  user: User;
};

export function readSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const stored = window.sessionStorage.getItem(SESSION_KEY);
  if (!stored) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(stored);
    if (
      typeof value === "object" &&
      value !== null &&
      "accessToken" in value &&
      typeof value.accessToken === "string" &&
      "expiresAt" in value &&
      typeof value.expiresAt === "number" &&
      "user" in value &&
      typeof value.user === "object" &&
      value.user !== null &&
      "id" in value.user &&
      typeof value.user.id === "string" &&
      "email" in value.user &&
      typeof value.user.email === "string" &&
      "created_at" in value.user &&
      typeof value.user.created_at === "string"
    ) {
      return {
        accessToken: value.accessToken,
        expiresAt: value.expiresAt,
        user: {
          id: value.user.id,
          email: value.user.email,
          created_at: value.user.created_at,
        },
      };
    }
  } catch {
    window.sessionStorage.removeItem(SESSION_KEY);
    return null;
  }

  window.sessionStorage.removeItem(SESSION_KEY);
  return null;
}

export function saveSession(response: AuthResponse): AuthSession {
  const session: AuthSession = {
    accessToken: response.access_token,
    expiresAt: Date.now() + response.expires_in * 1000,
    user: response.user,
  };
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
  return session;
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(SESSION_KEY);
  }
}
