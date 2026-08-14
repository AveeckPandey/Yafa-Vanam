"use client";

import Image from "next/image";
import Link from "next/link";
import type { CatalogProduct } from "@/lib/catalog-types";
import { formatCatalogPrice } from "@/lib/catalog-types";

export default function ProductCard({ product, onQuickShop, eager = false, showShadeCount = false }: { product: CatalogProduct; onQuickShop: (product: CatalogProduct) => void; eager?: boolean; showShadeCount?: boolean }) {
  const shadeCount = product.variants.filter((variant) => variant.isActive && variant.shade).length;
  return (
    <article className={`catalog-product-card${showShadeCount ? " catalog-product-card--makeup" : ""}`}>
      <div className="catalog-product-card__media">
        <Link href={`/products/${product.slug}`} aria-label={`View ${product.name}`}>
          <Image src={product.image} alt={product.imageAlt} fill loading={eager ? "eager" : "lazy"} sizes="(max-width: 640px) 100vw, (max-width: 1100px) 50vw, 25vw" />
        </Link>
        <button type="button" onClick={() => onQuickShop(product)}>Quick Shop</button>
      </div>
      <div className="catalog-product-card__copy">
        <p>{product.productType}</p>
        <h3><Link href={`/products/${product.slug}`}>{product.name}</Link></h3>
        {showShadeCount && shadeCount > 1 ? <span className="catalog-product-card__shade-count">{shadeCount} {shadeCount === 1 ? "shade" : "shades"}</span> : null}
        <strong>{formatCatalogPrice(product.currency, product.price)}</strong>
      </div>
    </article>
  );
}
