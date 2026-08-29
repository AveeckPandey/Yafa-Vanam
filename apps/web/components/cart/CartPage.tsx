"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { CartResponse } from "@/lib/cart-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { useYafa } from "@/components/yafa/YafaProvider";
import { getCart, removeCartItem, updateCartItem } from "./cart-client";
import styles from "./CartPage.module.css";

const emptyCart: CartResponse = { items: [], itemCount: 0, subtotal: 0, currency: "INR" };

export default function CartPage() {
  const { setPageContext } = useYafa();
  const [cart, setCart] = useState<CartResponse>(emptyCart);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [busyKeys, setBusyKeys] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState("");

  useEffect(() => {
    setPageContext({ type: "cart" });
    return () => setPageContext(null);
  }, [setPageContext]);

  useEffect(() => {
    let active = true;
    getCart()
      .then((nextCart) => {
        if (!active) return;
        setCart(nextCart);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    return () => { active = false; };
  }, []);

  const changeQuantity = async (key: string, quantity: number) => {
    if (busyKeys.has(key)) return;
    setBusyKeys((current) => new Set(current).add(key));
    setError("");
    try {
      setCart(quantity < 1 ? await removeCartItem(key) : await updateCartItem(key, quantity));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not update your bag. Please try again.");
    } finally {
      setBusyKeys((current) => {
        const next = new Set(current);
        next.delete(key);
        return next;
      });
    }
  };

  return (
    <main className={styles.page} id="main-content">
      <header className={styles.header}>
        <p>YOUR BAG</p>
        <h1>Your beauty edit, ready when you are.</h1>
        <span>{cart.itemCount ? `${cart.itemCount} ${cart.itemCount === 1 ? "item" : "items"} selected` : "Add pieces that feel like you."}</span>
      </header>

      {status === "loading" ? <p className={styles.status}>Loading your bag…</p> : null}
      {status === "error" ? <p className={styles.error} role="alert">We could not load your bag. Please refresh and try again.</p> : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {status === "ready" && cart.items.length === 0 ? (
        <section className={styles.empty}>
          <h2>Your bag is waiting for something beautiful.</h2>
          <p>Explore the collection or let YAFA help you find a shade, ritual, or full look.</p>
          <div><Link className="button-primary" href="/shop">Explore the collection <span aria-hidden="true">→</span></Link><Link href="/yafa">Find your shade</Link></div>
        </section>
      ) : null}

      {cart.items.length ? (
        <div className={styles.layout}>
          <section className={styles.items} aria-label="Bag items">
            {cart.items.map((item) => {
              const busy = busyKeys.has(item.key);
              return (
                <article className={styles.line} key={item.key} aria-busy={busy}>
                  <Link className={styles.image} href={`/products/${item.slug}`}>
                    <Image src={item.image} alt="" fill sizes="(max-width: 720px) 100px, 148px" />
                  </Link>
                  <div className={styles.details}>
                    <p>{item.productType}</p>
                    <h2><Link href={`/products/${item.slug}`}>{item.name}</Link></h2>
                    <span>{[item.size, item.shade].filter(Boolean).join(" · ") || "Standard option"}</span>
                    <div className={styles.lineActions}>
                      <div className={styles.quantity} aria-label={`Quantity for ${item.name}`}>
                        <button type="button" disabled={busy || item.quantity <= 1} onClick={() => void changeQuantity(item.key, item.quantity - 1)} aria-label={`Decrease ${item.name} quantity`}>−</button>
                        <span aria-live="polite">{item.quantity}</span>
                        <button type="button" disabled={busy || item.quantity >= 20} onClick={() => void changeQuantity(item.key, item.quantity + 1)} aria-label={`Increase ${item.name} quantity`}>+</button>
                      </div>
                      <button type="button" disabled={busy} onClick={() => void changeQuantity(item.key, 0)}>Remove</button>
                    </div>
                  </div>
                  <strong>{formatCatalogPrice(item.currency, item.unitPrice * item.quantity)}</strong>
                </article>
              );
            })}
          </section>

          <aside className={styles.summary}>
            <p>ORDER SUMMARY</p>
            <div><span>Subtotal</span><strong>{formatCatalogPrice(cart.currency, cart.subtotal)}</strong></div>
            <small>Delivery choices and final totals are confirmed securely at checkout.</small>
            <Link className="button-primary" href="/checkout">Secure checkout <span aria-hidden="true">→</span></Link>
            <Link className={styles.continue} href="/shop">Continue shopping</Link>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
