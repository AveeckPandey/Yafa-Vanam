import type { Metadata } from "next";
import { Suspense } from "react";
import MakeupCatalog from "./MakeupCatalog";
import { getMakeupProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Makeup Collection",
  description: "Explore YAFA VANAM complexion, eye, lip and cheek colour.",
  alternates: { canonical: "/makeup" },
};

export default function MakeupPage() {
  return <Suspense fallback={<main id="main-content" className="makeup-collection-page" />}><MakeupCatalog products={getMakeupProducts()} /></Suspense>;
}
