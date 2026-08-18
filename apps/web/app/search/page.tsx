import SearchExperience from "./SearchExperience";
import { getAllCatalogProducts } from "@/lib/catalog";

export default function Page() {
  return <SearchExperience products={getAllCatalogProducts()} />;
}
