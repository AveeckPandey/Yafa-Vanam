import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ProductPageClient from "@/components/product/ProductPageClient";
import { getAllCatalogProducts, getProductBySlug, getRelatedProducts } from "@/lib/catalog";
import { absoluteUrl } from "@/lib/seo";
import { getSampleReviews } from "@/lib/sample-reviews";

export function generateStaticParams() {
  return getAllCatalogProducts().map((product) => ({ slug: product.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) return {};
  return {
    title: product.name,
    description: product.shortDescription,
    alternates: { canonical: `/products/${product.slug}` },
    openGraph: {
      type: "website",
      url: `/products/${product.slug}`,
      title: product.name,
      description: product.shortDescription,
      images: [{ url: product.image, alt: product.imageAlt }],
    },
    twitter: { card: "summary_large_image", title: product.name, description: product.shortDescription, images: [product.image] },
  };
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
  const sampleReviews = process.env.SHOW_SAMPLE_REVIEWS === "true" ? getSampleReviews(product) : [];
  const defaultVariant = product.variants.find((variant) => variant.id === product.defaultVariantId);
  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.fullDescription || product.shortDescription,
    image: [product.image, ...product.gallery].map((image) => absoluteUrl(image)),
    sku: product.id,
    brand: { "@type": "Brand", name: "YAFA VANAM" },
    offers: {
      "@type": "Offer",
      url: absoluteUrl(`/products/${product.slug}`),
      priceCurrency: product.currency,
      price: defaultVariant?.price ?? product.price,
    },
  };
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl() },
      { "@type": "ListItem", position: 2, name: product.category, item: absoluteUrl(`/${product.category.toLowerCase().replaceAll(" ", "-")}`) },
      { "@type": "ListItem", position: 3, name: product.name, item: absoluteUrl(`/products/${product.slug}`) },
    ],
  };
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
    <ProductPageClient product={product} related={related} layerMatch={layerMatch} sampleReviews={sampleReviews} />
  </>;
}
