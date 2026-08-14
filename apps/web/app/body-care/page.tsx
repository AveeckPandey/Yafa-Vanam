import type { Metadata } from "next";
import BodyCareCatalog from "./BodyCareCatalog";
import { getBodyCareProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Body Care Collection | YAFA VANAM",
  description: "Explore YAFA VANAM body essentials for hands, feet and skin.",
};

export default function BodyCarePage() {
  return <BodyCareCatalog products={getBodyCareProducts()} />;
}
