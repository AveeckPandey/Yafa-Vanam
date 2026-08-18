"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { CatalogProduct, SkincareGroup } from "@/lib/catalog-types";

type SkinCareFilter = "all" | "cleanse" | "treat" | "hydrate" | "protect" | "scalp-care";
type SortOrder = "featured" | "price-asc" | "price-desc" | "name";

const collectionTabs: Array<{ value: SkinCareFilter; label: string; groups: SkincareGroup[] }> = [
  { value: "all", label: "All", groups: [] },
  { value: "cleanse", label: "Cleanse", groups: ["cleansers"] },
  { value: "treat", label: "Treat", groups: ["serums-treatments", "eye-care", "lip-care", "masks-exfoliation"] },
  { value: "hydrate", label: "Hydrate", groups: ["moisturizers"] },
  { value: "protect", label: "Protect", groups: ["sunscreen"] },
  { value: "scalp-care", label: "Scalp Care", groups: ["scalp-care"] },
];

const skincareGroups: Array<{ value: SkincareGroup; label: string }> = [
  { value: "cleansers", label: "Cleansers" },
  { value: "serums-treatments", label: "Serums & Treatments" },
  { value: "eye-care", label: "Eye Care" },
  { value: "lip-care", label: "Lip Care" },
  { value: "masks-exfoliation", label: "Masks & Exfoliation" },
  { value: "moisturizers", label: "Moisturizers" },
  { value: "sunscreen", label: "Sunscreen" },
  { value: "scalp-care", label: "Scalp Care" },
];

const queryGroupMap: Record<string, SkincareGroup> = {
  cleansers: "cleansers",
  serums: "serums-treatments",
  "serums-treatments": "serums-treatments",
  "eye-care": "eye-care",
  "lip-care": "lip-care",
  masks: "masks-exfoliation",
  "masks-exfoliation": "masks-exfoliation",
  moisturisers: "moisturizers",
  moisturizers: "moisturizers",
  "sun-care": "sunscreen",
  sunscreen: "sunscreen",
  "scalp-care": "scalp-care",
};

export default function SkinCareCatalog({ products }: { products: CatalogProduct[] }) {
  const searchParams = useSearchParams();
  const [category, setCategory] = useState<SkinCareFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("featured");
  const [selectedGroups, setSelectedGroups] = useState<SkincareGroup[]>([]);
  const [filterOpen, setFilterOpen] = useState(false);
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);
  const requestedCategory = searchParams.get("category")?.toLowerCase() ?? null;
  const requestedGroup = requestedCategory ? queryGroupMap[requestedCategory] : null;

  useEffect(() => {
    setCategory("all");
    setSelectedGroups(requestedGroup ? [requestedGroup] : []);
  }, [requestedGroup]);

  const visibleProducts = useMemo(() => {
    const activeTab = collectionTabs.find((tab) => tab.value === category)!;
    const filtered = products.filter((product) => {
      const group = product.skincareGroup;
      if (!group) return false;
      const matchesTab = category === "all" || activeTab.groups.includes(group);
      return matchesTab && (selectedGroups.length === 0 || selectedGroups.includes(group));
    });
    if (sortOrder === "price-asc") return [...filtered].sort((a, b) => a.price - b.price);
    if (sortOrder === "price-desc") return [...filtered].sort((a, b) => b.price - a.price);
    if (sortOrder === "name") return [...filtered].sort((a, b) => a.name.localeCompare(b.name));
    return filtered;
  }, [category, products, selectedGroups, sortOrder]);

  const groupCount = (group: SkincareGroup) => products.filter((product) => product.skincareGroup === group).length;
  const selectCategory = (next: SkinCareFilter) => { setCategory(next); setSelectedGroups([]); };

  return (
    <main id="main-content" className="skincare-collection-page">
      <section className="collection-intro" aria-labelledby="skincare-title">
        <div className="collection-intro__eyebrow">The daily skin ritual</div>
        <h1 id="skincare-title">Skin care, made into a ritual.</h1>
        <p>Thoughtful essentials for cleansing, treating, hydrating and protecting the skin — designed around what your skin needs.</p>
      </section>

      <section className="collection-shop" aria-label="Skin Care collection">
        <div className="collection-toolbar">
          <div className="collection-tabs" role="group" aria-label="Filter by Skin Care routine step">
            {collectionTabs.map((item) => (
              <button key={item.value} type="button" className={category === item.value && selectedGroups.length === 0 ? "is-active" : ""} aria-pressed={category === item.value && selectedGroups.length === 0} onClick={() => selectCategory(item.value)}>
                {item.label}
              </button>
            ))}
          </div>
          <div className="collection-toolbar__actions">
            <button type="button" onClick={() => setFilterOpen(true)}><span aria-hidden="true">☷</span> Filter{selectedGroups.length ? ` (${selectedGroups.length})` : ""}</button>
            <label className="collection-sort"><span>Sort</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)}><option value="featured">Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name: A–Z</option></select></label>
            <p>{visibleProducts.length} {visibleProducts.length === 1 ? "product" : "products"}</p>
          </div>
        </div>
        {requestedCategory ? <p className="collection-status" aria-live="polite">{requestedGroup ? `Showing ${skincareGroups.find((group) => group.value === requestedGroup)?.label.toLowerCase()}.` : `“${requestedCategory}” is not a recognised category. Showing all skin care.`}</p> : null}

        <div className="commerce-grid">
          {visibleProducts.map((product, index) => (
            <div className="commerce-grid__item" key={product.id}>
              {category === "all" && selectedGroups.length === 0 && sortOrder === "featured" && index === 0 ? (
                <article className="collection-editorial-tile"><Image src="/images/yafavanam/No%20Shades%20Items/face%20Care/Morningroot_Daily_Face_Cleanser.png" alt="Morningroot Daily Face Cleanser by YAFA VANAM" fill sizes="25vw" /><div className="collection-editorial-tile__shade" /><div className="collection-editorial-tile__content"><p>The daily ritual</p><h3>Care, at your own pace.</h3><span>Discover Skin Care</span></div></article>
              ) : null}
              {category === "all" && selectedGroups.length === 0 && sortOrder === "featured" && index === 7 ? (
                <article className="collection-kit-tile"><div className="collection-kit-tile__mark" aria-hidden="true">YV</div><div><p>Your skin care ritual</p><h3>Build a routine around what your skin needs.</h3><span>Cleanse, treat, hydrate and protect — one thoughtful step at a time.</span></div><Link href="/build-my-kit">Build My Kit <span aria-hidden="true">↗</span></Link></article>
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
          <fieldset><legend>Routine step</legend>{skincareGroups.map((group) => <label key={group.value}><input type="checkbox" checked={selectedGroups.includes(group.value)} onChange={() => setSelectedGroups((current) => current.includes(group.value) ? current.filter((item) => item !== group.value) : [...current, group.value])} /><span>{group.label} ({groupCount(group.value)})</span></label>)}</fieldset>
          <footer><button type="button" onClick={() => setSelectedGroups([])}>Clear</button><button type="button" onClick={() => setFilterOpen(false)}>View {visibleProducts.length} products</button></footer>
        </section>
      </div>

      <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
    </main>
  );
}
