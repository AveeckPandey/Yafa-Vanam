import type { Metadata } from "next";
import { Suspense } from "react";
import BodyCareCatalog from "./BodyCareCatalog";
import { getBodyCareProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Body Care Collection",
  description: "Explore YAFA VANAM body essentials for hands, feet and skin.",
  alternates: { canonical: "/body-care" },
};

export default function BodyCarePage() {
  return <Suspense fallback={<main id="main-content" className="bodycare-collection-page" />}><BodyCareCatalog products={getBodyCareProducts()} /></Suspense>;
}
