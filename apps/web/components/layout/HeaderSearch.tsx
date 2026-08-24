"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { trackEvent } from "@/lib/analytics";
import type { SearchIndexProduct } from "@/lib/product-search";
import { HEADER_SEARCH_LIMIT, searchIndexProducts } from "@/lib/product-search";
import { formatCatalogPrice } from "@/lib/catalog-types";

const suggestedSearches = ["Skincare", "Foundation", "Lip Color"];

// The index is tiny (one lightweight entry per product) and identical for
// every visitor, so it is fetched once per session and filtered locally —
// results appear on every keystroke with no network round-trip.
let indexPromise: Promise<SearchIndexProduct[]> | null = null;

function loadSearchIndex() {
  // A failed fetch clears itself so the next time the panel opens it retries.
  indexPromise ??= fetch("/api/search", { cache: "no-store" })
    .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Search unavailable"))))
    .then((data: { products: SearchIndexProduct[] }) => data.products)
    .catch((error) => {
      indexPromise = null;
      throw error;
    });
  return indexPromise;
}

type HeaderSearchProps = {
  open: boolean;
  onClose: () => void;
};

export default function HeaderSearch({ open, onClose }: HeaderSearchProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const firstResultRef = useRef<HTMLAnchorElement>(null);
  const [products, setProducts] = useState<SearchIndexProduct[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [query, setQuery] = useState("");
  // Screen readers hear the count once typing settles instead of per keystroke.
  const [announcedTerm, setAnnouncedTerm] = useState("");

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setLoadFailed(false);
    trackEvent("search_opened");
    loadSearchIndex()
      .then(setProducts)
      .catch(() => setLoadFailed(true));
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    const timer = window.setTimeout(() => setAnnouncedTerm(query.trim()), 400);
    return () => window.clearTimeout(timer);
  }, [query]);

  const results = useMemo(
    () => searchIndexProducts(products ?? [], query),
    [products, query],
  );
  const visibleResults = results.slice(0, HEADER_SEARCH_LIMIT);
  const searchTerm = query.trim();
  const hasQuery = Boolean(searchTerm);

  const announcedResults = useMemo(
    () => searchIndexProducts(products ?? [], announcedTerm),
    [products, announcedTerm],
  );

  const handleSearch = useCallback((term: string) => {
    const trimmed = term.trim();
    // Always route on submit: the /search page renders a proper empty state,
    // so pressing Enter with zero matches still gives visible feedback.
    if (!trimmed) return;
    trackEvent("search_performed", { query: trimmed, result_count: results.length });
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }, [results.length, router]);

  const handleClear = useCallback(() => {
    setQuery("");
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const handleSuggestedSearch = useCallback((term: string) => {
    setQuery(term);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const stopPanelEvent = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && visibleResults.length) {
      event.preventDefault();
      firstResultRef.current?.focus();
    }
  };

  if (!open) return null;

  return (
    <div className="header-search-layer">
      <button
        className="header-search-layer__backdrop"
        type="button"
        onClick={onClose}
        aria-label="Close search"
      />
      <section
        className="header-search"
        id="header-search-panel"
        role="region"
        aria-label="Site search"
        onPointerDown={stopPanelEvent}
        onClick={stopPanelEvent}
      >
        <div className="site-shell header-search__inner">
          <form
            className="header-search__field-row"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              event.stopPropagation();
              handleSearch(query);
            }}
            onPointerDown={stopPanelEvent}
            onClick={stopPanelEvent}
          >
            <div className="header-search__field">
              <label className="header-search__label" htmlFor="header-search-input">Search</label>
              <input
                id="header-search-input"
                ref={inputRef}
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="Search products, concerns, ingredients or rituals"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                enterKeyHint="search"
                onPointerDown={stopPanelEvent}
                onClick={stopPanelEvent}
              />
              {query ? (
                <button
                  className="header-search__clear"
                  type="button"
                  aria-label="Clear search text"
                  onPointerDown={stopPanelEvent}
                  onClick={(event) => {
                    stopPanelEvent(event);
                    handleClear();
                  }}
                >
                  Clear
                </button>
              ) : null}
            </div>
            <button
              className="header-search__close"
              type="button"
              aria-label="Close search"
              onPointerDown={stopPanelEvent}
              onClick={(event) => {
                stopPanelEvent(event);
                onClose();
              }}
            >
              <span aria-hidden="true">×</span>
            </button>
          </form>

        <p className="visually-hidden" role="status">
          {!hasQuery
            ? ""
            : loadFailed
              ? "Search is unavailable right now"
              : !products
                ? "Loading products"
                : `${announcedResults.length} ${announcedResults.length === 1 ? "result" : "results"} for ${announcedTerm}`}
        </p>

        {hasQuery && loadFailed ? (
          <div className="header-search__empty">
            <p>Search is unavailable right now.</p>
          </div>
        ) : hasQuery && products && !results.length ? (
          <div className="header-search__empty">
            <p>Your search for &ldquo;{searchTerm}&rdquo; didn&rsquo;t return any results.</p>
            <p>Check the spelling or try a broader product, category, or shade name.</p>
            <div className="header-search__suggestions" aria-label="Suggested searches">
              {suggestedSearches.map((term) => (
                <button
                  key={term}
                  type="button"
                  onPointerDown={stopPanelEvent}
                  onClick={(event) => {
                    stopPanelEvent(event);
                    handleSuggestedSearch(term);
                  }}
                >
                  {term}
                </button>
              ))}
            </div>
          </div>
        ) : hasQuery && results.length ? (
          <>
            <ul className="header-search__results">
              {visibleResults.map((product, index) => (
                <li key={product.id}>
                  <Link
                    className="header-search__result"
                    href={`/products/${product.slug}`}
                    ref={index === 0 ? firstResultRef : undefined}
                    onPointerDown={stopPanelEvent}
                    onClick={stopPanelEvent}
                  >
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
            <Link
              className="header-search__view-all"
              href={`/search?q=${encodeURIComponent(searchTerm)}`}
              onPointerDown={stopPanelEvent}
              onClick={(event) => {
                stopPanelEvent(event);
                trackEvent("search_performed", { query: searchTerm, result_count: results.length });
              }}
            >
              See all results for &ldquo;{searchTerm}&rdquo;
            </Link>
          </>
        ) : null}
        </div>
      </section>
    </div>
  );
}
