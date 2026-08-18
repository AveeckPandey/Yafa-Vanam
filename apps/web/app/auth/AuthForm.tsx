"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const [submitted, setSubmitted] = useState(false);
  const create = mode === "sign-up";
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setSubmitted(true); };
  return <main id="main-content" className="auth-page"><section><p>YAFA VANAM / Account</p><h1>{create ? "Create your account." : "Welcome back."}</h1><span>{create ? "Save your ritual and make future checkout simpler." : "Sign in to see your orders, saved products and beauty profile."}</span><form onSubmit={submit}>{create ? <label htmlFor="auth-name">Name<input id="auth-name" autoComplete="name" required /></label> : null}<label htmlFor="auth-email">Email<input id="auth-email" type="email" autoComplete="email" required /></label><label htmlFor="auth-password">Password<input id="auth-password" type="password" autoComplete={create ? "new-password" : "current-password"} minLength={8} required /></label><button type="submit">{create ? "Create account" : "Sign in"}</button>{submitted ? <p role="status">Account authentication will be connected to the commerce service before launch. Your details have not been submitted.</p> : null}</form><p>{create ? "Already have an account?" : "New to YAFA VANAM?"} <Link href={create ? "/auth/sign-in" : "/auth/sign-up"}>{create ? "Sign in" : "Create one"}</Link></p></section></main>;
}
