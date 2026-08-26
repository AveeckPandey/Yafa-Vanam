"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { CartResponse } from "@/lib/cart-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getCart, removeCartItem, updateCartItem } from "@/components/cart/cart-client";
import { csrfToken } from "@/lib/csrf-client";
import { useAuth } from "@/components/auth/AuthProvider";

type ShippingMethod = "standard" | "express";
type CheckoutState = "idle" | "processing" | "complete";
type CheckoutForm = { email: string; firstName: string; lastName: string; address: string; apartment: string; city: string; state: string; pin: string; phone: string; giftMessage: string };
type RazorpayResponse = { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };
type RazorpayInstance = { open: () => void };
type RazorpayConstructor = new (options: {
  key: string; amount: number; currency: string; name: string; order_id: string;
  prefill?: { name?: string; email?: string; contact?: string }; theme?: { color?: string };
  handler: (response: RazorpayResponse) => void | Promise<void>; modal: { ondismiss: () => void };
}) => RazorpayInstance;

declare global { interface Window { Razorpay?: RazorpayConstructor } }

const emptyCart: CartResponse = { items: [], itemCount: 0, subtotal: 0, currency: "INR" };
const initialForm: CheckoutForm = { email: "", firstName: "", lastName: "", address: "", apartment: "", city: "", state: "", pin: "", phone: "", giftMessage: "" };
const FREE_SHIPPING_THRESHOLD = 1999;
// Promotions are account-bound and applied by the server: eligible signed-in
// customers automatically receive their first-order discount at payment time.
// There are no public coupon codes to enter, share, or leak.

function calculateTotals(subtotal: number, shippingMethod: ShippingMethod) {
  const shipping = subtotal <= 0 ? 0 : shippingMethod === "express" ? 299 : (subtotal >= FREE_SHIPPING_THRESHOLD ? 0 : 199);
  return { shipping, total: subtotal + shipping };
}

function fieldError(form: CheckoutForm, field: keyof CheckoutForm) {
  const value = form[field].trim();
  if (["email", "firstName", "lastName", "address", "city", "state", "pin", "phone"].includes(field) && !value) return "This field is required.";
  if (field === "email" && !/^\S+@\S+\.\S+$/.test(value)) return "Enter a valid email address.";
  if (field === "pin" && !/^[1-9][0-9]{5}$/.test(value)) return "Enter a valid 6-digit PIN code.";
  if (field === "phone" && !/^[6-9][0-9]{9}$/.test(value.replace(/\s/g, ""))) return "Enter a valid 10-digit mobile number.";
  return "";
}

function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    if (existing) { existing.addEventListener("load", () => resolve(), { once: true }); existing.addEventListener("error", () => reject(new Error("Razorpay could not be loaded.")), { once: true }); return; }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js"; script.async = true;
    script.onload = () => resolve(); script.onerror = () => reject(new Error("Razorpay could not be loaded. Please check your connection and try again."));
    document.body.appendChild(script);
  });
}

function Label({ children, htmlFor }: { children: React.ReactNode; htmlFor: string }) { return <label className="checkout-label" htmlFor={htmlFor}>{children}</label>; }
function ErrorText({ message }: { message: string }) { return message ? <span className="checkout-error" role="alert">{message}</span> : null; }

export default function CheckoutExperience() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [cart, setCart] = useState<CartResponse>(emptyCart);
  const [cartStatus, setCartStatus] = useState<"loading" | "ready" | "error">("loading");
  const [busyItemKeys, setBusyItemKeys] = useState<Set<string>>(() => new Set());
  const [form, setForm] = useState(initialForm);
  const [touched, setTouched] = useState<Partial<Record<keyof CheckoutForm, boolean>>>({});
  const [shippingMethod, setShippingMethod] = useState<ShippingMethod>("standard");
  const [giftMessageEnabled, setGiftMessageEnabled] = useState(false);
  const [emailOffers, setEmailOffers] = useState(false);
  const [textOffers, setTextOffers] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [state, setState] = useState<CheckoutState>("idle");
  const [notice, setNotice] = useState("");
	const [recoveryVoucherCode, setRecoveryVoucherCode] = useState("");

  useEffect(() => {
    if (isLoading) return;
    let active = true;
    setCartStatus("loading");
    getCart().then((nextCart) => {
      if (active) { setCart(nextCart); setCartStatus("ready"); }
    }).catch(() => { if (active) setCartStatus("error"); });
    return () => { active = false; };
  }, [isLoading, user?.id]);

  const totals = useMemo(() => calculateTotals(cart.subtotal, shippingMethod), [cart.subtotal, shippingMethod]);
  const addressReady = ["address", "city", "state", "pin"].every((field) => !fieldError(form, field as keyof CheckoutForm));
  const requiredFields: Array<keyof CheckoutForm> = ["email", "firstName", "lastName", "address", "city", "state", "pin", "phone"];
  const formIsValid = requiredFields.every((field) => !fieldError(form, field));
  const readyToPay = cart.items.length > 0 && formIsValid && state !== "processing";
  const updateField = (field: keyof CheckoutForm, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const blurField = (field: keyof CheckoutForm) => setTouched((current) => ({ ...current, [field]: true }));

  async function changeQuantity(key: string, quantity: number) {
    if (busyItemKeys.has(key)) return;
    setBusyItemKeys((current) => new Set(current).add(key));
    try {
      setCart(quantity < 1 ? await removeCartItem(key) : await updateCartItem(key, quantity));
    } catch {
      setNotice("We could not update that quantity. Please try again.");
    } finally {
      setBusyItemKeys((current) => { const next = new Set(current); next.delete(key); return next; });
    }
  }

  async function startPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setTouched(Object.fromEntries(requiredFields.map((field) => [field, true]))); setNotice("");
    if (!readyToPay) { setNotice(cart.items.length ? "Review the highlighted fields before continuing." : "Your bag is empty. Add something special before checking out."); return; }
    if (giftMessageEnabled && /<[^>]*>|javascript\s*:/i.test(form.giftMessage)) { setNotice("Please remove HTML or script content from your gift message."); return; }
    setState("processing");
    try {
      const token = await csrfToken();
		const orderResponse = await fetch("/api/payments/razorpay/order", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ shippingMethod, discountCode: user ? recoveryVoucherCode.trim() : "", customer: form }) });
      const order = await orderResponse.json() as { error?: string; orderId?: string; amount?: number; currency?: "INR"; keyId?: string };
      if (!orderResponse.ok || !order.orderId || !order.amount || !order.currency || !order.keyId) throw new Error(order.error || "We could not prepare your payment. Please try again.");
      await loadRazorpay(); if (!window.Razorpay) throw new Error("Razorpay could not be opened. Please try again.");
      const payment = new window.Razorpay({
        key: order.keyId, amount: order.amount, currency: order.currency, name: "YAFA VANAM", order_id: order.orderId,
        prefill: { name: `${form.firstName} ${form.lastName}`.trim(), email: form.email, contact: `+91${form.phone.replace(/\s/g, "")}` }, theme: { color: "#111111" },
        modal: { ondismiss: () => { setState("idle"); setNotice("Payment was cancelled. Your checkout details are still here."); } },
        handler: async (response: RazorpayResponse) => {
          try {
            const verification = await fetch("/api/payments/razorpay/verify", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify(response) });
            const result = await verification.json() as { error?: string; verified?: boolean; order_number?: string };
            if (!verification.ok || !result.verified) throw new Error(result.error || "We could not verify the payment.");
            router.push(`/order-confirmation?order_id=${encodeURIComponent(result.order_number || "")}`);
          } catch (error) { setState("idle"); setNotice(error instanceof Error ? error.message : "We could not verify the payment. Please contact support before trying again."); }
        },
      }); payment.open();
    } catch (error) { setState("idle"); setNotice(error instanceof Error ? error.message : "We could not start the payment. Please try again."); }
  }

  return <main className="checkout-page"><div className="checkout-layout">
    <form className="checkout-main" onSubmit={startPayment} noValidate>
      <header className="checkout-header"><Link className="checkout-wordmark" href="/" aria-label="YAFA VANAM home">YAFA<br />VANAM</Link><Link className="checkout-sign-in" href="/auth/sign-in">Sign in</Link></header>
      <section className="checkout-section"><div className="checkout-section__title"><h1>Contact information</h1><span>Already have an account? <Link href="/auth/sign-in">Sign in</Link></span></div><Label htmlFor="checkout-email">Email address</Label><input id="checkout-email" type="email" autoComplete="email" value={form.email} onChange={(event) => updateField("email", event.target.value)} onBlur={() => blurField("email")} aria-invalid={Boolean(touched.email && fieldError(form, "email"))} placeholder="you@example.com" /><ErrorText message={touched.email ? fieldError(form, "email") : ""} /><label className="checkout-check"><input type="checkbox" checked={emailOffers} onChange={(event) => setEmailOffers(event.target.checked)} /><span>Email me with news and thoughtful offers</span></label></section>
      <section className="checkout-section"><h2>Delivery</h2><div className="checkout-field"><Label htmlFor="checkout-country">Country / Region</Label><select id="checkout-country" defaultValue="India" autoComplete="country"><option>India</option></select></div><div className="checkout-grid checkout-grid--two"><div><Label htmlFor="checkout-first-name">First name</Label><input id="checkout-first-name" autoComplete="given-name" value={form.firstName} onChange={(event) => updateField("firstName", event.target.value)} onBlur={() => blurField("firstName")} aria-invalid={Boolean(touched.firstName && fieldError(form, "firstName"))} /><ErrorText message={touched.firstName ? fieldError(form, "firstName") : ""} /></div><div><Label htmlFor="checkout-last-name">Last name</Label><input id="checkout-last-name" autoComplete="family-name" value={form.lastName} onChange={(event) => updateField("lastName", event.target.value)} onBlur={() => blurField("lastName")} aria-invalid={Boolean(touched.lastName && fieldError(form, "lastName"))} /><ErrorText message={touched.lastName ? fieldError(form, "lastName") : ""} /></div></div><div className="checkout-field"><Label htmlFor="checkout-address">Address</Label><input id="checkout-address" autoComplete="street-address" value={form.address} onChange={(event) => updateField("address", event.target.value)} onBlur={() => blurField("address")} aria-invalid={Boolean(touched.address && fieldError(form, "address"))} placeholder="House number and street" /><ErrorText message={touched.address ? fieldError(form, "address") : ""} /></div><div className="checkout-field"><Label htmlFor="checkout-apartment">Apartment, floor or suite <em>(optional)</em></Label><input id="checkout-apartment" autoComplete="address-line2" value={form.apartment} onChange={(event) => updateField("apartment", event.target.value)} /></div><div className="checkout-grid checkout-grid--three"><div><Label htmlFor="checkout-city">City</Label><input id="checkout-city" autoComplete="address-level2" value={form.city} onChange={(event) => updateField("city", event.target.value)} onBlur={() => blurField("city")} aria-invalid={Boolean(touched.city && fieldError(form, "city"))} /><ErrorText message={touched.city ? fieldError(form, "city") : ""} /></div><div><Label htmlFor="checkout-state">State</Label><select id="checkout-state" autoComplete="address-level1" value={form.state} onChange={(event) => updateField("state", event.target.value)} onBlur={() => blurField("state")} aria-invalid={Boolean(touched.state && fieldError(form, "state"))}><option value="">Select</option><option>Karnataka</option><option>Maharashtra</option><option>Delhi</option><option>Tamil Nadu</option><option>Telangana</option><option>West Bengal</option><option>Other</option></select><ErrorText message={touched.state ? fieldError(form, "state") : ""} /></div><div><Label htmlFor="checkout-pin">PIN code</Label><input id="checkout-pin" inputMode="numeric" autoComplete="postal-code" maxLength={6} value={form.pin} onChange={(event) => updateField("pin", event.target.value.replace(/\D/g, ""))} onBlur={() => blurField("pin")} aria-invalid={Boolean(touched.pin && fieldError(form, "pin"))} /><ErrorText message={touched.pin ? fieldError(form, "pin") : ""} /></div></div><div className="checkout-field"><Label htmlFor="checkout-phone">Phone</Label><input id="checkout-phone" inputMode="tel" autoComplete="tel-national" maxLength={10} value={form.phone} onChange={(event) => updateField("phone", event.target.value.replace(/\D/g, ""))} onBlur={() => blurField("phone")} aria-invalid={Boolean(touched.phone && fieldError(form, "phone"))} placeholder="10-digit mobile number" /><ErrorText message={touched.phone ? fieldError(form, "phone") : ""} /></div><label className="checkout-check"><input type="checkbox" checked={textOffers} onChange={(event) => setTextOffers(event.target.checked)} /><span>Text me with news and thoughtful offers</span></label></section>
      <section className="checkout-section"><h2>How would you like your order delivered?</h2><p className="checkout-lead">Please allow 1–3 business days of processing before your order ships.</p>{!addressReady ? <p className="checkout-info">Enter your delivery address to view available shipping methods.</p> : <div className="checkout-options"><label className={`checkout-option${shippingMethod === "standard" ? " is-selected" : ""}`}><input type="radio" name="shipping" value="standard" checked={shippingMethod === "standard"} onChange={() => setShippingMethod("standard")} /><span><strong>Standard delivery</strong><small>Estimated 4–6 business days</small></span><b>{cart.subtotal >= FREE_SHIPPING_THRESHOLD ? "Complimentary" : formatCatalogPrice(cart.currency, 199)}</b></label><label className={`checkout-option${shippingMethod === "express" ? " is-selected" : ""}`}><input type="radio" name="shipping" value="express" checked={shippingMethod === "express"} onChange={() => setShippingMethod("express")} /><span><strong>Express delivery</strong><small>Estimated 2–3 business days</small></span><b>{formatCatalogPrice(cart.currency, 299)}</b></label></div>}</section>
      <section className="checkout-section checkout-gifts"><h2>Gift options</h2><label className="checkout-check"><input type="checkbox" checked={giftMessageEnabled} onChange={(event) => setGiftMessageEnabled(event.target.checked)} /><span>Add a gift message</span></label>{giftMessageEnabled ? <textarea value={form.giftMessage} onChange={(event) => updateField("giftMessage", event.target.value)} placeholder="Write a personal note…" maxLength={250} /> : null}</section>
      {user ? <section className="checkout-section"><h2>Recovery voucher</h2><p className="checkout-lead">Have a YV_20 code from our support team? It can only be used on your signed-in account.</p><Label htmlFor="checkout-recovery-voucher">YV_20 code <em>(optional)</em></Label><input id="checkout-recovery-voucher" value={recoveryVoucherCode} onChange={(event) => setRecoveryVoucherCode(event.target.value.toUpperCase())} maxLength={32} autoComplete="off" placeholder="YV20-XXXXXXXX" /></section> : null}
      <section className="checkout-section checkout-payment"><h2>Payment</h2><p className="checkout-lead">All transactions are secure and encrypted.</p><div className="checkout-payment-card"><span className="checkout-payment-card__radio" aria-hidden="true" /><div><strong>Secure payment with Razorpay</strong><small>Choose UPI, card, net banking, wallet or other available methods securely in the next step.</small></div></div><div className="checkout-payment-methods" aria-label="Accepted payment methods"><Image src="/images/payment/card-networks.svg" alt="Visa, American Express, UnionPay, Diners Club, Discover, JCB and Mastercard" width={282} height={36} /></div><p className="checkout-payment-note">Your card or UPI details are collected only by Razorpay’s secure checkout. YAFA VANAM never sees or stores them.</p><p className="checkout-payment-trust"><Image src="/images/payment/razorpay.svg" alt="Razorpay" width={166} height={40} /><span>Protected payment gateway</span></p></section>
      <section className="checkout-section checkout-terms"><p>By placing your order, you agree to our <Link href="/terms">Terms &amp; Conditions</Link> and <Link href="/privacy-policy">Privacy Policy</Link>. Payments are processed securely by Razorpay.</p></section>{notice ? <p className={`checkout-notice${state === "processing" ? " is-processing" : ""}`} role="status">{notice}</p> : null}<button className="checkout-submit" type="submit" disabled={!readyToPay} aria-busy={state === "processing"}>{state === "processing" ? "Preparing secure payment…" : `Pay ${formatCatalogPrice(cart.currency, totals.total)}`}</button><footer className="checkout-footer"><Link href="/shipping">Shipping</Link><Link href="/returns">Returns</Link><Link href="/faq">Help</Link></footer>
    </form>
    <aside className={`checkout-summary${summaryOpen ? " is-open" : ""}`} aria-label="Order summary"><button className="checkout-summary__toggle" type="button" onClick={() => setSummaryOpen((value) => !value)} aria-expanded={summaryOpen}><span>Order summary <em>({cart.itemCount})</em></span><strong>{formatCatalogPrice(cart.currency, totals.total)}</strong><b aria-hidden="true">⌄</b></button><div className="checkout-summary__content">{cartStatus === "loading" ? <p className="checkout-summary__empty">Loading your ritual…</p> : null}{cartStatus === "error" ? <p className="checkout-summary__empty">We could not load your bag. Refresh and try again.</p> : null}{cartStatus === "ready" && !cart.items.length ? <p className="checkout-summary__empty">Your bag is waiting for something beautiful. <Link href="/shop">Explore the collection</Link>.</p> : null}{cart.items.map((item) => { const pending = busyItemKeys.has(item.key); return <article className="checkout-line" key={item.key} aria-busy={pending}><div className="checkout-line__image"><Image src={item.image} alt="" fill sizes="72px" /><span>{item.quantity}</span></div><div><h2>{item.name}</h2><p>{[item.size, item.shade].filter(Boolean).join(" · ") || item.productType}</p><div className="checkout-line__quantity" aria-label={`Quantity for ${item.name}`}><button type="button" disabled={pending} onClick={() => changeQuantity(item.key, item.quantity - 1)} aria-label={`Decrease ${item.name} quantity`}>−</button><span aria-live="polite">{item.quantity}</span><button type="button" disabled={pending || item.quantity >= 20} onClick={() => changeQuantity(item.key, item.quantity + 1)} aria-label={`Increase ${item.name} quantity`}>+</button></div><button className="checkout-line__remove" type="button" disabled={pending} onClick={() => changeQuantity(item.key, 0)}>Remove</button></div><strong>{formatCatalogPrice(item.currency, item.unitPrice * item.quantity)}</strong></article>; })}<dl className="checkout-totals"><div><dt>Subtotal <span>· {cart.itemCount} {cart.itemCount === 1 ? "item" : "items"}</span></dt><dd>{formatCatalogPrice(cart.currency, cart.subtotal)}</dd></div><div><dt>Shipping</dt><dd>{addressReady ? (totals.shipping ? formatCatalogPrice(cart.currency, totals.shipping) : "Complimentary") : "Enter delivery address"}</dd></div><div className="checkout-total"><dt>Total <small>INR</small></dt><dd>{formatCatalogPrice(cart.currency, totals.total)}</dd></div></dl></div></aside>
  </div></main>;
}
