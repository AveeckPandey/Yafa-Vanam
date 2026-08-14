"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { CartResponse } from "@/lib/cart-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getCart, removeCartItem, updateCartItem } from "./cart-client";

const emptyCart: CartResponse = { items: [], itemCount: 0, subtotal: 0, currency: "INR" };

export default function CartDrawer() {
  const [open, setOpen] = useState(false);
  const [cart, setCart] = useState<CartResponse>(emptyCart);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    getCart().then(setCart).catch(() => undefined);
    const onOpen = (event: Event) => {
      previousFocus.current = document.activeElement as HTMLElement | null;
      const detail = (event as CustomEvent<CartResponse>).detail;
      if (detail) setCart(detail);
      setOpen(true);
    };
    const onUpdate = (event: Event) => {
      const detail = (event as CustomEvent<CartResponse>).detail;
      if (detail) setCart(detail);
    };
    window.addEventListener("yafa-cart-open", onOpen);
    window.addEventListener("yafa-cart-updated", onUpdate);
    return () => {
      window.removeEventListener("yafa-cart-open", onOpen);
      window.removeEventListener("yafa-cart-updated", onUpdate);
    };
  }, []);

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
    setBusyKey(key);
    try {
      setCart(quantity < 1 ? await removeCartItem(key) : await updateCartItem(key, quantity));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className={`site-cart-drawer${open ? " is-open" : ""}`} aria-hidden={!open}>
      <button className="site-cart-drawer__scrim" type="button" tabIndex={open ? 0 : -1} aria-label="Close bag" onClick={close} />
      <section className="site-cart-drawer__panel" role="dialog" aria-modal="true" aria-labelledby="site-cart-title" inert={!open}>
        <header>
          <div><p>YAFA VANAM</p><h2 id="site-cart-title">Your bag <span>({cart.itemCount})</span></h2></div>
          <button ref={closeRef} type="button" aria-label="Close bag" onClick={close}>×</button>
        </header>

        <div className="site-cart-drawer__body">
          {cart.items.length === 0 ? (
            <div className="site-cart-drawer__empty">
              <p>Your fragrance ritual begins here.</p>
              <button type="button" onClick={close}>Continue shopping</button>
            </div>
          ) : cart.items.map((item) => (
            <article className="site-cart-line" key={item.key} aria-busy={busyKey === item.key}>
              <Link className="site-cart-line__image" href={`/products/${item.slug}`} onClick={close}>
                <Image src={item.image} alt="" fill sizes="104px" />
              </Link>
              <div>
                <p>{item.productType}</p>
                <h3><Link href={`/products/${item.slug}`} onClick={close}>{item.name}</Link></h3>
                {item.size ? <span>Size: {item.size}</span> : null}
                {item.shade ? <span>Shade: {item.shade}</span> : null}
                <strong>{formatCatalogPrice(item.currency, item.unitPrice)}</strong>
                <div className="site-cart-line__actions">
                  <div aria-label={`Quantity for ${item.name}`}>
                    <button type="button" disabled={busyKey === item.key} aria-label={`Decrease ${item.name} quantity`} onClick={() => changeQuantity(item.key, item.quantity - 1)}>−</button>
                    <span aria-live="polite">{item.quantity}</span>
                    <button type="button" disabled={busyKey === item.key} aria-label={`Increase ${item.name} quantity`} onClick={() => changeQuantity(item.key, item.quantity + 1)}>+</button>
                  </div>
                  <button type="button" disabled={busyKey === item.key} onClick={() => changeQuantity(item.key, 0)}>Remove</button>
                </div>
              </div>
            </article>
          ))}
        </div>

        {cart.items.length > 0 ? (
          <footer>
            <div><span>Subtotal</span><strong>{formatCatalogPrice(cart.currency, cart.subtotal)}</strong></div>
            <p>Shipping and tax are calculated at checkout.</p>
            <Link href="/checkout" onClick={close}>Checkout</Link>
            <button type="button" onClick={close}>Continue shopping</button>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
