"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { CatalogProduct } from "@/lib/catalog-types";

export default function SearchExperience({ products }: { products: CatalogProduct[] }) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return products.slice(0, 6);
    return products.filter((product) => [product.name, product.category, product.subcategory, product.productType, product.benefits.join(" ")].join(" ").toLowerCase().includes(term)).slice(0, 24);
  }, [products, query]);

  return <main id="main-content" className="utility-page search-page">
    <section className="utility-page__intro"><p>YAFA VANAM / Search</p><h1>Find your next ritual.</h1><span>Search by product, category, finish or concern.</span></section>
    <section className="search-page__content" aria-label="Product search"><label htmlFor="catalogue-search">Search the collection</label><input id="catalogue-search" autoFocus type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try “foundation”, “hydration” or “berry”" />
      <p className="search-page__count" aria-live="polite">{query ? `${results.length} ${results.length === 1 ? "result" : "results"} for “${query}”` : "Popular places to begin"}</p>
      {results.length ? <div className="search-page__results">{results.map((product) => <Link key={product.id} href={`/products/${product.slug}`}><span>{product.category}</span><h2>{product.name}</h2><p>{product.shortDescription}</p><b>Explore <span aria-hidden="true">→</span></b></Link>)}</div> : <div className="search-page__empty"><h2>No matches yet.</h2><p>Try a product type, a category such as makeup or skin care, or a finish such as radiant.</p><Link href="/shop">Browse all products</Link></div>}</section>
  </main>;
}
