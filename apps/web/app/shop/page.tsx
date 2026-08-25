import ShopCatalog from "./ShopCatalog";
import { getAllCatalogProducts } from "@/lib/catalog";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Shop Botanical Beauty",
  description: "Shop the complete YAFA VANAM collection of botanical makeup, skincare, body care and fragrance.",
  alternates: { canonical: "/shop" },
};

export default function Page() {
  return <ShopCatalog products={getAllCatalogProducts()} />;
}
