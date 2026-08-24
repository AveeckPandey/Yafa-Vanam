import { NextRequest, NextResponse } from "next/server";
import { getProductById } from "@/lib/catalog";

/**
 * Live commerce card data for Yafa recommendation cards (Phase 3 section 39):
 * identity from the canonical catalogue, price/stock ALWAYS fetched live from
 * the Go API - never from static JSON.
 */
const commerceBase = () =>
  (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const productId = request.nextUrl.searchParams.get("id");
  if (!productId) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }

  const catalogueProduct = getProductById(productId);
  if (!catalogueProduct) {
    return NextResponse.json({ error: "unknown_product" }, { status: 404 });
  }

  const base = commerceBase();
  if (!base) {
    return NextResponse.json({
      id: catalogueProduct.id,
      slug: catalogueProduct.slug,
      name: catalogueProduct.name,
      image: catalogueProduct.image,
      live: false,
    });
  }

  try {
    const upstream = await fetch(`${base}/api/v1/products/${catalogueProduct.slug}`, {
      cache: "no-store",
    });
    if (!upstream.ok) throw new Error(String(upstream.status));
    const product = (await upstream.json()) as {
      variants?: Array<{ price?: number; is_active?: boolean; stock?: number | null }>;
      price?: number;
      currency?: string;
    };
    const variants = (product.variants || []).filter((variant) => variant.is_active !== false);
    const prices = variants
      .map((variant) => variant.price ?? product.price)
      .filter((price): price is number => typeof price === "number");
    const inStock = variants.some(
      (variant) => variant.stock === null || variant.stock === undefined || variant.stock > 0,
    );
    return NextResponse.json({
      id: catalogueProduct.id,
      slug: catalogueProduct.slug,
      name: catalogueProduct.name,
      image: catalogueProduct.image,
      live: true,
      currency: product.currency || "INR",
      price: prices.length ? Math.min(...prices) : null,
      in_stock: inStock && variants.length > 0,
    });
  } catch {
    return NextResponse.json(
      { id: catalogueProduct.id, slug: catalogueProduct.slug, name: catalogueProduct.name, image: catalogueProduct.image, live: false },
      { status: 200 },
    );
  }
}
