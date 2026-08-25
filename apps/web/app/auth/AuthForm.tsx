"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ConfirmationRequiredError, VerificationRequiredError, useAuth } from "../../components/auth/AuthProvider";

function PasswordInput({ id, name = "password", label = "Password", autoComplete, value, onChange }: { id: string; name?: string; label?: string; autoComplete: string; value?: string; onChange?: (value: string) => void }) {
  const [visible, setVisible] = useState(false);
  return <label htmlFor={id}>{label}<span className="auth-page__password-wrap"><input id={id} name={name} type={visible ? "text" : "password"} autoComplete={autoComplete} minLength={8} required value={value} onChange={onChange ? (event) => onChange(event.target.value) : undefined}/><button type="button" onClick={() => setVisible((current) => !current)} aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M2.5 12s3.3-5.5 9.5-5.5S21.5 12 21.5 12 18.2 17.5 12 17.5 2.5 12 2.5 12Z" stroke="currentColor" strokeWidth="1.6"/><circle cx="12" cy="12" r="2.7" stroke="currentColor" strokeWidth="1.6"/>{!visible && <path d="m4 4 16 16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>}</svg></button></span></label>;
}

/** Same rule as the server's safeReturnTo — only same-origin absolute paths. */
const safeReturnTo = (value: string | null | undefined, fallback = "/account") => value && value.startsWith("/") && !value.startsWith("//") ? value : fallback;

export default function AuthForm({ mode }: { mode: "sign-in" | "sign-up" | "reset-password" }) {
  const router = useRouter();
  const { provider, login, register, confirmRegistration, resendConfirmationCode, requestPasswordReset, submitResetCode, resetPassword } = useAuth();
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [confirming, setConfirming] = useState(false), [pendingEmail, setPendingEmail] = useState(""), [pendingPassword, setPendingPassword] = useState("");
  const [resetReady, setResetReady] = useState(false), [resendIn, setResendIn] = useState(0);
  const create = mode === "sign-up", reset = mode === "reset-password";
  const params = typeof window === "undefined" ? null : new URLSearchParams(window.location.search);
  const token = params?.get("token") || "";
  const returnTo = safeReturnTo(params?.get("return_to"));
  const cognito = provider === "cognito";
  // Cognito emails one-time codes rather than signed reset links, so its reset
  // page runs email → code → new password entirely on this screen. Native
  // keeps the emailed-link (?token=) flow unchanged.
  const resetRequestsCode = reset && !!cognito;
  const resetAwaitingCode = resetRequestsCode && !resetReady;

  useEffect(() => { if (resendIn <= 0) return; const timer = setInterval(() => setResendIn((value) => Math.max(0, value - 1)), 1000); return () => clearInterval(timer); }, [resendIn]);

  const armConfirm = (email: string, rememberedPassword: string) => { setPendingEmail(email); setPendingPassword(rememberedPassword); setConfirming(true); setError(""); setNotice(""); setResendIn(60); };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || "").trim().toLowerCase(), entered = String(data.get("password") || "");
    if ((create || (reset && !resetAwaitingCode)) && entered !== String(data.get("confirmPassword") || "")) { setError("Passwords do not match. Please check and try again."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      if (resetAwaitingCode) {
        setNotice(await requestPasswordReset(email));
        setPendingEmail(email); setResetReady(true); setResendIn(60);
      } else if (reset) {
        setNotice(cognito ? await submitResetCode(email, String(data.get("code") || "").trim(), entered) : await (() => { if (!token) throw new Error("This reset link is invalid or has expired. Please request a new one."); return resetPassword(token, entered); })());
      } else if (create) {
        try { await register(String(data.get("name") || ""), email, entered, false); router.push(returnTo); }
        catch (reason) { if (reason instanceof ConfirmationRequiredError) armConfirm(reason.email, entered); else throw reason; }
      } else {
        try { await login(email, entered, false); router.push(returnTo); }
        catch (reason) { if (reason instanceof VerificationRequiredError) armConfirm(reason.email, entered); else throw reason; }
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to continue. Please try again."); } finally { setBusy(false); }
  };

  const submitConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code") || "").trim();
    setBusy(true); setError("");
    try { await confirmRegistration(pendingEmail, code, pendingPassword, false); router.push(returnTo); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "We could not verify that code. Please try again."); } finally { setBusy(false); }
  };

  const resend = async () => {
    if (resendIn > 0 || busy) return;
    setBusy(true); setError(""); setNotice("");
    try { setNotice(await resendConfirmationCode(confirming ? pendingEmail : pendingEmail)); setResendIn(60); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "We could not send a new code."); } finally { setBusy(false); }
  };

  const title = confirming ? "Verify your email." : reset ? (resetAwaitingCode ? "Reset your password." : "Choose a new password.") : create ? "Create your account." : "Welcome back.";
  const intro = confirming
    ? `We emailed a 6-digit code to ${pendingEmail}. Enter it below to finish signing in.`
    : reset
      ? resetAwaitingCode ? "Enter your email and we’ll send you a one-time reset code." : "Enter the code we emailed you along with a new password."
      : create ? "Save your ritual and make future checkout simpler." : "Sign in to see your orders, saved products and beauty profile.";
  const resendButton = confirming || (resetRequestsCode && resetReady) ? <button className="auth-page__forgot" type="button" disabled={busy || resendIn > 0} onClick={() => void resend()}>{resendIn > 0 ? `Resend available in ${resendIn}s` : "Resend code"}</button> : null;
  const signInLink = `/auth/sign-in${returnTo === "/account" ? "" : `?return_to=${encodeURIComponent(returnTo)}`}`;

  return <main id="main-content" className="auth-page"><section><p>YAFA VANAM / Account</p><h1>{title}</h1><span>{intro}</span>
    {confirming ? (
      <form onSubmit={submitConfirm}>
        <label htmlFor="auth-confirm-code">Verification code<input id="auth-confirm-code" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]*" placeholder="••••••" required/></label>
        {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
        <button type="submit" disabled={busy}>{busy ? "Verifying…" : "Verify & sign in"}</button>
        {resendButton}
      </form>
    ) : (
      <form onSubmit={submit}>
        {create && <label htmlFor="auth-name">Name<input id="auth-name" name="name" autoComplete="name" required/></label>}
        {(!reset || cognito) && <label htmlFor="auth-email">Email<input id="auth-email" name="email" type="email" autoComplete="email" defaultValue={pendingEmail || undefined} required/></label>}
        {!resetAwaitingCode && <PasswordInput id="auth-password" autoComplete={create || reset ? "new-password" : "current-password"}/>}
        {resetRequestsCode && resetReady && <label htmlFor="auth-reset-code">Reset code<input id="auth-reset-code" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]*" placeholder="••••••" required/></label>}
        {(create || (reset && !resetAwaitingCode)) && <PasswordInput id="auth-confirm-password" name="confirmPassword" label="Confirm password" autoComplete="new-password"/>}
        {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
        <button type="submit" disabled={busy}>{busy ? "Please wait…" : resetAwaitingCode ? "Send reset code" : reset ? "Update password" : create ? "Create account" : "Sign in"}</button>
        {resendButton}
      </form>
    )}
    {reset ? <p>Remembered it? <Link href={signInLink}>Sign in</Link></p> : <><p>{create ? "Already have an account?" : "New to YAFA VANAM?"} <Link href={(create ? "/auth/sign-in" : "/auth/sign-up") + (returnTo === "/account" ? "" : `?return_to=${encodeURIComponent(returnTo)}`)}>{create ? "Sign in" : "Create one"}</Link></p>
      {!create && (cognito
        ? <Link className="auth-page__forgot" href={`/auth/reset-password${returnTo === "/account" ? "" : `?return_to=${encodeURIComponent(returnTo)}`}`}>Forgot password?</Link>
        : <button className="auth-page__forgot" type="button" disabled={busy} onClick={async () => { const email = window.prompt("Enter your email address to receive a reset link:"); if (!email) return; setBusy(true); setError(""); try { setNotice(await requestPasswordReset(email)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to request a reset link."); } finally { setBusy(false); } }}>Forgot password?</button>)}
    </>}</section></main>;
}
