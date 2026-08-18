import ShopCatalog from "./ShopCatalog";
import { getAllCatalogProducts } from "@/lib/catalog";

export default function Page() {
  return <ShopCatalog products={getAllCatalogProducts()} />;
}
