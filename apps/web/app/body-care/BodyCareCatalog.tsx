"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { BodyCareGroup, CatalogProduct } from "@/lib/catalog-types";

type BodyCareFilter = "all" | "body" | "hand-foot";
type SortOrder = "featured" | "price-asc" | "price-desc" | "name";

const collectionTabs: Array<{ value: BodyCareFilter; label: string; groups: BodyCareGroup[] }> = [
  { value: "all", label: "All", groups: [] },
  { value: "body", label: "Body", groups: ["body-moisturizers"] },
  { value: "hand-foot", label: "Hand & Foot", groups: ["hand-foot-care"] },
];

const bodyCareGroups: Array<{ value: BodyCareGroup; label: string }> = [
  { value: "body-moisturizers", label: "Body" },
  { value: "hand-foot-care", label: "Hand & Foot" },
];

const typeQueryMap: Record<string, string> = {
  "body-butter": "Body Butter",
  "hand-cream": "Hand Cream",
  "foot-cream": "Foot Cream",
};

export default function BodyCareCatalog({ products }: { products: CatalogProduct[] }) {
  const searchParams = useSearchParams();
  const [category, setCategory] = useState<BodyCareFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("featured");
  const [selectedGroups, setSelectedGroups] = useState<BodyCareGroup[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [filterOpen, setFilterOpen] = useState(false);
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);
  const requestedType = searchParams.get("type")?.toLowerCase() ?? null;
  const resolvedType = requestedType ? typeQueryMap[requestedType] : null;

  useEffect(() => {
    setCategory("all");
    setSelectedGroups([]);
    setSelectedTypes(resolvedType ? [resolvedType] : []);
  }, [resolvedType]);

  const visibleProducts = useMemo(() => {
    const activeTab = collectionTabs.find((tab) => tab.value === category)!;
    const filtered = products.filter((product) => {
      const group = product.bodyCareGroup;
      if (!group) return false;
      const matchesTab = category === "all" || activeTab.groups.includes(group);
      return matchesTab && (selectedGroups.length === 0 || selectedGroups.includes(group)) && (selectedTypes.length === 0 || selectedTypes.includes(product.productType));
    });
    if (sortOrder === "price-asc") return [...filtered].sort((a, b) => a.price - b.price);
    if (sortOrder === "price-desc") return [...filtered].sort((a, b) => b.price - a.price);
    if (sortOrder === "name") return [...filtered].sort((a, b) => a.name.localeCompare(b.name));
    return filtered;
  }, [category, products, selectedGroups, selectedTypes, sortOrder]);

  const groupCount = (group: BodyCareGroup) => products.filter((product) => product.bodyCareGroup === group).length;
  const selectCategory = (next: BodyCareFilter) => { setCategory(next); setSelectedGroups([]); setSelectedTypes([]); };

  return (
    <main id="main-content" className="bodycare-collection-page">
      <section className="collection-intro collection-intro--image collection-intro--bodycare" aria-labelledby="bodycare-title">
        <Image className="collection-intro__image" src="/images/home/campaign/hero-body-care-winter.png" alt="" fill priority sizes="100vw" />
        <div className="collection-intro__veil" aria-hidden="true" />
        <div className="collection-intro__eyebrow">The body ritual</div>
        <h1 id="bodycare-title">Care for the body, quietly.</h1>
      </section>

      <section className="collection-shop" aria-label="Body Care collection">
        <div className="collection-toolbar">
          <div className="collection-tabs" role="group" aria-label="Filter by Body Care category">
            {collectionTabs.map((item) => <button key={item.value} type="button" className={category === item.value && selectedTypes.length === 0 ? "is-active" : ""} aria-pressed={category === item.value && selectedTypes.length === 0} onClick={() => selectCategory(item.value)}>{item.label}</button>)}
          </div>
          <div className="collection-toolbar__actions">
            <button type="button" onClick={() => setFilterOpen(true)}><span aria-hidden="true">☷</span> Filter{selectedGroups.length ? ` (${selectedGroups.length})` : ""}</button>
            <label className="collection-sort"><span>Sort</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)}><option value="featured">Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name: A–Z</option></select></label>
            <p>{visibleProducts.length} {visibleProducts.length === 1 ? "product" : "products"}</p>
          </div>
        </div>
        {requestedType ? <p className="collection-status" aria-live="polite">{resolvedType ? `Showing ${resolvedType.toLowerCase()}.` : `“${requestedType}” is not a recognised category. Showing all body care.`}</p> : null}

        <div className="commerce-grid">
          {visibleProducts.map((product, index) => <div className="commerce-grid__item" key={product.id}><ProductCard product={product} onQuickShop={setQuickProduct} eager={index < 3} /></div>)}
        </div>
      </section>

      <div className={`filter-sheet${filterOpen ? " is-open" : ""}`} aria-hidden={!filterOpen}>
        <button className="filter-sheet__scrim" type="button" aria-label="Close filters" tabIndex={filterOpen ? 0 : -1} onClick={() => setFilterOpen(false)} />
        <section role="dialog" aria-modal="true" aria-labelledby="bodycare-filter-title" inert={!filterOpen}>
          <header><div><p>Filter</p><h2 id="bodycare-filter-title">Refine the collection</h2></div><button type="button" aria-label="Close filters" onClick={() => setFilterOpen(false)}>×</button></header>
          <fieldset><legend>Category</legend>{bodyCareGroups.map((group) => <label key={group.value}><input type="checkbox" checked={selectedGroups.includes(group.value)} onChange={() => setSelectedGroups((current) => current.includes(group.value) ? current.filter((item) => item !== group.value) : [...current, group.value])} /><span>{group.label} ({groupCount(group.value)})</span></label>)}</fieldset>
          <footer><button type="button" onClick={() => setSelectedGroups([])}>Clear</button><button type="button" onClick={() => setFilterOpen(false)}>View {visibleProducts.length} products</button></footer>
        </section>
      </div>

      <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
    </main>
  );
}
