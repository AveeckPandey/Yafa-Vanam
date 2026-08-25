import type { Metadata } from "next";
import { Suspense } from "react";
import FragranceCatalog from "./FragranceCatalog";
import { getFragranceProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Fragrance Collection",
  description: "Explore twelve YAFA VANAM fragrance compositions, from botanical mists to eau de parfum and solid perfume.",
  alternates: { canonical: "/fragrance" },
};

export default function FragrancePage() {
  return <Suspense fallback={<main id="main-content" className="fragrance-collection-page" />}><FragranceCatalog products={getFragranceProducts()} /></Suspense>;
}
