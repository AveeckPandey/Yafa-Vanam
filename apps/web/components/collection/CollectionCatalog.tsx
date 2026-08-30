"use client";

import { Fragment, useState, type ReactNode } from "react";
import Link from "next/link";
import ProductCard from "@/components/product/ProductCard";
import QuickShop from "@/components/product/QuickShop";
import type { CatalogProduct } from "@/lib/catalog-types";

export type CollectionSortOrder = "featured" | "price-asc" | "price-desc" | "name";

export function sortProducts(products: CatalogProduct[], sortOrder: CollectionSortOrder): CatalogProduct[] {
  if (sortOrder === "price-asc") return [...products].sort((a, b) => a.price - b.price);
  if (sortOrder === "price-desc") return [...products].sort((a, b) => b.price - a.price);
  if (sortOrder === "name") return [...products].sort((a, b) => a.name.localeCompare(b.name));
  return products;
}

// Shared chrome for the fragrance / skincare / body-care catalogs: intro,
// toolbar, sort, filter sheet, grid and quick-shop. Callers own filtering,
// query-param resolution, and pass everything variable as props.
export default function CollectionCatalog({
  pageClass,
  titleId,
  eyebrow,
  title,
  tagline,
  shopLabel,
  tabsLabel,
  tabs,
  activeTab,
  onSelectTab,
  tabClearsHighlight,
  filterLegend,
  facets,
  selectedFacets,
  facetCounts,
  onToggleFacet,
  onClearFacets,
  status,
  results,
  sortOrder,
  onSortChange,
  tiles = [],
  trailingTile,
}: {
  pageClass: string;
  titleId: string;
  eyebrow: string;
  title: ReactNode;
  tagline: string;
  shopLabel: string;
  tabsLabel: string;
  tabs: Array<{ value: string; label: string }>;
  activeTab: string;
  onSelectTab: (value: string) => void;
  /** Skincare/body-care deactivate the tab highlight while sheet facets are selected; fragrance does not. */
  tabClearsHighlight?: boolean;
  filterLegend: string;
  facets: Array<{ value: string; label: string }>;
  selectedFacets: string[];
  facetCounts?: Record<string, number>;
  onToggleFacet: (value: string) => void;
  onClearFacets: () => void;
  status: ReactNode;
  results: CatalogProduct[];
  sortOrder: CollectionSortOrder;
  onSortChange: (value: CollectionSortOrder) => void;
  /** Editorial/kit tiles rendered inline inside the grid item at position `at`. */
  tiles?: Array<{ at: number; node: ReactNode }>;
  trailingTile?: ReactNode;
}) {
  const [filterOpen, setFilterOpen] = useState(false);
  const [quickProduct, setQuickProduct] = useState<CatalogProduct | null>(null);
  const tabActive = (value: string) => activeTab === value && !(tabClearsHighlight && selectedFacets.length > 0);

  return (
    <main id="main-content" className={pageClass}>
      <section className="collection-intro" aria-labelledby={titleId}>
        <div className="collection-intro__eyebrow">{eyebrow}</div>
        <h1 id={titleId}>{title}</h1>
        <p>{tagline}</p>
      </section>

      <section className="collection-shop" aria-label={shopLabel}>
        <div className="collection-toolbar">
          <div className="collection-tabs" role="group" aria-label={tabsLabel}>
            {tabs.map((item) => <button key={item.value} type="button" className={tabActive(item.value) ? "is-active" : ""} aria-pressed={tabActive(item.value)} onClick={() => onSelectTab(item.value)}>{item.label}</button>)}
          </div>
          <div className="collection-toolbar__actions">
            <button type="button" onClick={() => setFilterOpen(true)}><span aria-hidden="true">☷</span> Filter{selectedFacets.length ? ` (${selectedFacets.length})` : ""}</button>
            <label className="collection-sort"><span>Sort</span><select value={sortOrder} onChange={(event) => onSortChange(event.target.value as CollectionSortOrder)}><option value="featured">Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name: A–Z</option></select></label>
            <p>{results.length} {results.length === 1 ? "product" : "products"}</p>
          </div>
        </div>
        {status}

        <div className="commerce-grid">
          {results.map((product, index) => (
            <div className="commerce-grid__item" key={product.id}>
              {tiles.filter((tile) => tile.at === index).map((tile) => <Fragment key={tile.at}>{tile.node}</Fragment>)}
              <ProductCard product={product} onQuickShop={setQuickProduct} eager={index < 3} />
            </div>
          ))}
          {trailingTile ? <div className="commerce-grid__item">{trailingTile}</div> : null}
        </div>
      </section>

      <div className={`filter-sheet${filterOpen ? " is-open" : ""}`} aria-hidden={!filterOpen}>
        <button className="filter-sheet__scrim" type="button" aria-label="Close filters" tabIndex={filterOpen ? 0 : -1} onClick={() => setFilterOpen(false)} />
        <section role="dialog" aria-modal="true" aria-labelledby={`${titleId}-filter`} inert={!filterOpen}>
          <header><div><p>Filter</p><h2 id={`${titleId}-filter`}>Refine the collection</h2></div><button type="button" aria-label="Close filters" onClick={() => setFilterOpen(false)}>×</button></header>
          <fieldset><legend>{filterLegend}</legend>{facets.map((facet) => <label key={facet.value}><input type="checkbox" checked={selectedFacets.includes(facet.value)} onChange={() => onToggleFacet(facet.value)} /><span>{facetCounts ? `${facet.label} (${facetCounts[facet.value] ?? 0})` : facet.label}</span></label>)}</fieldset>
          <footer><button type="button" onClick={onClearFacets}>Clear</button><button type="button" onClick={() => setFilterOpen(false)}>View {results.length} products</button></footer>
        </section>
      </div>

      <QuickShop product={quickProduct} onClose={() => setQuickProduct(null)} />
    </main>
  );
}
