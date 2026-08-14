import type { Metadata } from "next";
import MakeupCatalog from "./MakeupCatalog";
import { getMakeupProducts } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Makeup Collection | YAFA VANAM",
  description: "Explore YAFA VANAM complexion, eye, lip and cheek colour.",
};

export default function MakeupPage() {
  return <MakeupCatalog products={getMakeupProducts()} />;
}
