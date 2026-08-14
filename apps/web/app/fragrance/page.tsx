import type { Metadata } from "next";
import FragranceCatalog from "./FragranceCatalog";
import { getFragranceProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Fragrance Collection | YAFA VANAM",
  description: "Explore twelve YAFA VANAM fragrance compositions, from botanical mists to eau de parfum and solid perfume.",
};

export default function FragrancePage() {
  return <FragranceCatalog products={getFragranceProducts()} />;
}
