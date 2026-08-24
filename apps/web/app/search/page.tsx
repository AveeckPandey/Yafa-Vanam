import type { Metadata } from "next";
import { Suspense } from "react";
import SearchExperience from "./SearchExperience";
import { getSearchIndex } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Search | YAFA VANAM",
};

export default function Page() {
  return (
    <Suspense fallback={<main id="main-content" className="search-results-page" />}>
      <SearchExperience products={getSearchIndex()} />
    </Suspense>
  );
}
