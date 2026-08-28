"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import AuthModal from "./AuthModal";

export type AuthUser = { id: string; name: string; email: string };
/** Values collected by the sign-up form for Cognito's required attributes. */
export type SignUpCredentials = {
  givenName: string;
  email: string;
  gender: string;
  /** Strict YYYY-MM-DD, as Cognito birthdate requires. */
  birthDate: string;
  password: string;
  remember: boolean;
};
type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "error";
type Provider = "cognito" | "native";
type AuthContextValue = {
  user: AuthUser | null; authStatus: AuthStatus; isAuthenticated: boolean; isLoading: boolean; provider: Provider | null;
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  register: (credentials: SignUpCredentials) => Promise<void>;
  confirmRegistration: (email: string, code: string, password: string, remember: boolean) => Promise<void>;
  resendConfirmationCode: (email: string) => Promise<string>;
  requestPasswordReset: (email: string) => Promise<string>;
  submitResetCode: (email: string, code: string, password: string) => Promise<string>;
  resetPassword: (token: string, password: string) => Promise<string>;
  logout: () => Promise<void>; requireAuth: (action: () => void | Promise<void>) => void; openAuth: () => void;
};
const AuthContext = createContext<AuthContextValue | null>(null);
// Auth is proxied through this same-origin route so secure cookies work when
// the API remains private inside Railway's network.
const API = "/api";

export class VerificationRequiredError extends Error {
  constructor(email: string) {
    super("Please verify your email to finish signing in.");
    this.name = "VerificationRequiredError";
    this.email = email;
  }
  email: string;
}
export class ConfirmationRequiredError extends Error {
  constructor(email: string) {
    super("Check your email for a verification code.");
    this.name = "ConfirmationRequiredError";
    this.email = email;
  }
  email: string;
}

async function readError(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null) as { error?: string } | null;
  return payload?.error || fallback;
}
async function csrf() {
  const response = await fetch(`${API}/auth/csrf`, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error(await readError(response, "Secure sign-in is temporarily unavailable. Please try again shortly."));
  const payload = await response.json().catch(() => null) as { csrfToken?: string } | null;
  if (!payload?.csrfToken) throw new Error("Secure sign-in is temporarily unavailable. Please try again shortly.");
  return payload.csrfToken;
}
async function post(path: string, body: unknown, token: string) {
  return fetch(`${API}${path}`, { method: "POST", credentials: "include", cache: "no-store", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify(body) });
}

function useAuthApi() {
  const [provider, setProvider] = useState<Provider | null>(null);

  // Which auth system is live is decided SERVER-side; build-time env vars can
  // drift from runtime configuration and would leave dead buttons.
  const resolveProvider = useCallback(async () => {
    if (provider) return provider;
    const response = await fetch(`${API}/auth/cognito/capability`, { cache: "no-store" });
    if (!response.ok) throw new Error("Secure sign-in is temporarily unavailable. Please try again shortly.");
    const payload = await response.json() as { provider?: Provider };
    if (payload.provider !== "cognito" && payload.provider !== "native") throw new Error("Secure sign-in is temporarily unavailable. Please try again shortly.");
    setProvider(payload.provider);
    return payload.provider;
  }, [provider]);

  /** Cognito mutations always carry the CSRF pair their Go counterparts require. */
  const cognitoPost = useCallback(async (path: string, body: unknown) => post(path, body, await csrf()), []);

  const restoreSession = useCallback(async (activeProvider: Provider) => {
    const token = await csrf();
    if (activeProvider === "cognito") {
      // The header matters: the session route may heal the Go session through
      // /auth/cognito/exchange, which enforces the double-submit check.
      const session = await fetch(`${API}/auth/cognito/session`, { credentials: "include", cache: "no-store", headers: { "X-CSRF-Token": token } });
      if (session.ok) {
        const payload = await session.json() as { user?: AuthUser };
        return payload.user ? ({ user: payload.user, status: "authenticated" } as const) : ({ status: "error" } as const);
      }
      if (session.status !== 401) return { status: "error" } as const;
      const refreshed = await fetch(`${API}/auth/cognito/refresh`, { method: "POST", credentials: "include", cache: "no-store", headers: { "Content-Type": "application/json", "X-CSRF-Token": token } });
      if (!refreshed.ok) return { status: refreshed.status === 401 ? "unauthenticated" : "error" } as const;
      const payload = await refreshed.json() as { user?: AuthUser };
      return payload.user ? ({ user: payload.user, status: "authenticated" } as const) : ({ status: "error" } as const);
    }
    const session = await fetch(`${API}/auth/me`, { credentials: "include", cache: "no-store", headers: { "X-CSRF-Token": token } });
    if (session.ok) {
      const payload = await session.json() as { user?: AuthUser };
      return payload.user ? ({ user: payload.user, status: "authenticated" } as const) : ({ status: "error" } as const);
    }
    if (session.status !== 401) return { status: "error" } as const;
    // Only an explicit unauthenticated response may use the refresh session.
    // A network or server failure must not be mistaken for a logged-out user.
    const refreshed = await fetch(`${API}/auth/refresh`, { method: "POST", credentials: "include", cache: "no-store", headers: { "X-CSRF-Token": token } });
    if (!refreshed.ok) return { status: refreshed.status === 401 ? "unauthenticated" : "error" } as const;
    const payload = await refreshed.json() as { user?: AuthUser };
    return payload.user ? ({ user: payload.user, status: "authenticated" } as const) : ({ status: "error" } as const);
  }, []);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const activeProvider = await resolveProvider();
    let response: Response;
    if (activeProvider === "cognito") {
      response = await cognitoPost("/auth/cognito/login", { email, password, remember });
      if (response.ok) {
        const payload = await response.json() as { user?: AuthUser };
        if (payload.user) return payload.user;
      }
      const payload = await response.json().catch(() => ({})) as { needsConfirmation?: boolean; error?: string };
      if (payload.needsConfirmation) throw new VerificationRequiredError(email.trim().toLowerCase());
      throw new Error(payload.error || "Incorrect email or password.");
    }
    response = await post("/auth/login", { email, password, remember }, await csrf());
    const payload = await response.json().catch(() => ({})) as { user?: AuthUser; error?: string };
    if (!response.ok || !payload.user) {
      if (response.status === 401) throw new Error("Incorrect email or password. Please try again.");
      throw new Error(payload.error || "We could not complete that request. Please try again.");
    }
    return payload.user;
  }, [resolveProvider, cognitoPost]);

  const register = useCallback(async (credentials: SignUpCredentials): Promise<void> => {
    const activeProvider = await resolveProvider();
    if (activeProvider === "cognito") {
      // Cognito sign-up ends at "check your email": no session exists until
      // the emailed code confirms the address (and fires the welcome coupon).
      const response = await cognitoPost("/auth/cognito/signup", {
        givenName: credentials.givenName,
        email: credentials.email,
        gender: credentials.gender,
        birthDate: credentials.birthDate,
        password: credentials.password,
      });
      if (response.ok) throw new ConfirmationRequiredError(credentials.email.trim().toLowerCase());
      const payload = await response.json().catch(() => ({})) as { error?: string };
      throw new Error(payload.error || "We could not create your account. Please try again.");
    }
    // Native accounts keep their single display-name field; the given name
    // fills it until the visitor adds more in their profile.
    const response = await post("/auth/register", { name: credentials.givenName, email: credentials.email, password: credentials.password, remember: credentials.remember }, await csrf());
    const payload = await response.json().catch(() => ({})) as { user?: AuthUser; error?: string };
    if (!response.ok || !payload.user) {
      if (response.status === 401) throw new Error("Incorrect email or password. Please try again.");
      throw new Error(payload.error || "We could not complete that request. Please try again.");
    }
  }, [resolveProvider, cognitoPost]);

  const confirmRegistration = useCallback(async (email: string, code: string, password: string, remember: boolean) => {
    const response = await cognitoPost("/auth/cognito/confirm", { email, code, password, remember });
    const payload = await response.json().catch(() => ({})) as { user?: AuthUser; error?: string };
    if (!response.ok || !payload.user) throw new Error(payload.error || "We could not verify that code. Please try again.");
    return payload.user!;
  }, [cognitoPost]);

  const resendConfirmationCode = useCallback(async (email: string) => {
    const response = await cognitoPost("/auth/cognito/resend", { email });
    const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
    if (!response.ok) throw new Error(payload.error || "We could not send a new code. Please try again shortly.");
    return payload.message || "If that account still needs verifying, a new code is on its way.";
  }, [cognitoPost]);

  const requestPasswordReset = useCallback(async (email: string) => {
    const activeProvider = await resolveProvider();
    if (activeProvider === "cognito") {
      const response = await cognitoPost("/auth/cognito/forgot", { email });
      const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
      if (!response.ok) throw new Error(payload.error || "We could not complete that request. Please try again.");
      return payload.message || "If an account matches that email, a verification code will arrive shortly.";
    }
    const response = await fetch(`${API}/auth/password-reset/request`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
    const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
    if (!response.ok) throw new Error(payload.error || "We could not complete that request. Please try again.");
    return payload.message || "If an account matches that email, a reset link will arrive shortly.";
  }, [resolveProvider, cognitoPost]);

  const submitResetCode = useCallback(async (email: string, code: string, password: string) => {
    const response = await cognitoPost("/auth/cognito/reset-confirm", { email, code, password });
    const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
    if (!response.ok) throw new Error(payload.error || "We could not update your password. Please try again.");
    return payload.message || "Your password has been updated. You can now sign in.";
  }, [cognitoPost]);

  const resetPassword = useCallback(async (token: string, password: string) => {
    const response = await fetch(`${API}/auth/password-reset/confirm`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }) });
    const payload = await response.json().catch(() => ({})) as { message?: string; error?: string };
    if (!response.ok) throw new Error(payload.error || "We could not complete that request. Please try again.");
    return payload.message || "Your password has been updated. You can now sign in.";
  }, []);

  const logout = useCallback(async () => {
    const token = await csrf().catch(() => "");
    if (provider === "cognito") {
      await fetch(`${API}/auth/cognito/logout`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } }).catch(() => undefined);
    } else if (provider === "native") {
      await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } }).catch(() => undefined);
    } else {
      // Capability never resolved (offline?) — clear whichever family exists.
      await Promise.all([
        fetch(`${API}/auth/logout`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } }).catch(() => undefined),
        fetch(`${API}/auth/cognito/logout`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } }).catch(() => undefined),
      ]);
    }
  }, [provider]);

  return { provider, resolveProvider, restoreSession, login, register, confirmRegistration, resendConfirmationCode, requestPasswordReset, submitResetCode, resetPassword, logout };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const api = useAuthApi();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");
  const [modalOpen, setModalOpen] = useState(false);
  const deferredAction = useRef<(() => void | Promise<void>) | null>(null);
  const isLoading = authStatus === "loading";

  useEffect(() => {
    let active = true;
    const restoreSession = async () => {
      try {
        const outcome = await api.restoreSession(await api.resolveProvider());
        if (!active) return;
        setUser("user" in outcome ? outcome.user ?? null : null);
        setAuthStatus(outcome.status);
      } catch {
        if (active) setAuthStatus("error");
      }
    };
    void restoreSession();
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);
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

  const complete = useCallback((nextUser: AuthUser) => { setUser(nextUser); setAuthStatus("authenticated"); setModalOpen(false); const action = deferredAction.current; deferredAction.current = null; void action?.(); }, []);
  const login = useCallback(async (email: string, password: string, remember: boolean) => complete(await api.login(email, password, remember)), [api, complete]);
  const register = useCallback(async (credentials: SignUpCredentials) => api.register(credentials), [api, complete]);
  const confirmRegistration = useCallback(async (email: string, code: string, password: string, remember: boolean) => complete(await api.confirmRegistration(email, code, password, remember)), [api, complete]);
  const requireAuth = useCallback((action: () => void | Promise<void>) => {
    if (user) { void action(); return; }
    deferredAction.current = action;
    if (!isLoading) setModalOpen(true);
  }, [isLoading, user]);

  const value = useMemo(() => ({
    user, authStatus, isAuthenticated: !!user, isLoading, provider: api.provider,
    login, register,
    confirmRegistration,
    resendConfirmationCode: api.resendConfirmationCode,
    requestPasswordReset: api.requestPasswordReset,
    submitResetCode: api.submitResetCode,
    resetPassword: api.resetPassword,
    logout: api.logout, requireAuth, openAuth: () => setModalOpen(true),
  }), [user, authStatus, isLoading, api, login, register, confirmRegistration, requireAuth]);

  const currentPath = typeof window === "undefined" ? "/" : `${window.location.pathname}${window.location.search}`;
  const returnPath = deferredAction.current ? "/checkout" : currentPath;
  return <AuthContext.Provider value={value}>{children}<AuthModal open={modalOpen} onClose={() => { deferredAction.current = null; setModalOpen(false); }} returnTo={returnPath} /></AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }
export function useRequireAuth(action: () => void | Promise<void>) { const { requireAuth } = useAuth(); return useCallback(() => requireAuth(action), [requireAuth, action]); }
