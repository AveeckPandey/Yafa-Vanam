import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ProductPageClient from "@/components/product/ProductPageClient";
import { getAllCatalogProducts, getProductBySlug, getRelatedProducts } from "@/lib/catalog";

export function generateStaticParams() {
  return getAllCatalogProducts().map((product) => ({ slug: product.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) return {};
  return { title: `${product.name} | YAFA VANAM`, description: product.shortDescription };
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) notFound();
  const isMist = product.productType.includes("Mist");
  const layerMatch = product.fragranceProfile?.relatedScentLine
    ? getAllCatalogProducts().find((candidate) =>
        candidate.id !== product.id
        && candidate.fragranceProfile?.relatedScentLine === product.fragranceProfile?.relatedScentLine
        && (isMist ? !candidate.productType.includes("Mist") : candidate.productType.includes("Mist")),
      ) ?? null
    : null;
  const related = getRelatedProducts(product, 5).filter((candidate) => candidate.id !== layerMatch?.id).slice(0, 4);
  return <ProductPageClient product={product} related={related} layerMatch={layerMatch} />;
}
