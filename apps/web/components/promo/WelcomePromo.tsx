"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";

const DISMISSAL_KEY = "yafa_welcome_promo_dismissed";
/** Commerce funnels never get interrupted mid-flow. */
const EXCLUDED_PREFIXES = ["/checkout", "/cart", "/order"];
const OPEN_DELAY_MS = 6000;

function readDismissed() {
  try { return window.sessionStorage.getItem(DISMISSAL_KEY) === "1"; } catch { return false; }
}

export default function WelcomePromo() {
  const { authStatus } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLElement>(null);
  const titleID = `${useId()}-title`;

  const dismiss = useCallback(() => {
    setOpen(false);
    try { window.sessionStorage.setItem(DISMISSAL_KEY, "1"); } catch { /* private mode etc. — closing is enough */ }
  }, []);

  useEffect(() => {
    // Only first-time-ish visitors: signed-out, past the loading probe, on a
    // browsable page, and not already waved away this session.
    const { pathname } = window.location;
    const excluded = EXCLUDED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
    if (authStatus !== "unauthenticated" || excluded || readDismissed()) return;
    const timer = setTimeout(() => setOpen(true), OPEN_DELAY_MS);
    return () => clearTimeout(timer);
  }, [authStatus]);

  useEffect(() => {
    if (!open) return;
    const key = (event: KeyboardEvent) => event.key === "Escape" && dismiss();
    document.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  }, [open, dismiss]);

  if (!open) return null;

  const accept = () => {
    const returnTo = `${window.location.pathname}${window.location.search}`;
    dismiss();
    router.push(`/auth/sign-in?return_to=${encodeURIComponent(returnTo)}`);
  };

  return <div className="welcome-promo__backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) dismiss(); }}>
    <section className="welcome-promo" ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleID} tabIndex={-1}>
      <button className="welcome-promo__close" type="button" onClick={dismiss} aria-label="Close offer">×</button>
      <p className="welcome-promo__eyebrow">A WELCOME FROM YAFA VANAM</p>
      <h2 id={titleID}>GET 10% OFF</h2>
      <p className="welcome-promo__copy">Sign in or create an account to receive 10% off your order — your bag stays right here.</p>
      <button className="welcome-promo__cta" type="button" onClick={accept}>SIGN IN / SIGN UP</button>
      <button className="welcome-promo__decline" type="button" onClick={dismiss}>NO THANKS</button>
      <p className="welcome-promo__fineprint">New customers only. One code per account.</p>
    </section>
  </div>;
}
