"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { searchIndexProducts } from "@/lib/product-search";
import type { SearchIndexProduct } from "@/lib/product-search";
import { formatCatalogPrice } from "@/lib/catalog-types";

const suggestedSearches = ["Skincare", "Foundation", "Lip Color"];

export default function SearchExperience({ products }: { products: SearchIndexProduct[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(initialQuery);

  useEffect(() => {
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const results = useMemo(() => {
    if (!query.trim()) return [];
    return searchIndexProducts(products, query);
  }, [products, query]);

  const searchTerm = query.trim();

  const handleSuggestedSearch = (term: string) => {
    setQuery(term);
    router.replace(`/search?q=${encodeURIComponent(term)}`);
  };

  return (
    <main id="main-content" className="search-results-page">
      <div className="site-shell">
        <h1 className="visually-hidden">Search the YAFA VANAM collection</h1>
        <form
          className="header-search__field-row"
          role="search"
          onSubmit={(event) => event.preventDefault()}
        >
          <label className="header-search__label" htmlFor="catalogue-search">Search</label>
          <div className="header-search__field">
            <input
              id="catalogue-search"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search products, concerns, ingredients or rituals"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              enterKeyHint="search"
            />
          </div>
        </form>

        <p className="search-results-page__count" aria-live="polite">
          {query.trim()
            ? `${results.length} ${results.length === 1 ? "result" : "results"} for “${query.trim()}”`
            : "Type to search the full YAFA VANAM collection"}
        </p>

        {results.length ? (
          <ul className="header-search__results header-search__results--page">
            {results.map((product) => (
              <li key={product.id}>
                <Link className="header-search__result" href={`/products/${product.slug}`}>
                  <span className="header-search__result-media">
                    <Image src={product.image} alt="" fill sizes="(max-width: 760px) 46vw, 300px" />
                  </span>
                  <span className="header-search__result-category">{product.category}</span>
                  <span className="header-search__result-name">{product.name}</span>
                  <span className="header-search__result-benefit">{product.shortDescription}</span>
                  <span className="header-search__result-price">{formatCatalogPrice(product.currency, product.price)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="header-search__empty">
            {searchTerm ? (
              <>
                <p>Your search for &ldquo;{searchTerm}&rdquo; didn&rsquo;t return any results.</p>
                <p>Check the spelling or try a broader product, category, or shade name.</p>
                <div className="header-search__suggestions" aria-label="Suggested searches">
                  {suggestedSearches.map((term) => (
                    <button key={term} type="button" onClick={() => handleSuggestedSearch(term)}>
                      {term}
                    </button>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        )}
      </div>
    </main>
  );
}
