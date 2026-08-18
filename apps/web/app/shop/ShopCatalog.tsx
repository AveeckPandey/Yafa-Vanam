"use client";

import { useMemo, useState } from "react";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { CatalogProduct } from "@/lib/catalog-types";

type Department = "all" | "Makeup" | "Skincare" | "Body Care" | "Fragrance";

const departments: Array<{ value: Department; label: string; description: string }> = [
  { value: "all", label: "All", description: "Every YAFA VANAM ritual" },
  { value: "Makeup", label: "Makeup", description: "Colour and complexion" },
  { value: "Skincare", label: "Skin Care", description: "Daily care essentials" },
  { value: "Body Care", label: "Body Care", description: "Care beyond the face" },
  { value: "Fragrance", label: "Fragrance", description: "Quiet personal scent" },
];

export default function ShopCatalog({ products }: { products: CatalogProduct[] }) {
  const [department, setDepartment] = useState<Department>("all");
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);
  const visibleProducts = useMemo(() => department === "all" ? products : products.filter((product) => product.category === department), [department, products]);

  return <main id="main-content" className="shop-page">
    <section className="shop-page__intro" aria-labelledby="shop-title">
      <p>YAFA VANAM / Shop</p>
      <h1 id="shop-title">Beauty, made personal.</h1>
      <span>Explore complexion, colour, care and fragrance designed to become part of your ritual.</span>
    </section>
    <section className="shop-page__catalogue" aria-label="Shop catalogue">
      <div className="shop-page__toolbar">
        <div className="shop-page__departments" role="group" aria-label="Shop department">
          {departments.map((item) => <button key={item.value} type="button" className={department === item.value ? "is-active" : ""} aria-pressed={department === item.value} onClick={() => setDepartment(item.value)}>{item.label}</button>)}
        </div>
        <p aria-live="polite">{visibleProducts.length} {visibleProducts.length === 1 ? "product" : "products"} · {departments.find((item) => item.value === department)?.description}</p>
      </div>
      <div className="commerce-grid shop-page__grid">
        {visibleProducts.map((product, index) => <div className="commerce-grid__item" key={product.id}><ProductCard product={product} onQuickShop={setQuickProduct} eager={index < 4} showShadeCount={product.category === "Makeup"} /></div>)}
      </div>
    </section>
    <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
  </main>;
}
