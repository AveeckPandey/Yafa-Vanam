import BuildMyKit from "./BuildMyKit";
import { getAllCatalogProducts } from "@/lib/catalog";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Build My Kit",
  description: "Create a considered YAFA VANAM beauty kit around your preferences, routine and mood.",
  alternates: { canonical: "/build-my-kit" },
};

export default function Page() {
  return <BuildMyKit products={getAllCatalogProducts()} />;
}
