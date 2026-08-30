"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { CatalogProduct } from "@/lib/catalog-types";

type Category = "all" | "eau-de-parfum" | "body-mist" | "hair-body-mist" | "solid-perfume" | "warm-fragrance";
type SortOrder = "featured" | "price-asc" | "price-desc" | "name";

const categories: Array<{ value: Category; label: string }> = [
  { value: "all", label: "All" },
  { value: "eau-de-parfum", label: "Eau de Parfum" },
  { value: "body-mist", label: "Body Mists" },
  { value: "hair-body-mist", label: "Hair & Body" },
  { value: "solid-perfume", label: "Solid Perfume" },
  { value: "warm-fragrance", label: "Warm Fragrance" },
];

const productTypes = ["Eau de Parfum", "Body Mist", "Hair & Body Mist", "Solid Perfume Balm", "Fragrance"];

export default function FragranceCatalog({ products }: { products: CatalogProduct[] }) {
  const searchParams = useSearchParams();
  const [category, setCategory] = useState<Category>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("featured");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [filterOpen, setFilterOpen] = useState(false);
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);
  const requestedCategory = searchParams.get("category")?.toLowerCase() ?? null;
  const resolvedCategory: Category = categories.some((item) => item.value === requestedCategory) ? requestedCategory as Category : "all";

  useEffect(() => {
    setCategory(resolvedCategory);
    setSelectedTypes([]);
  }, [resolvedCategory]);

  const visibleProducts = useMemo(() => {
    const filtered = products.filter((product) => {
      const matchesCategory = category === "all"
        || (category === "eau-de-parfum" && product.productType === "Eau de Parfum")
        || (category === "body-mist" && product.productType === "Body Mist")
        || (category === "hair-body-mist" && product.productType === "Hair & Body Mist")
        || (category === "solid-perfume" && product.productType === "Solid Perfume Balm");
      const isWarmFragrance = category === "warm-fragrance" && product.name.toLowerCase().includes("warm");
      return (matchesCategory || isWarmFragrance) && (selectedTypes.length === 0 || selectedTypes.includes(product.productType));
    });
    if (sortOrder === "price-asc") return [...filtered].sort((a, b) => a.price - b.price);
    if (sortOrder === "price-desc") return [...filtered].sort((a, b) => b.price - a.price);
    if (sortOrder === "name") return [...filtered].sort((a, b) => a.name.localeCompare(b.name));
    return filtered;
  }, [category, products, selectedTypes, sortOrder]);

  return (
    <main id="main-content" className="fragrance-collection-page">
      <section className="collection-intro collection-intro--image collection-intro--fragrance" aria-labelledby="fragrance-title">
        <Image className="collection-intro__image" src="/images/home/campaign/hero-fragrance-lakeside.png" alt="" fill priority sizes="100vw" />
        <div className="collection-intro__veil" aria-hidden="true" />
        <div className="collection-intro__eyebrow">Fragrance</div>
        <h1 id="fragrance-title">Fragrance, in its<br />quietest form.</h1>
      </section>

      <section className="collection-shop" aria-label="Fragrance collection">
        <div className="collection-toolbar">
          <div className="collection-tabs" role="group" aria-label="Filter by fragrance category">
            {categories.map((item) => <button key={item.value} type="button" className={category === item.value ? "is-active" : ""} aria-pressed={category === item.value} onClick={() => { setCategory(item.value); setSelectedTypes([]); }}>{item.label}</button>)}
          </div>
          <div className="collection-toolbar__actions">
            <button type="button" onClick={() => setFilterOpen(true)}><span aria-hidden="true">☷</span> Filter{selectedTypes.length ? ` (${selectedTypes.length})` : ""}</button>
            <label className="collection-sort"><span>Sort</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)}><option value="featured">Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name: A–Z</option></select></label>
            <p>{visibleProducts.length} {visibleProducts.length === 1 ? "product" : "products"}</p>
          </div>
        </div>
        {requestedCategory ? <p className="collection-status" aria-live="polite">{resolvedCategory === "all" ? `“${requestedCategory}” is not a recognised category. Showing all fragrance.` : `Showing ${categories.find((item) => item.value === resolvedCategory)?.label.toLowerCase()}.`}</p> : null}

        <div className="commerce-grid">
          {visibleProducts.map((product, index) => (
            <div className="commerce-grid__item" key={product.id}>
              {category === "all" && !selectedTypes.length && sortOrder === "featured" && index === 0 ? (
                <article className="collection-editorial-tile"><Image src="/images/hero/yafa-vanam-fragrance-collection.png" alt="YAFA VANAM fragrance collection campaign" fill sizes="25vw" /><div className="collection-editorial-tile__shade" /><div className="collection-editorial-tile__content"><p>From the atelier</p><h3>Fragrance as a quiet ritual.</h3><span>Discover the collection</span></div></article>
              ) : null}
              <ProductCard product={product} onQuickShop={setQuickProduct} eager={index < 3} />
            </div>
          ))}
        </div>
      </section>

      <div className={`filter-sheet${filterOpen ? " is-open" : ""}`} aria-hidden={!filterOpen}>
        <button className="filter-sheet__scrim" type="button" aria-label="Close filters" tabIndex={filterOpen ? 0 : -1} onClick={() => setFilterOpen(false)} />
        <section role="dialog" aria-modal="true" aria-labelledby="filter-title" inert={!filterOpen}>
          <header><div><p>Filter</p><h2 id="filter-title">Refine the collection</h2></div><button type="button" aria-label="Close filters" onClick={() => setFilterOpen(false)}>×</button></header>
          <fieldset><legend>Product type</legend>{productTypes.map((type) => <label key={type}><input type="checkbox" checked={selectedTypes.includes(type)} onChange={() => setSelectedTypes((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type])} /><span>{type}</span></label>)}</fieldset>
          <footer><button type="button" onClick={() => setSelectedTypes([])}>Clear</button><button type="button" onClick={() => setFilterOpen(false)}>View {visibleProducts.length} products</button></footer>
        </section>
      </div>

      <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
    </main>
  );
}
