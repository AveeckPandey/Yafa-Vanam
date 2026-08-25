import type { Metadata } from "next";
import { Suspense } from "react";
import SkinCareCatalog from "./SkinCareCatalog";
import { getSkincareProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Skin Care Collection",
  description: "Explore YAFA VANAM essentials for cleansing, treating, hydrating, protecting and scalp care.",
  alternates: { canonical: "/skincare" },
};

export default function SkinCarePage() {
  return <Suspense fallback={<main id="main-content" className="skincare-collection-page" />}><SkinCareCatalog products={getSkincareProducts()} /></Suspense>;
}
