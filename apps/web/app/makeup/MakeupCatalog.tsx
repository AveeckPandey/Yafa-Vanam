"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { CatalogProduct, MakeupGroup } from "@/lib/catalog-types";

type MakeupFilter = "all" | MakeupGroup;
type SortOrder = "featured" | "price-asc" | "price-desc" | "name";

const categories: Array<{ value: MakeupFilter; label: string; image: string; alt: string }> = [
  { value: "face", label: "Face", image: "/images/yafavanam/skin/Softcanopy_Powder_Foundation/4N.png", alt: "Softcanopy Powder Foundation" },
  { value: "eyes", label: "Eyes", image: "/images/yafavanam/eye/eye%20color%20collection/eye%20canopy/Caramel_Brown.png", alt: "Canopy Eye Color" },
  { value: "lips", label: "Lips", image: "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Rose-Mist.png", alt: "Petal Velvet Lip Color" },
  { value: "cheeks", label: "Cheeks", image: "/images/yafavanam/cheeks/Airbloom/Airbloom-Rose-Mist.png", alt: "Airbloom Blush" },
];

const tabs: Array<{ value: MakeupFilter; label: string }> = [{ value: "all", label: "All" }, ...categories.map(({ value, label }) => ({ value, label }))];

export default function MakeupCatalog({ products }: { products: CatalogProduct[] }) {
  const [category, setCategory] = useState<MakeupFilter>("all");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [sortOrder, setSortOrder] = useState<SortOrder>("featured");
  const [filterOpen, setFilterOpen] = useState(false);
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);

  const availableTypes = useMemo(() => Array.from(new Set(products.filter((product) => category === "all" || product.makeupGroup === category).map((product) => product.productType))).sort(), [category, products]);
  const visibleProducts = useMemo(() => {
    const filtered = products.filter((product) => (category === "all" || product.makeupGroup === category) && (selectedTypes.length === 0 || selectedTypes.includes(product.productType)));
    if (sortOrder === "price-asc") return [...filtered].sort((a, b) => a.price - b.price);
    if (sortOrder === "price-desc") return [...filtered].sort((a, b) => b.price - a.price);
    if (sortOrder === "name") return [...filtered].sort((a, b) => a.name.localeCompare(b.name));
    return filtered;
  }, [category, products, selectedTypes, sortOrder]);

  const selectCategory = (next: MakeupFilter) => { setCategory(next); setSelectedTypes([]); };

  return (
    <main id="main-content" className="makeup-collection-page">
      <section className="makeup-collection-intro" aria-labelledby="makeup-title">
        <p>Home <span aria-hidden="true">/</span> Makeup</p>
        <div><span>The color ritual</span><h1 id="makeup-title">All Makeup</h1><strong>Color, complexion and definition — considered as one ritual.</strong></div>
        <nav className="makeup-category-nav" aria-label="Makeup categories">{categories.map((item) => <button key={item.value} type="button" className={category === item.value ? "is-active" : ""} aria-pressed={category === item.value} onClick={() => selectCategory(item.value)}><span><Image src={item.image} alt={item.alt} fill sizes="(max-width: 760px) 38vw, 180px" /></span><b>{item.label}</b></button>)}</nav>
      </section>

      <section className="collection-shop makeup-collection-shop" aria-label="Makeup collection">
        <div className="collection-toolbar makeup-collection-toolbar">
          <div className="collection-tabs" role="group" aria-label="Filter by makeup category">{tabs.map((item) => <button key={item.value} type="button" className={category === item.value ? "is-active" : ""} aria-pressed={category === item.value} onClick={() => selectCategory(item.value)}>{item.label}</button>)}</div>
          <div className="collection-toolbar__actions"><button type="button" onClick={() => setFilterOpen(true)}><span aria-hidden="true">☷</span> Filters{selectedTypes.length ? ` (${selectedTypes.length})` : ""}</button><p>{visibleProducts.length} {visibleProducts.length === 1 ? "product" : "products"}</p><label className="collection-sort"><span>Sort</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)}><option value="featured">Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name: A–Z</option></select></label></div>
        </div>
        <div className="commerce-grid makeup-product-grid">
          {visibleProducts.map((product, index) => <div className="commerce-grid__item" key={product.id}>{category === "all" && selectedTypes.length === 0 && sortOrder === "featured" && index === 6 ? <article className="makeup-shade-tile"><p>Find your shade</p><h2>A more personal starting point for complexion.</h2><Link href="/build-my-kit">Find My Shade <span aria-hidden="true">↗</span></Link></article> : null}<ProductCard product={product} onQuickShop={setQuickProduct} eager={index < 4} showShadeCount /></div>)}
        </div>
      </section>

      <div className={`filter-sheet${filterOpen ? " is-open" : ""}`} aria-hidden={!filterOpen}>
        <button className="filter-sheet__scrim" type="button" aria-label="Close filters" tabIndex={filterOpen ? 0 : -1} onClick={() => setFilterOpen(false)} />
        <section role="dialog" aria-modal="true" aria-labelledby="makeup-filter-title" inert={!filterOpen}><header><div><p>Filters</p><h2 id="makeup-filter-title">Refine the collection</h2></div><button type="button" aria-label="Close filters" onClick={() => setFilterOpen(false)}>×</button></header><fieldset><legend>Product type</legend>{availableTypes.map((type) => <label key={type}><input type="checkbox" checked={selectedTypes.includes(type)} onChange={() => setSelectedTypes((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type])} /><span>{type}</span></label>)}</fieldset><footer><button type="button" onClick={() => setSelectedTypes([])}>Clear</button><button type="button" onClick={() => setFilterOpen(false)}>View {visibleProducts.length} products</button></footer></section>
      </div>

      <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
    </main>
  );
}
