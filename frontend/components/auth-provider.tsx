"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import { SESSION_EXPIRED_EVENT } from "@/lib/api";
import { clearSession, readSession, saveSession, type AuthSession } from "@/lib/session";
import type { AuthResponse, User } from "@/lib/types";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  sessionExpired: boolean;
  signIn: (response: AuthResponse) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<User | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  const expireSession = useCallback(() => {
    const wasDemoSession = readSession()?.user.is_demo === true;
    clearSession();
    setUser(null);
    setStatus("unauthenticated");
    setSessionExpired(true);
    router.replace(wasDemoSession ? "/login?reason=demo-expired" : "/login?reason=expired");
  }, [router]);

  useEffect(() => {
    let expiryTimer: number | undefined;
    const checkTimer = window.setTimeout(() => {
      const stored: AuthSession | null = readSession();
      if (!stored) {
        setStatus("unauthenticated");
        return;
      }
      if (stored.expiresAt <= Date.now()) {
        expireSession();
        return;
      }

      setUser(stored.user);
      setStatus("authenticated");
      expiryTimer = window.setTimeout(
        expireSession,
        Math.max(0, stored.expiresAt - Date.now()),
      );
    }, 0);
    return () => {
      window.clearTimeout(checkTimer);
      if (expiryTimer !== undefined) window.clearTimeout(expiryTimer);
    };
  }, [expireSession, status]);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, [expireSession]);

  const signIn = useCallback((response: AuthResponse) => {
    saveSession(response);
    setSessionExpired(false);
    setUser(response.user);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
    setSessionExpired(false);
    setStatus("unauthenticated");
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ status, user, sessionExpired, signIn, signOut }),
    [status, user, sessionExpired, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
