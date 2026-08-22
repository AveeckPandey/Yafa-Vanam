"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { CartResponse } from "@/lib/cart-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getCart, removeCartItem, updateCartItem } from "./cart-client";
import { useRequireAuth } from "@/components/auth/AuthProvider";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { getConfirmedYafaProfile, type ConfirmedYafaProfile } from "@/lib/yafa-profile";
import { trackEvent } from "@/lib/analytics";

const emptyCart: CartResponse = { items: [], itemCount: 0, subtotal: 0, currency: "INR" };

export default function CartDrawer() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [open, setOpen] = useState(false);
  const [cart, setCart] = useState<CartResponse>(emptyCart);
  const [cartStatus, setCartStatus] = useState<"loading" | "ready" | "error">("loading");
  const [busyKeys, setBusyKeys] = useState<Set<string>>(() => new Set());
  const [cartError, setCartError] = useState("");
  const [yafaProfile, setYafaProfile] = useState<ConfirmedYafaProfile | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const cartRevision = useRef(0);
  const pendingKeys = useRef(new Set<string>());

  const close = useCallback(() => setOpen(false), []);
  const checkout = useRequireAuth(() => { close(); router.push("/checkout"); });

  useEffect(() => {
    const onOpen = (event: Event) => {
      previousFocus.current = document.activeElement as HTMLElement | null;
      const detail = (event as CustomEvent<CartResponse>).detail;
      if (detail) { cartRevision.current += 1; setCart(detail); setCartStatus("ready"); }
      setOpen(true);
      trackEvent("cart_viewed", { item_count: detail?.itemCount ?? cart.itemCount });
    };
    const onUpdate = (event: Event) => {
      const detail = (event as CustomEvent<CartResponse>).detail;
      if (detail) { cartRevision.current += 1; setCart(detail); setCartStatus("ready"); }
    };
    window.addEventListener("yafa-cart-open", onOpen);
    window.addEventListener("yafa-cart-updated", onUpdate);
    return () => {
      window.removeEventListener("yafa-cart-open", onOpen);
      window.removeEventListener("yafa-cart-updated", onUpdate);
    };
  }, []);

  useEffect(() => {
    if (isLoading) return;
    let active = true;
    const initialRevision = cartRevision.current;
    setCartStatus("loading");
    getCart().then((nextCart) => {
      if (active && cartRevision.current === initialRevision) {
        setCart(nextCart);
        setCartStatus("ready");
      }
    }).catch(() => {
      // Keep the last confirmed cart if the startup request has a transient
      // failure. An error is not evidence that the cart is empty.
      if (active) setCartStatus("error");
    });
    return () => { active = false; };
  }, [isLoading, user?.id]);

  useEffect(() => {
    if (!user) {
      setYafaProfile(null);
      return;
    }
    getConfirmedYafaProfile().then(setYafaProfile).catch(() => setYafaProfile(null));
  }, [user]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key !== "Tab") return;
      const panel = closeRef.current?.closest(".site-cart-drawer__panel");
      const focusable = panel?.querySelectorAll<HTMLElement>(
        'a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [close, open]);

  const changeQuantity = async (key: string, quantity: number) => {
    if (quantity < 0 || pendingKeys.current.has(key)) return;
    pendingKeys.current.add(key);
    setBusyKeys((current) => new Set(current).add(key));
    setCartError("");
    try {
      setCart(quantity < 1 ? await removeCartItem(key) : await updateCartItem(key, quantity));
    } catch (error) {
      try { setCart(await getCart()); } catch { /* Keep the last confirmed cart if recovery is unavailable. */ }
      setCartError(error instanceof Error ? error.message : "We could not update your bag. Please try again.");
    } finally {
      pendingKeys.current.delete(key);
      setBusyKeys((current) => { const next = new Set(current); next.delete(key); return next; });
    }
  };
  const foundationMismatch = Boolean(yafaProfile && cart.items.some((item) => item.productType.toLowerCase().includes("foundation")) && !cart.items.some((item) => item.shade === yafaProfile.shade_name));

  return (
    <div className={`site-cart-drawer${open ? " is-open" : ""}`} aria-hidden={!open}>
      <button className="site-cart-drawer__scrim" type="button" tabIndex={open ? 0 : -1} aria-label="Close bag" onClick={close} />
      <section className="site-cart-drawer__panel" role="dialog" aria-modal="true" aria-labelledby="site-cart-title" inert={!open}>
        <header>
          <div><p>YAFA VANAM</p><h2 id="site-cart-title">Your bag <span>({cart.itemCount})</span></h2></div>
          <button ref={closeRef} type="button" aria-label="Close bag" onClick={close}>×</button>
        </header>

        <div className="site-cart-drawer__body">
          {cartError ? <p className="site-cart-drawer__error" role="alert">{cartError}</p> : null}
          {cartStatus === "loading" ? <p className="site-cart-drawer__empty">Loading your bag…</p> : null}
          {cartStatus === "error" ? <p className="site-cart-drawer__error" role="alert">We could not refresh your bag. Please try again.</p> : null}
          {foundationMismatch ? <aside className="site-cart-yafa-upsell">Your Yafa shade {yafaProfile?.shade_name} is available. <Link href="/shop" onClick={close}>Find your match</Link></aside> : null}
          {cartStatus === "ready" && cart.items.length === 0 ? (
            <div className="site-cart-drawer__empty">
              <p>Your fragrance ritual begins here.</p>
              <button type="button" onClick={close}>Continue shopping</button>
            </div>
          ) : cart.items.map((item) => (
            <article className="site-cart-line" key={item.key} aria-busy={busyKeys.has(item.key)}>
              <Link className="site-cart-line__image" href={`/products/${item.slug}`} onClick={close}>
                <Image src={item.image} alt="" fill sizes="104px" />
              </Link>
              <div>
                <p>{item.productType}</p>
                <h3><Link href={`/products/${item.slug}`} onClick={close}>{item.name}</Link></h3>
                {item.size ? <span>Size: {item.size}</span> : null}
                {item.shade ? <span>Shade: {item.shade}</span> : null}
                {yafaProfile?.shade_name === item.shade ? <small className="site-cart-yafa-match">Yafa match</small> : null}
                <strong>{formatCatalogPrice(item.currency, item.unitPrice)}</strong>
                <div className="site-cart-line__actions">
                  <div aria-label={`Quantity for ${item.name}`}>
                    <button type="button" disabled={busyKeys.has(item.key)} aria-label={`Decrease ${item.name} quantity`} onClick={() => changeQuantity(item.key, item.quantity - 1)}>−</button>
                    <span aria-live="polite">{item.quantity}</span>
                    <button type="button" disabled={busyKeys.has(item.key)} aria-label={`Increase ${item.name} quantity`} onClick={() => changeQuantity(item.key, item.quantity + 1)}>+</button>
                  </div>
                  <button type="button" disabled={busyKeys.has(item.key)} onClick={() => changeQuantity(item.key, 0)}>Remove</button>
                </div>
              </div>
            </article>
          ))}
        </div>

        {cart.items.length > 0 ? (
          <footer>
            <div><span>Subtotal</span><strong>{formatCatalogPrice(cart.currency, cart.subtotal)}</strong></div>
            <p>Shipping and tax are calculated at checkout.</p>
            <button type="button" onClick={checkout}>Checkout</button>
            <button type="button" onClick={close}>Continue shopping</button>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
