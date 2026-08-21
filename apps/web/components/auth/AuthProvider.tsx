"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import AuthModal from "./AuthModal";

export type AuthUser = { id: string; name: string; email: string };
type AuthContextValue = { user: AuthUser | null; isAuthenticated: boolean; isLoading: boolean; login: (email: string, password: string, remember: boolean) => Promise<void>; register: (name: string, email: string, password: string, remember: boolean) => Promise<void>; requestPasswordReset: (email: string) => Promise<string>; resetPassword: (token: string, password: string) => Promise<string>; logout: () => Promise<void>; requireAuth: (action: () => void | Promise<void>) => void; openAuth: () => void };
const AuthContext = createContext<AuthContextValue | null>(null);
// Auth is proxied through this same-origin route so secure cookies work when
// the API remains private inside Railway's network.
const API = "/api";

async function readError(response: Response, fallback: string) { const payload = await response.json().catch(() => null) as { error?: string } | null; return payload?.error || fallback; }
async function csrf() {
  const response = await fetch(`${API}/auth/csrf`, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error(await readError(response, "Secure sign-in is temporarily unavailable. Please try again shortly."));
  const payload = await response.json().catch(() => null) as { csrfToken?: string } | null;
  if (!payload?.csrfToken) throw new Error("Secure sign-in is temporarily unavailable. Please try again shortly.");
  return payload.csrfToken;
}
async function authRequest(path: string, body?: unknown) {
  const token = await csrf();
  const response = await fetch(`${API}${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: body === undefined ? undefined : JSON.stringify(body) });
  const payload = await response.json().catch(() => ({})) as { user?: AuthUser; error?: string };
  if (!response.ok || !payload.user) {
    if (response.status === 401) throw new Error("Incorrect email or password. Please try again.");
    throw new Error(payload.error || "We could not complete that request. Please try again.");
  }
  return payload.user;
}
async function resetRequest(path: string, body: unknown) {
  const response = await fetch(`${API}${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
  if (!response.ok) throw new Error(payload.error || "We could not complete that request. Please try again.");
  return payload.message || "If an account matches that email, a reset link will arrive shortly.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const deferredAction = useRef<(() => void | Promise<void>) | null>(null);
  useEffect(() => { fetch(`${API}/auth/me`, { credentials: "include" }).then(async (response) => response.ok ? (await response.json() as { user: AuthUser }).user : null).then(setUser).catch(() => setUser(null)).finally(() => setIsLoading(false)); }, []);
  useEffect(() => {
    if (isLoading || !deferredAction.current) return;
    if (user) {
      const action = deferredAction.current;
      deferredAction.current = null;
      void action();
      return;
    }
    setModalOpen(true);
  }, [isLoading, user]);
  const complete = useCallback((nextUser: AuthUser) => { setUser(nextUser); setModalOpen(false); const action = deferredAction.current; deferredAction.current = null; void action?.(); }, []);
  const login = useCallback(async (email: string, password: string, remember: boolean) => complete(await authRequest("/auth/login", { email, password, remember })), [complete]);
  const register = useCallback(async (name: string, email: string, password: string, remember: boolean) => complete(await authRequest("/auth/register", { name, email, password, remember })), [complete]);
  const requestPasswordReset = useCallback((email: string) => resetRequest("/auth/password-reset/request", { email }), []);
  const resetPassword = useCallback((token: string, password: string) => resetRequest("/auth/password-reset/confirm", { token, password }), []);
  const logout = useCallback(async () => { const token = await csrf(); await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } }); setUser(null); }, []);
  const requireAuth = useCallback((action: () => void | Promise<void>) => {
    if (user) { void action(); return; }
    deferredAction.current = action;
    if (!isLoading) setModalOpen(true);
  }, [isLoading, user]);
  const value = useMemo(() => ({ user, isAuthenticated: !!user, isLoading, login, register, requestPasswordReset, resetPassword, logout, requireAuth, openAuth: () => setModalOpen(true) }), [user, isLoading, login, register, requestPasswordReset, resetPassword, logout, requireAuth]);
  const currentPath = typeof window === "undefined" ? "/" : `${window.location.pathname}${window.location.search}`;
  const googleUrl = `${API}/auth/google?return_to=${encodeURIComponent(currentPath)}`;
  return <AuthContext.Provider value={value}>{children}<AuthModal open={modalOpen} onClose={() => { deferredAction.current = null; setModalOpen(false); }} onLogin={login} onRegister={register} onRequestPasswordReset={requestPasswordReset} googleUrl={googleUrl} /></AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }
export function useRequireAuth(action: () => void | Promise<void>) { const { requireAuth } = useAuth(); return useCallback(() => requireAuth(action), [requireAuth, action]); }
