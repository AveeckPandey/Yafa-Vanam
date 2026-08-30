import type { MetadataRoute } from "next";
import { getAllCatalogProducts } from "@/lib/catalog";
import { SITE_URL } from "@/lib/seo";

const publicRoutes = [
  "", "/shop", "/makeup", "/skincare", "/body-care", "/fragrance",
  "/about", "/contact", "/faq", "/shipping", "/returns", "/privacy-policy", "/terms", "/accessibility", "/cookie-policy",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...publicRoutes.map((path) => ({
      url: `${SITE_URL}${path || "/"}`,
      changeFrequency: path === "" ? "weekly" as const : "monthly" as const,
      priority: path === "" ? 1 : 0.7,
    })),
    ...getAllCatalogProducts().map((product) => ({
      url: `${SITE_URL}/products/${product.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
  ];
}
