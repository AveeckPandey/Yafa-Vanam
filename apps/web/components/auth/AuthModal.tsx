"use client";

import { useEffect, useId, useRef, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onLogin: (email: string, password: string, remember: boolean) => Promise<void>;
  onRegister: (name: string, email: string, password: string, remember: boolean) => Promise<void>;
  googleUrl: string;
};
type Mode = "signin" | "signup";

function passwordStrength(password: string) {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return score <= 1 ? "weak" : score <= 3 ? "moderate" : "strong";
}

function LeafMark() {
  return <svg className="auth-modal__leaf" aria-hidden="true" viewBox="0 0 108 96" fill="none"><path d="M16 81C41 72 65 47 85 12c2 30-8 58-31 72-12 7-25 6-38-3Z" stroke="currentColor" strokeWidth="1.25" /><path d="M23 77C40 62 58 44 79 22M48 59c-7-4-12-8-15-13M58 48c7 0 13-2 18-7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" /></svg>;
}

export default function AuthModal({ open, onClose, onLogin, onRegister, googleUrl }: Props) {
  const [mode, setMode] = useState<Mode>("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");
  const dialog = useRef<HTMLElement>(null);
  const id = useId();
  const errorID = `${id}-error`;
  const tabID = (tab: Mode) => `${id}-${tab}-tab`;
  const panelID = `${id}-panel`;

  useEffect(() => {
    if (!open) return;
    const key = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  }, [open, onClose]);

  if (!open) return null;

  const switchMode = (next: Mode) => { setMode(next); setError(""); setPassword(""); };
  const submit = async (form: HTMLFormElement) => {
    const data = new FormData(form);
    const nextPassword = String(data.get("password") || "");
    if (mode === "signup" && nextPassword !== String(data.get("confirmPassword") || "")) {
      setError("Passwords do not match. Please check and try again.");
      return;
    }
    setBusy(true); setError("");
    try {
      if (mode === "signin") await onLogin(String(data.get("email") || ""), nextPassword, data.get("remember") === "on");
      else await onRegister(String(data.get("name") || ""), String(data.get("email") || ""), nextPassword, data.get("remember") === "on");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not sign you in. Please try again.");
    } finally { setBusy(false); }
  };

  const strength = passwordStrength(password);
  return <div className="auth-modal__backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="auth-modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} tabIndex={-1}>
      <LeafMark />
      <button className="auth-modal__close" type="button" onClick={onClose} aria-label="Close account dialog">×</button>
      <p className="auth-modal__eyebrow">YOUR YAFA VANAM RITUAL</p>
      <h2 id={`${id}-title`}>{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
      <p className="auth-modal__intro">{mode === "signin" ? "Your saved ritual is waiting." : "A more personal beauty edit begins here."}</p>
      <div className="auth-modal__tabs" role="tablist" aria-label="Account access">
        <button id={tabID("signin")} className={mode === "signin" ? "is-active" : ""} type="button" role="tab" aria-selected={mode === "signin"} aria-controls={panelID} onClick={() => switchMode("signin")}>Sign in</button>
        <button id={tabID("signup")} className={mode === "signup" ? "is-active" : ""} type="button" role="tab" aria-selected={mode === "signup"} aria-controls={panelID} onClick={() => switchMode("signup")}>Sign up</button>
      </div>
      <div id={panelID} className="auth-modal__panel" role="tabpanel" aria-labelledby={tabID(mode)}>
        <form onSubmit={(event) => { event.preventDefault(); void submit(event.currentTarget); }} noValidate>
          {mode === "signup" && <label htmlFor={`${id}-name`}>Full name<input id={`${id}-name`} name="name" autoComplete="name" required /></label>}
          <label htmlFor={`${id}-email`}>Email address<input id={`${id}-email`} name="email" type="email" autoComplete="email" required aria-describedby={error ? errorID : undefined} /></label>
          <label htmlFor={`${id}-password`}>Password<input id={`${id}-password`} name="password" type="password" minLength={8} autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} required aria-describedby={mode === "signup" || error ? `${mode === "signup" ? `${id}-strength ` : ""}${error ? errorID : ""}`.trim() : undefined} /></label>
          {mode === "signup" && <div id={`${id}-strength`} className={`auth-modal__strength is-${strength}`} aria-live="polite"><span><i /><i /><i /></span><b>Password strength: {strength}</b></div>}
          {mode === "signup" && <label htmlFor={`${id}-confirm`}>Confirm password<input id={`${id}-confirm`} name="confirmPassword" type="password" minLength={8} autoComplete="new-password" required aria-describedby={error ? errorID : undefined} /></label>}
          <div className="auth-modal__options">
            <label className="auth-modal__remember"><input name="remember" type="checkbox" /> Remember me</label>
            {mode === "signin" && <button type="button" className="auth-modal__link" onClick={() => setError("Password reset will be available shortly. Please contact support if you need help.")}>Forgot password?</button>}
          </div>
          {error && <p id={errorID} className="auth-modal__error" role="alert">{error}</p>}
          <button className="auth-modal__submit" disabled={busy} type="submit">{busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}</button>
        </form>
        <div className="auth-modal__divider"><span>OR CONTINUE WITH</span></div>
        <a className="auth-modal__google" href={googleUrl}><span aria-hidden="true">G</span> Continue with Google</a>
        {mode === "signup" && <p className="auth-modal__switch">Already have an account? <button type="button" onClick={() => switchMode("signin")}>Sign in</button></p>}
        <p className="auth-modal__fineprint">Secure checkout begins after you sign in. You can continue browsing freely.</p>
      </div>
    </section>
  </div>;
}
