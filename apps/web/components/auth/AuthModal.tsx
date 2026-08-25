"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ConfirmationRequiredError, VerificationRequiredError, useAuth } from "./AuthProvider";

type Props = { open: boolean; onClose: () => void; returnTo: string };
type Mode = "signin" | "signup" | "forgot";
type Step = "form" | "confirm" | "forgot-code";

function passwordStrength(password: string) { let score = 0; if (password.length >= 8) score++; if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++; if (/\d/.test(password)) score++; if (/[^A-Za-z0-9]/.test(password)) score++; return score <= 1 ? "weak" : score <= 3 ? "moderate" : "strong"; }
function Eye({ visible }: { visible: boolean }) { return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M2.5 12s3.3-5.5 9.5-5.5S21.5 12 21.5 12 18.2 17.5 12 17.5 2.5 12 2.5 12Z" stroke="currentColor" strokeWidth="1.6"/><circle cx="12" cy="12" r="2.7" stroke="currentColor" strokeWidth="1.6"/>{!visible && <path d="m4 4 16 16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>}</svg>; }
function PasswordField({ id, name, label, value, onChange, autoComplete, describedBy }: { id: string; name: string; label: string; value?: string; onChange?: (value: string) => void; autoComplete: string; describedBy?: string }) { const [visible, setVisible] = useState(false); return <label htmlFor={id}>{label}<span className="auth-modal__password-wrap"><input id={id} name={name} type={visible ? "text" : "password"} minLength={8} autoComplete={autoComplete} value={value} onChange={onChange ? (event) => onChange(event.target.value) : undefined} required aria-describedby={describedBy}/><button className="auth-modal__password-toggle" type="button" onClick={() => setVisible((current) => !current)} aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible}><Eye visible={visible}/></button></span></label>; }
function LeafMark() { return <svg className="auth-modal__leaf" aria-hidden="true" viewBox="0 0 108 96" fill="none"><path d="M16 81C41 72 65 47 85 12c2 30-8 58-31 72-12 7-25 6-38-3Z" stroke="currentColor" strokeWidth="1.25"/><path d="M23 77C40 62 58 44 79 22M48 59c-7-4-12-8-15-13M58 48c7 0 13-2 18-7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/></svg>; }

export default function AuthModal({ open, onClose, returnTo }: Props) {
  const { provider, login, register, confirmRegistration, resendConfirmationCode, requestPasswordReset, submitResetCode } = useAuth();
  const [mode, setMode] = useState<Mode>("signin"), [step, setStep] = useState<Step>("form");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState(""), [password, setPassword] = useState("");
  const [pendingEmail, setPendingEmail] = useState(""), [pendingPassword, setPendingPassword] = useState(""), [resetCodeSent, setResetCodeSent] = useState(false);
  const [resendIn, setResendIn] = useState(0);
  const dialog = useRef<HTMLElement>(null); const id = useId(); const errorID = `${id}-error`; const tabID = (tab: "signin" | "signup") => `${id}-${tab}-tab`; const panelID = `${id}-panel`;
  const cognito = provider === "cognito";

  useEffect(() => { if (!open || resendIn <= 0) return; const timer = setInterval(() => setResendIn((value) => Math.max(0, value - 1)), 1000); return () => clearInterval(timer); }, [open, resendIn]);
  useEffect(() => { if (!open) return; const key = (event: KeyboardEvent) => event.key === "Escape" && onClose(); document.addEventListener("keydown", key); document.body.style.overflow = "hidden"; dialog.current?.focus(); return () => { document.removeEventListener("keydown", key); document.body.style.overflow = ""; }; }, [open, onClose]);
  if (!open) return null;

  const switchMode = (next: Mode) => { setMode(next); setStep("form"); setError(""); setNotice(""); setPassword(""); setPendingEmail(""); setPendingPassword(""); setResetCodeSent(false); };
  const enterConfirm = (email: string, rememberedPassword: string) => { setPendingEmail(email); setPendingPassword(rememberedPassword); setStep("confirm"); setError(""); setNotice(""); setResendIn(60); };

  const submitForm = async (form: HTMLFormElement) => {
    const data = new FormData(form);
    const email = String(data.get("email") || "").trim().toLowerCase();
    const nextPassword = String(data.get("password") || "");
    if (mode === "signup" && nextPassword !== String(data.get("confirmPassword") || "")) { setError("Passwords do not match. Please check and try again."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      if (mode === "signin") {
        await login(email, nextPassword, data.get("remember") === "on");
      } else if (mode === "signup") {
        await register(String(data.get("name") || ""), email, nextPassword, data.get("remember") === "on");
      } else {
        setNotice(await requestPasswordReset(email));
        setPendingEmail(email);
        setResetCodeSent(true);
      }
    } catch (reason) {
      if (reason instanceof VerificationRequiredError || reason instanceof ConfirmationRequiredError) {
        // Cognito mode routes every unverified sign-in into the code panel.
        enterConfirm(reason.email, nextPassword);
      } else {
        setError(reason instanceof Error ? reason.message : "We could not complete that request. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  const submitConfirm = async (form: HTMLFormElement) => {
    const code = String(new FormData(form).get("code") || "").trim();
    setBusy(true); setError("");
    try {
      await confirmRegistration(pendingEmail, code, pendingPassword, true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not verify that code. Please try again.");
    } finally { setBusy(false); }
  };

  const submitForgotCode = async (form: HTMLFormElement) => {
    const data = new FormData(form);
    const email = String(data.get("email") || "").trim().toLowerCase();
    const code = String(data.get("code") || "").trim();
    const nextPassword = String(data.get("password") || "");
    if (nextPassword !== String(data.get("confirmPassword") || "")) { setError("Passwords do not match. Please check and try again."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      setNotice(await submitResetCode(email, code, nextPassword));
      setStep("form"); setMode("signin"); setPendingEmail(""); setResetCodeSent(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not update your password. Please try again.");
    } finally { setBusy(false); }
  };

  const resend = async () => {
    if (resendIn > 0) return;
    setBusy(true); setError(""); setNotice("");
    try { setNotice(await resendConfirmationCode(step === "confirm" ? pendingEmail : pendingEmail)); setResendIn(60); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "We could not send a new code."); }
    finally { setBusy(false); }
  };

  const strength = passwordStrength(password);
  const title = step === "confirm" ? "Verify your email" : step === "forgot-code" ? "Enter your reset code" : mode === "signin" ? "Welcome back" : mode === "signup" ? "Create your account" : "Reset your password";
  const intro = step === "confirm"
    ? `We emailed a 6-digit code to ${pendingEmail}. Enter it below to finish setting up your account.`
    : step === "forgot-code"
      ? "Enter the 6-digit code we emailed you along with a new password."
      : cognito
        ? mode === "signin" ? "Sign in to continue securely to checkout. Your bag is already saved." : mode === "signup" ? "A more personal beauty edit begins here." : "Enter your email and we’ll send a one-time code to reset your password."
        : mode === "signin" ? "Sign in to continue securely to checkout. Your bag is already saved." : mode === "signup" ? "A more personal beauty edit begins here." : "Enter your email and we’ll send a secure, one-time reset link if an account matches it.";

  const googleLink = provider !== "cognito" && mode !== "forgot" && step === "form" ? <><div className="auth-modal__divider"><span>OR CONTINUE WITH</span></div><a className="auth-modal__google" href={`/api/auth/google?return_to=${encodeURIComponent(returnTo)}`}><span aria-hidden="true">G</span> Continue with Google</a>{mode === "signup" && <p className="auth-modal__switch">Already have an account? <button type="button" onClick={() => switchMode("signin")}>Sign in</button></p>}</> : null;

  return <div className="auth-modal__backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="auth-modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} tabIndex={-1}><LeafMark/><button className="auth-modal__close" type="button" onClick={onClose} aria-label="Close account dialog">×</button><p className="auth-modal__eyebrow">YOUR YAFA VANAM RITUAL</p><h2 id={`${id}-title`}>{title}</h2><p className="auth-modal__intro">{intro}</p>
    {step === "form" && mode !== "forgot" && <div className="auth-modal__tabs" role="tablist" aria-label="Account access"><button id={tabID("signin")} className={mode === "signin" ? "is-active" : ""} type="button" role="tab" aria-selected={mode === "signin"} aria-controls={panelID} onClick={() => switchMode("signin")}>Sign in</button><button id={tabID("signup")} className={mode === "signup" ? "is-active" : ""} type="button" role="tab" aria-selected={mode === "signup"} aria-controls={panelID} onClick={() => switchMode("signup")}>Sign up</button></div>}
    <div id={panelID} className="auth-modal__panel" role="tabpanel" aria-labelledby={mode === "forgot" || step !== "form" ? undefined : tabID(mode)}>
      {step === "confirm" ? (
        <form onSubmit={(event) => { event.preventDefault(); void submitConfirm(event.currentTarget); }} noValidate>
          <label htmlFor={`${id}-code`}>Verification code<input id={`${id}-code`} name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]*" placeholder="••••••" className="auth-modal__code" required aria-describedby={error ? errorID : undefined}/></label>
          {error && <p id={errorID} className="auth-modal__error" role="alert">{error}</p>}
          {notice && <p className="auth-modal__notice" role="status">{notice}</p>}
          <button className="auth-modal__submit" disabled={busy} type="submit">{busy ? "Verifying…" : "Verify & sign in"}</button>
          <button type="button" className="auth-modal__link" onClick={() => void resend()} disabled={busy}>{resendIn > 0 ? `Resend available in ${resendIn}s` : "Resend code"}</button>
          <button type="button" className="auth-modal__link auth-modal__back-link" onClick={() => switchMode(cognito ? "signin" : "signin")}>← Back to sign in</button>
        </form>
      ) : step === "forgot-code" ? (
        <form onSubmit={(event) => { event.preventDefault(); void submitForgotCode(event.currentTarget); }} noValidate>
          <label htmlFor={`${id}-reset-email`}>Email address<input id={`${id}-reset-email`} name="email" type="email" autoComplete="email" defaultValue={pendingEmail} required/></label>
          <label htmlFor={`${id}-reset-code`}>Reset code<input id={`${id}-reset-code`} name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]*" required aria-describedby={error ? errorID : undefined}/></label>
          <PasswordField id={`${id}-reset-password`} name="password" label="New password" value={password} onChange={setPassword} autoComplete="new-password" describedBy={`${id}-strength ${error ? errorID : ""}`.trim()}/>
          <div id={`${id}-strength`} className={`auth-modal__strength is-${strength}`} aria-live="polite"><span><i/><i/><i/></span><b>Password strength: {strength}</b></div>
          <PasswordField id={`${id}-reset-confirm`} name="confirmPassword" label="Confirm password" autoComplete="new-password" describedBy={error ? errorID : undefined}/>
          {error && <p id={errorID} className="auth-modal__error" role="alert">{error}</p>}
          <button className="auth-modal__submit" disabled={busy} type="submit">{busy ? "Updating…" : "Update password"}</button>
          <button type="button" className="auth-modal__link auth-modal__back-link" onClick={() => switchMode("signin")}>← Back to sign in</button>
        </form>
      ) : (
        <>
          <form onSubmit={(event) => { event.preventDefault(); void submitForm(event.currentTarget); }} noValidate>
            {mode === "signup" && <label htmlFor={`${id}-name`}>Full name<input id={`${id}-name`} name="name" autoComplete="name" required/></label>}
            <label htmlFor={`${id}-email`}>Email address<input id={`${id}-email`} name="email" type="email" autoComplete="email" required aria-describedby={error ? errorID : undefined}/></label>
            {mode !== "forgot" && <PasswordField id={`${id}-password`} name="password" label="Password" value={password} onChange={setPassword} autoComplete={mode === "signin" ? "current-password" : "new-password"} describedBy={mode === "signup" || error ? `${mode === "signup" ? `${id}-strength ` : ""}${error ? errorID : ""}`.trim() : undefined}/>}
            {mode === "signup" && <div id={`${id}-strength`} className={`auth-modal__strength is-${strength}`} aria-live="polite"><span><i/><i/><i/></span><b>Password strength: {strength}</b></div>}
            {mode === "signup" && <PasswordField id={`${id}-confirm`} name="confirmPassword" label="Confirm password" autoComplete="new-password" describedBy={error ? errorID : undefined}/>}
            {mode === "signin" && <div className="auth-modal__options"><label className="auth-modal__remember"><input name="remember" type="checkbox"/> Remember me</label><button type="button" className="auth-modal__link" onClick={() => switchMode("forgot")}>Forgot password?</button></div>}
            {mode === "forgot" && resetCodeSent && <button type="button" className="auth-modal__link" onClick={() => { setStep("forgot-code"); setError(""); setNotice(""); }}>I have a code from my email</button>}
            {mode === "forgot" && <button type="button" className="auth-modal__link auth-modal__back-link" onClick={() => switchMode("signin")}>← Back to sign in</button>}
            {error && <p id={errorID} className="auth-modal__error" role="alert">{error}</p>}
            {notice && <p className="auth-modal__notice" role="status">{notice}</p>}
            <button className="auth-modal__submit" disabled={busy} type="submit">{busy ? "Please wait…" : mode === "signin" ? "Sign in" : mode === "signup" ? "Create account" : "Send reset code"}</button>
          </form>
          {googleLink}
        </>
      )}
      <p className="auth-modal__fineprint">Secure checkout begins after you sign in. You can continue browsing freely.</p>
    </div>
  </section></div>;
}
