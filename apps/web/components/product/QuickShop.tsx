"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { CatalogProduct } from "@/lib/catalog-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getMakeupVariantImage } from "@/lib/makeup-variant-images";
import AddToBag from "./AddToBag";
import QuantitySelector from "./QuantitySelector";

export default function QuickShop({ product, onClose }: { product: CatalogProduct | null; onClose: () => void }) {
  const [quantity, setQuantity] = useState(1);
  const [variantId, setVariantId] = useState("");
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!product) return;
    setQuantity(1);
    setVariantId(product.defaultVariantId);
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const panel = closeRef.current?.closest(".quick-shop__panel");
      const focusable = panel?.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [onClose, product]);

  const visibleVariants = product?.variants.filter((variant) => variant.size || variant.shade) ?? [];
  const selected = product?.variants.find((variant) => variant.id === variantId);
  const selectedImage = product ? getMakeupVariantImage(product.id, variantId) ?? product.image : null;

  return (
    <div className={`quick-shop${product ? " is-open" : ""}`} aria-hidden={!product}>
      <button className="quick-shop__scrim" type="button" tabIndex={product ? 0 : -1} aria-label="Close Quick Shop" onClick={onClose} />
      <section className="quick-shop__panel" role="dialog" aria-modal="true" aria-labelledby="quick-shop-title" inert={!product}>
        {product ? (
          <>
            <header><p>Quick Shop</p><button ref={closeRef} type="button" aria-label="Close Quick Shop" onClick={onClose}>×</button></header>
            <div className="quick-shop__image"><Image key={selectedImage} src={selectedImage ?? product.image} alt={product.imageAlt} fill sizes="(max-width: 640px) 100vw, 360px" /></div>
            <div className="quick-shop__copy">
              <p>{product.productType}</p>
              <h2 id="quick-shop-title">{product.name}</h2>
              {product.fragranceProfile ? <span>{product.fragranceProfile.family.replaceAll("_", " ")}</span> : null}
              <strong>{formatCatalogPrice(product.currency, selected?.price ?? product.price)}</strong>
              {visibleVariants.length > 0 ? (
                <fieldset className="quick-shop__variants"><legend>{visibleVariants.some((variant) => variant.shade) ? "Choose shade" : "Choose option"}</legend><div>{visibleVariants.map((variant) => <button key={variant.id} type="button" className={variantId === variant.id ? "is-selected" : ""} aria-pressed={variantId === variant.id} aria-label={`Select ${variant.shade?.name ?? variant.size ?? "option"}`} onClick={() => setVariantId(variant.id)}>{variant.shade?.hex ? <i style={{ backgroundColor: variant.shade.hex }} aria-hidden="true" /> : null}<span>{variant.size ?? variant.shade?.name}</span></button>)}</div><p aria-live="polite">Selected: {selected?.shade?.name ?? selected?.size ?? "Default option"}</p></fieldset>
              ) : null}
              <div className="quick-shop__purchase"><QuantitySelector value={quantity} onChange={setQuantity} /><AddToBag className="quick-shop__add" productId={product.id} variantId={variantId || product.defaultVariantId} quantity={quantity} /></div>
              <Link href={`/products/${product.slug}`} onClick={onClose}>View full details <span aria-hidden="true">→</span></Link>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
