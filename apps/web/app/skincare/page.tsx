import type { Metadata } from "next";
import SkinCareCatalog from "./SkinCareCatalog";
import { getSkincareProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Skin Care Collection | YAFA VANAM",
  description: "Explore YAFA VANAM essentials for cleansing, treating, hydrating, protecting and scalp care.",
};

export default function SkinCarePage() {
  return <SkinCareCatalog products={getSkincareProducts()} />;
}
