"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { CartResponse } from "@/lib/cart-types";
import { getCart } from "@/components/cart/cart-client";
import { csrfToken } from "@/lib/csrf-client";
import { trackEvent } from "@/lib/analytics";

type CheckoutStep = 1 | 2 | 3;
type AddressForm = { fullName: string; phone: string; email: string; addressLine1: string; addressLine2: string; city: string; state: string; pincode: string };
type FieldName = keyof AddressForm;
type RazorpayResponse = { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };
type CheckoutOrder = { orderId: string; amount: number; currency: "INR"; keyId: string; orderNumber: string };
type RazorpayInstance = { open: () => void };
type RazorpayConstructor = new (options: {
  key: string | undefined; amount: number; currency: "INR"; order_id: string; name: string;
  prefill: { name: string; email: string; contact: string }; theme: { color: string };
  handler: (response: RazorpayResponse) => void | Promise<void>; modal: { ondismiss: () => void };
}) => RazorpayInstance;

declare global { interface Window { Razorpay?: RazorpayConstructor } }

const emptyCart: CartResponse = { items: [], itemCount: 0, subtotal: 0, currency: "INR" };
const initialForm: AddressForm = { fullName: "", phone: "", email: "", addressLine1: "", addressLine2: "", city: "", state: "", pincode: "" };
const checkoutSteps: Array<{ number: CheckoutStep; label: string }> = [
  { number: 1, label: "Shipping" }, { number: 2, label: "Review" }, { number: 3, label: "Payment" },
];
const indianRegions = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
] as const;
const emailPattern = /^(?:[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+)@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/;
const unsafeMarkupPattern = /<script\b|javascript\s*:|<[^>]*>/i;

function cleanValue(value: string) { return value.trim(); }
function hasUnsafeMarkup(value: string) { return unsafeMarkupPattern.test(value); }
function asPaise(rupees: number) { return Math.round(rupees * 100); }
function formatInr(paise: number) { return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(paise / 100); }

function validateAndSanitize(form: AddressForm) {
  const values = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, cleanValue(value)])) as AddressForm;
  const errors: Partial<Record<FieldName, string>> = {};
  const required: FieldName[] = ["fullName", "phone", "email", "addressLine1", "city", "state", "pincode"];
  (Object.keys(values) as FieldName[]).forEach((field) => { if (hasUnsafeMarkup(values[field])) errors[field] = "Please remove HTML or script content."; });
  required.forEach((field) => { if (!values[field] && !errors[field]) errors[field] = "This field is required."; });
  if (!errors.fullName && values.fullName.length < 2) errors.fullName = "Enter your full name (at least 2 characters).";
  if (!errors.phone && !/^\+91[6-9]\d{9}$/.test(values.phone)) errors.phone = "Use +91 followed by a valid 10-digit Indian mobile number.";
  if (!errors.email && !emailPattern.test(values.email)) errors.email = "Enter a valid email address.";
  if (!errors.state && !indianRegions.includes(values.state as (typeof indianRegions)[number])) errors.state = "Select a state or union territory.";
  if (!errors.pincode && !/^\d{6}$/.test(values.pincode)) errors.pincode = "Enter a valid 6-digit pincode.";
  return { values, errors, isValid: Object.keys(errors).length === 0 };
}

function loadRazorpaySdk() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const source = "https://checkout.razorpay.com/v1/checkout.js";
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${source}"]`);
    const script = existing ?? document.createElement("script");
    let settled = false;
    const onLoad = () => finish(window.Razorpay ? undefined : new Error("Secure payment could not be initialized."));
    const onError = () => finish(new Error("Secure payment could not be loaded. Please try again."));
    const timeout = window.setTimeout(() => finish(new Error("Secure payment took too long to load. Please try again.")), 10_000);
    function finish(error?: Error) {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
      if (error) reject(error); else resolve();
    }
    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });
    if (!existing) { script.src = source; script.async = true; document.head.appendChild(script); }
  });
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p id={id} className="yv-checkout__field-error" role="alert">{message}</p> : null;
}

export default function CheckoutExperience() {
  const router = useRouter();
  const [step, setStep] = useState<CheckoutStep>(1);
  const [cart, setCart] = useState<CartResponse>(emptyCart);
  const [cartState, setCartState] = useState<"loading" | "ready" | "error">("loading");
  const [form, setForm] = useState<AddressForm>(initialForm);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [notice, setNotice] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isInitializingPayment, setIsInitializingPayment] = useState(false);
  const [paymentFailed, setPaymentFailed] = useState(false);

  useEffect(() => { getCart().then((loaded) => { setCart(loaded); setCartState("ready"); }).catch(() => setCartState("error")); }, []);
  const totals = useMemo(() => {
    const subtotal = asPaise(cart.subtotal);
    const shipping = subtotal >= 199_900 ? 0 : 19_900;
    return { subtotal, shipping, grandTotal: subtotal + shipping };
  }, [cart.subtotal]);
  const setField = (field: FieldName, value: string) => { setForm((current) => ({ ...current, [field]: value })); if (errors[field]) setErrors((current) => ({ ...current, [field]: undefined })); };

  function continueToSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateAndSanitize(form);
    setErrors(result.errors); setNotice("");
    if (!result.isValid) return;
    setForm(result.values); setStep(2); trackEvent("checkout_started", { item_count: cart.itemCount, currency: cart.currency });
  }

  function continueToPayment() {
    const result = validateAndSanitize(form);
    setErrors(result.errors);
    if (!result.isValid) { setStep(1); return; }
    if (!cart.items.length) { setNotice("Your bag is empty. Add an item before checking out."); return; }
    setForm(result.values); setNotice(""); setStep(3);
  }

  async function placeOrder() {
    const validation = validateAndSanitize(form);
    setErrors(validation.errors);
    if (!validation.isValid) { setStep(1); return; }
    if (!cart.items.length || isProcessing) { if (!cart.items.length) setNotice("Your bag is empty. Add an item before checking out."); return; }
    setForm(validation.values); setNotice(""); setPaymentFailed(false); setIsProcessing(true); setIsInitializingPayment(true);
    try {
      const nameParts = validation.values.fullName.split(/\s+/).filter(Boolean);
      const customer = {
        firstName: nameParts[0] || "Customer",
        lastName: nameParts.slice(1).join(" ") || "Customer",
        email: validation.values.email,
        phone: validation.values.phone.replace(/^\+91/, ""),
        address: validation.values.addressLine1,
        apartment: validation.values.addressLine2 || undefined,
        city: validation.values.city,
        state: validation.values.state,
        pin: validation.values.pincode,
      };
      const token = await csrfToken();
      trackEvent("payment_info_added", { payment_method: "razorpay" });
      const orderResponse = await fetch("/api/payments/razorpay/order", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ shippingMethod: "standard", discountCode: "", customer }) });
      const order = await orderResponse.json().catch(() => null) as CheckoutOrder | { error?: string } | null;
      if (!orderResponse.ok || !order || !("orderId" in order) || !order.orderId || !order.keyId) throw new Error(order && "error" in order && order.error ? order.error : "We could not prepare your secure payment. Please try again.");
      await loadRazorpaySdk();
      if (!window.Razorpay) throw new Error("Secure payment could not be initialized. Please try again.");

      let paymentSubmitted = false;
      const checkout = new window.Razorpay({
        key: order.keyId, amount: order.amount, currency: order.currency, order_id: order.orderId, name: "YAFA VANAM",
        prefill: { name: validation.values.fullName, email: validation.values.email, contact: validation.values.phone }, theme: { color: "#985b6a" },
        modal: { ondismiss: () => { if (!paymentSubmitted) { setIsProcessing(false); setPaymentFailed(true); setNotice("Payment was cancelled. Your delivery details are still saved here."); } } },
        handler: async (response) => {
          paymentSubmitted = true;
          if (!response?.razorpay_order_id || !response?.razorpay_payment_id || !response?.razorpay_signature) { setIsProcessing(false); setPaymentFailed(true); setNotice("Payment details were incomplete. Please retry payment."); return; }
          try {
            const verification = await fetch("/api/payments/razorpay/verify", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ razorpay_order_id: response.razorpay_order_id, razorpay_payment_id: response.razorpay_payment_id, razorpay_signature: response.razorpay_signature }) });
            const verified = await verification.json().catch(() => null) as { verified?: boolean; order_number?: string } | null;
            if (!verification.ok || !verified?.verified || !verified.order_number) throw new Error("Payment verification failed.");
            trackEvent("purchase_completed", { order_number: verified.order_number, currency: order.currency, amount: order.amount });
            router.push(`/order-confirmation?order_id=${encodeURIComponent(verified.order_number)}`);
          } catch { setIsProcessing(false); setPaymentFailed(true); setNotice("We could not verify your payment. Please retry payment or contact support."); }
        },
      });
      setIsInitializingPayment(false);
      checkout.open();
    } catch (error) {
      setIsInitializingPayment(false); setIsProcessing(false); setPaymentFailed(true);
      setNotice(error instanceof Error ? error.message : "We could not start secure payment. Please try again.");
    }
  }

  const field = (name: FieldName, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => {
    const errorId = `checkout-${name}-error`;
    return <label className="yv-checkout__field" htmlFor={`checkout-${name}`}><span>{label}</span><input id={`checkout-${name}`} value={form[name]} onChange={(event) => setField(name, event.target.value)} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? errorId : undefined} {...props} /><FieldError id={errorId} message={errors[name]} /></label>;
  };

  return <main className="yv-checkout">
    {isInitializingPayment ? <div className="yv-checkout__loading" role="status" aria-live="polite"><span /><p>Opening secure payment…</p></div> : null}
    <div className="yv-checkout__shell">
      <section className="yv-checkout__panel">
        <header className="yv-checkout__header"><Link href="/" className="yv-checkout__brand">YAFA VANAM</Link><span>Secure checkout</span></header>
        <ol className="yv-checkout__steps" aria-label="Checkout progress">{checkoutSteps.map(({ number, label }) => <li key={number} className={step === number ? "is-current" : step > number ? "is-complete" : ""}><span>{step > number ? "✓" : number}</span>{label}</li>)}</ol>
        {step === 1 ? <form onSubmit={continueToSummary} noValidate><div className="yv-checkout__intro"><p>Step 1 of 3</p><h1>Where should we send your ritual?</h1></div><div className="yv-checkout__form-grid">{field("fullName", "Full name", { autoComplete: "name", minLength: 2, required: true })}{field("phone", "Phone", { type: "tel", inputMode: "tel", autoComplete: "tel", placeholder: "+919876543210", required: true })}{field("email", "Email", { type: "email", autoComplete: "email", placeholder: "you@example.com", required: true })}{field("addressLine1", "Address line 1", { autoComplete: "address-line1", required: true })}{field("addressLine2", "Address line 2 (optional)", { autoComplete: "address-line2" })}{field("city", "City", { autoComplete: "address-level2", required: true })}<label className="yv-checkout__field" htmlFor="checkout-state"><span>State / Union Territory</span><select id="checkout-state" value={form.state} onChange={(event) => setField("state", event.target.value)} aria-invalid={Boolean(errors.state)} aria-describedby={errors.state ? "checkout-state-error" : undefined} autoComplete="address-level1" required><option value="">Select your state or UT</option>{indianRegions.map((region) => <option key={region} value={region}>{region}</option>)}</select><FieldError id="checkout-state-error" message={errors.state} /></label>{field("pincode", "Pincode", { inputMode: "numeric", autoComplete: "postal-code", maxLength: 6, required: true })}</div><button className="yv-checkout__primary" type="submit">Continue to review <span>→</span></button></form> : null}
        {step === 2 ? <section><div className="yv-checkout__intro"><p>Step 2 of 3</p><h1>Review your order</h1></div><article className="yv-checkout__address-card"><div><small>DELIVERING TO</small><strong>{form.fullName}</strong><p>{form.addressLine1}{form.addressLine2 ? `, ${form.addressLine2}` : ""}<br />{form.city}, {form.state} — {form.pincode}<br />{form.phone}</p></div><button type="button" onClick={() => setStep(1)}>Edit</button></article><OrderSummary cart={cart} totals={totals} loading={cartState === "loading"} />{notice ? <p className="yv-checkout__notice" role="alert">{notice}</p> : null}<div className="yv-checkout__actions"><button className="yv-checkout__secondary" type="button" onClick={() => setStep(1)}>Back</button><button className="yv-checkout__primary" type="button" onClick={continueToPayment} disabled={cartState !== "ready"}>Continue to payment <span>→</span></button></div></section> : null}
        {step === 3 ? <section><div className="yv-checkout__intro"><p>Step 3 of 3</p><h1>Choose secure payment</h1><span>UPI, cards, net banking and wallets are securely handled by Razorpay.</span></div><div className="yv-checkout__payment-card"><div className="yv-checkout__payment-icon">₹</div><div><strong>Razorpay Secure</strong><p>You’ll choose your payment method in the next secure window.</p></div><span>Protected</span></div><OrderSummary cart={cart} totals={totals} loading={cartState === "loading"} compact />{notice ? <p className="yv-checkout__notice" role="alert">{notice}</p> : null}<div className="yv-checkout__actions"><button className="yv-checkout__secondary" type="button" onClick={() => setStep(2)} disabled={isProcessing}>Back</button><button className="yv-checkout__primary" type="button" onClick={placeOrder} disabled={isProcessing || cartState !== "ready" || !cart.items.length} aria-busy={isProcessing}>{isProcessing ? "Preparing secure payment…" : `${paymentFailed ? "Retry payment" : "Place order"} · ${formatInr(totals.grandTotal)}`}</button></div></section> : null}
      </section>
      {step === 1 ? <aside className="yv-checkout__sidebar"><p className="yv-checkout__sidebar-eyebrow">YOUR BAG</p><h2>{cart.itemCount} {cart.itemCount === 1 ? "item" : "items"} selected</h2><p>Shipping and taxes will be calculated in the next step.</p><Link href="/cart">Edit bag</Link></aside> : null}
    </div>
  </main>;
}

function OrderSummary({ cart, totals, loading, compact = false }: { cart: CartResponse; totals: { subtotal: number; shipping: number; grandTotal: number }; loading: boolean; compact?: boolean }) {
  return <aside className={`yv-checkout__summary${compact ? " is-compact" : ""}`} aria-label="Order summary"><div className="yv-checkout__summary-title"><h2>Order summary</h2><span>{loading ? "Loading…" : `${cart.itemCount} items`}</span></div>{loading ? <p className="yv-checkout__empty">Loading your bag…</p> : null}{!loading && !cart.items.length ? <p className="yv-checkout__empty">Your bag is empty. <Link href="/shop">Explore the collection</Link>.</p> : null}{cart.items.map((item) => <article className="yv-checkout__line" key={item.key}><div className="yv-checkout__image"><Image src={item.image} alt="" fill sizes="64px" /><span>{item.quantity}</span></div><div><h3>{item.name}</h3><p>{item.shade || item.productType}</p><small>Qty {item.quantity} · {formatInr(asPaise(item.unitPrice))} each</small></div><strong>{formatInr(asPaise(item.unitPrice * item.quantity))}</strong></article>)}<dl className="yv-checkout__totals"><div><dt>Subtotal</dt><dd>{formatInr(totals.subtotal)}</dd></div><div><dt>Shipping</dt><dd>{totals.shipping === 0 ? "Complimentary" : formatInr(totals.shipping)}</dd></div><div className="yv-checkout__grand-total"><dt>Total</dt><dd>{formatInr(totals.grandTotal)}</dd></div></dl></aside>;
}
