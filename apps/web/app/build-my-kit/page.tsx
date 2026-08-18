import BuildMyKit from "./BuildMyKit";
import { getAllCatalogProducts } from "@/lib/catalog";

export default function Page() {
  return <BuildMyKit products={getAllCatalogProducts()} />;
}
