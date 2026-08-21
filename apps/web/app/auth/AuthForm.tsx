"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "../../components/auth/AuthProvider";

export default function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const { login, register } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const create = mode === "sign-up";
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || "");
    const password = String(data.get("password") || "");
    const name = String(data.get("name") || "");
    setBusy(true); setError("");
    try {
      if (create) await register(name, email, password, false);
      else await login(email, password, false);
      router.push("/account");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to continue. Please try again.");
    } finally { setBusy(false); }
  };
  return <main id="main-content" className="auth-page"><section><p>YAFA VANAM / Account</p><h1>{create ? "Create your account." : "Welcome back."}</h1><span>{create ? "Save your ritual and make future checkout simpler." : "Sign in to see your orders, saved products and beauty profile."}</span><form onSubmit={submit}>{create ? <label htmlFor="auth-name">Name<input id="auth-name" name="name" autoComplete="name" required /></label> : null}<label htmlFor="auth-email">Email<input id="auth-email" name="email" type="email" autoComplete="email" required /></label><label htmlFor="auth-password">Password<input id="auth-password" name="password" type="password" autoComplete={create ? "new-password" : "current-password"} minLength={8} required /></label>{error ? <p role="alert">{error}</p> : null}<button type="submit" disabled={busy}>{busy ? "Please wait…" : create ? "Create account" : "Sign in"}</button></form><p>{create ? "Already have an account?" : "New to YAFA VANAM?"} <Link href={create ? "/auth/sign-in" : "/auth/sign-up"}>{create ? "Sign in" : "Create one"}</Link></p></section></main>;
}
