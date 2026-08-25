import type { Metadata } from "next";
import { Suspense } from "react";
import SearchExperience from "./SearchExperience";
import { getSearchIndex } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false, follow: true },
};

export default function Page() {
  return (
    <Suspense fallback={<main id="main-content" className="search-results-page"><h1 className="visually-hidden">Search the YAFA VANAM collection</h1></main>}>
      <SearchExperience products={getSearchIndex()} />
    </Suspense>
  );
}
