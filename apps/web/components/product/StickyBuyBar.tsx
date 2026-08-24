"use client";

import { useEffect, useState } from "react";
import { formatCatalogPrice } from "@/lib/catalog-types";
import AddToBag from "./AddToBag";

export default function StickyBuyBar({ name, price, currency, productId, variantId }: { name: string; price: number; currency: string; productId: string; variantId: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(max-width: 760px)").matches) {
      setVisible(true);
      return;
    }
    const purchase = document.getElementById("pdp-purchase");
    if (!purchase) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(!entry.isIntersecting), { threshold: 0 });
    observer.observe(purchase);
    return () => observer.disconnect();
  }, []);
  return (
    <aside className={`sticky-buy-bar${visible ? " is-visible" : ""}`} aria-label="Product purchase">
      <div><strong>{name}</strong><span>{formatCatalogPrice(currency, price)}</span></div>
      <AddToBag productId={productId} variantId={variantId} quantity={1} className="sticky-buy-bar__button" />
    </aside>
  );
}
