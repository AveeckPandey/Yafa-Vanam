"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CatalogProduct, CatalogVariant } from "@/lib/catalog-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getMakeupVariantImage, getVerifiedShadeImage } from "@/lib/makeup-variant-images";
import { usesWarmProductFrame } from "@/lib/makeup-assets";
import AddToBag from "./AddToBag";
import ProductAccordion from "./ProductAccordion";
import ProductGallery from "./ProductGallery";
import QuantitySelector from "./QuantitySelector";
import StickyBuyBar from "./StickyBuyBar";
import YafaProductGuidance from "@/components/yafa/YafaProductGuidance";
import { useAuth } from "@/components/auth/AuthProvider";
import { getConfirmedYafaProfile, type ConfirmedYafaProfile } from "@/lib/yafa-profile";
import { trackEvent } from "@/lib/analytics";
import { useYafa } from "@/components/yafa/YafaProvider";
import { getYafaProductQuestions } from "@/lib/yafa-product-questions";

function pretty(value: string) {
  return value.replaceAll("_", " ");
}

const masterShadeOrder = [
  "1C", "1N", "1W", "2C", "2N", "2W", "3C", "3N", "3W", "4N", "4W", "4O",
  "5N", "5W", "5O", "6N", "6W", "6O", "7C", "7N", "7W", "8N", "8W", "8O",
];

function titleCase(value: string | null) {
  return value ? pretty(value).replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function shadeName(shade: NonNullable<CatalogVariant["shade"]>) {
  const withoutCode = shade.name.replace(new RegExp(`^${shade.code ?? ""}\\s*`, "i"), "").trim();
  return withoutCode || [titleCase(shade.depthFamily), titleCase(shade.undertone)].filter(Boolean).join(" ");
}

function shadeSummary(shade: NonNullable<CatalogVariant["shade"]>) {
  const details = [titleCase(shade.depthFamily), titleCase(shade.undertone)].filter(Boolean).join(" · ");
  const identity = shade.code ? `${shade.code} — ${shadeName(shade)}` : shadeName(shade);
  return `${identity}${details ? ` · ${details}` : ""}`;
}

function shadeDescriptor(shade: NonNullable<CatalogVariant["shade"]>) {
  const depth = titleCase(shade.depthFamily);
  const undertone = titleCase(shade.undertone).toLowerCase();
  if (!depth || !undertone) return null;
  const tone = undertone === "cool"
    ? "soft rosy-beige"
    : undertone === "warm"
      ? "golden-beige"
      : undertone === "olive"
        ? "muted olive-golden"
        : "balanced beige";
  return `A ${depth.toLowerCase()} ${undertone} shade with ${tone} tones.`;
}

function shadeControlLabel(shade: NonNullable<CatalogVariant["shade"]>) {
  return [shade.code, shadeName(shade)].filter(Boolean).join(", ");
}

export default function ProductPageClient({
  product,
  related,
  layerMatch,
}: {
  product: CatalogProduct;
  related: CatalogProduct[];
  layerMatch: CatalogProduct | null;
}) {
  const { user } = useAuth();
  const { setPageContext, setQuickQuestions } = useYafa();
  const [quantity, setQuantity] = useState(1);
  const [variantId, setVariantId] = useState(product.defaultVariantId);
  const [yafaProfile, setYafaProfile] = useState<ConfirmedYafaProfile | null>(null);
  const variantOptions = product.variants.filter((variant) => variant.size || variant.shade);
  const selected = product.variants.find((variant) => variant.id === variantId);
  const hasShadeOptions = variantOptions.some((variant) => variant.shade);
  const orderedVariantOptions = hasShadeOptions
    ? [...variantOptions].sort((left, right) => {
        const leftIndex = masterShadeOrder.indexOf(left.shade?.code ?? "");
        const rightIndex = masterShadeOrder.indexOf(right.shade?.code ?? "");
        return (leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex) - (rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex);
      })
    : variantOptions;
  const profile = product.fragranceProfile;
  const price = selected?.price ?? product.price;
  const selectedShadeCode = selected?.shade?.code ?? null;
  const candidateShadeImage = getVerifiedShadeImage(product.id, selectedShadeCode);
  const shadeImage =
    candidateShadeImage?.shadeCode === selectedShadeCode ? candidateShadeImage : null;
  const variantImage = getMakeupVariantImage(variantId);
  const displayImage = shadeImage?.src ?? variantImage ?? product.image;
  const displayImageAlt = shadeImage
    ? `${product.imageAlt} in shade ${shadeImage.shadeCode}`
    : variantImage && selected?.shade
      ? `${product.imageAlt} in shade ${shadeName(selected.shade)}`
      : product.imageAlt;
  const yafaQuestions = useMemo(
    () => getYafaProductQuestions(product, selected?.shade ?? null),
    [product, selected?.shade],
  );

  useEffect(() => {
    trackEvent("product_viewed", { product_id: product.id, product_slug: product.slug, category: product.category });
  }, [product.category, product.id, product.slug]);
  useEffect(() => {
    if (!user) {
      setYafaProfile(null);
      return;
    }
    getConfirmedYafaProfile().then((profile) => {
      setYafaProfile(profile);
      const match = profile?.shade_code ? product.variants.find((variant) => variant.shade?.code === profile.shade_code) : undefined;
      if (match) setVariantId(match.id);
    }).catch(() => setYafaProfile(null));
  }, [product.variants, user]);
  const yafaVariantMatch = Boolean(yafaProfile?.shade_code && selected?.shade?.code === yafaProfile.shade_code);

  useEffect(() => {
    setPageContext({
      type: "product",
      product_id: product.id,
      variant_id: variantId,
      shade_id: selectedShadeCode,
    });
    setQuickQuestions(yafaQuestions);
    return () => {
      setPageContext(null);
      setQuickQuestions([]);
    };
  }, [product.id, selectedShadeCode, setPageContext, setQuickQuestions, variantId, yafaQuestions]);

  return (
    <main id="main-content" className="product-page">
      <nav className="product-page__breadcrumb" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <Link href={`/${product.category.toLowerCase().replaceAll(" ", "-")}`}>{product.category}</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{product.name}</span>
      </nav>

      <section className="pdp-hero" aria-labelledby="pdp-product-name">
        <ProductGallery
          image={displayImage}
          alt={displayImageAlt}
          className={usesWarmProductFrame(product.id) ? "pdp-gallery--warm-frame" : undefined}
        />

        <div className="pdp-sidebar">
          <section className="pdp-info">
            <p className="pdp-info__type">{product.productType}</p>
            <h1 id="pdp-product-name">{product.name}</h1>
            <p className="pdp-info__description">{product.shortDescription}</p>
            {profile ? <p className="pdp-info__family">{pretty(profile.family)}</p> : null}
            <div className="pdp-info__price">
              {formatCatalogPrice(product.currency, price)}
              {product.compareAtPrice ? <del>{formatCatalogPrice(product.currency, product.compareAtPrice)}</del> : null}
            </div>

            <div id="pdp-purchase" className="pdp-purchase">
              {variantOptions.length > 0 ? (
                <fieldset className={`pdp-shade-selector${hasShadeOptions ? " pdp-shade-selector--shades" : ""}${product.id === "yv-lip-002" ? " pdp-shade-selector--satin" : ""}`}>
                  <legend>{hasShadeOptions ? "Choose shade" : "Choose option"}</legend>
                  <div className="pdp-shade-selector__palette">
                    {orderedVariantOptions.map((variant) => {
                      const shade = variant.shade;
                      const isSelected = variantId === variant.id;
                      return (
                        <button
                          key={variant.id}
                          type="button"
                          className={isSelected ? "is-selected" : ""}
                          aria-pressed={isSelected}
                          aria-label={shade ? `Select shade ${shadeControlLabel(shade)}` : `Select ${variant.size ?? "option"}`}
                          title={shade ? shadeSummary(shade) : variant.size ?? "Option"}
                          onClick={() => {
                            setVariantId(variant.id);
                            trackEvent("variant_selected", { product_id: product.id, variant_id: variant.id, shade_code: shade?.code || null });
                          }}
                        >
                          {shade?.hex ? <i style={{ backgroundColor: shade.hex }} aria-hidden="true" /> : <span>{variant.size ?? shade?.name}</span>}
                        </button>
                      );
                    })}
                  </div>
                  {selected?.shade ? (
                    <div className="pdp-shade-preview" aria-live="polite">
                      <p>{`Selected: ${shadeSummary(selected.shade)}`}</p>
                      {shadeDescriptor(selected.shade) ? <span>{shadeDescriptor(selected.shade)}</span> : null}
                    </div>
                  ) : <p aria-live="polite">Selected: <strong>{selected?.size ?? "Standard option"}</strong></p>}
                </fieldset>
              ) : null}
              {product.includedShades.length ? (
                <section className="pdp-included-shades" aria-labelledby="included-shades-title">
                  <h2 id="included-shades-title">Included shades</h2>
                  <ul>
                    {product.includedShades.map((shade) => (
                      <li key={shade.id}>
                        {shade.hex ? <i style={{ backgroundColor: shade.hex }} aria-hidden="true" /> : null}
                        <span>{shade.name}</span>
                        {shade.finish ? <small>{titleCase(shade.finish)}</small> : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              <div className="pdp-purchase__row">
                <QuantitySelector value={quantity} onChange={setQuantity} />
                <AddToBag className="pdp-add" productId={product.id} variantId={variantId} quantity={quantity} />
              </div>
            </div>
            {yafaProfile ? <aside className="pdp-yafa-match"><span style={{ backgroundColor: yafaProfile.hex }} aria-hidden="true" /><div><strong>{yafaVariantMatch ? "Recommended for you by Yafa" : `Your Yafa match: ${yafaProfile.shade_name}`}</strong><p>{yafaVariantMatch ? `${yafaProfile.shade_name} is selected for this product.` : "This product does not currently offer your exact Yafa shade."}</p></div></aside> : null}
          </section>

          {product.ragQuestions.length > 0 ? (
            <YafaProductGuidance
              productId={product.id}
              variantId={variantId}
              shadeId={selected?.shade?.code ?? null}
              questions={yafaQuestions}
            />
          ) : null}

          <section className="pdp-details" aria-label="Product information">
            <ProductAccordion title="Details">
              <p>{product.fullDescription}</p>
              {product.benefits.length ? <ul>{product.benefits.map((benefit) => <li key={benefit}>{benefit}</li>)}</ul> : null}
            </ProductAccordion>
            <ProductAccordion title="The Ritual">
              <p>{product.usage.howToUse}</p>
              {product.usage.amount ? <p>Amount: {product.usage.amount}</p> : null}
            </ProductAccordion>
            <ProductAccordion title="Ingredients">
              {product.ingredients.fullInci ? <p>{product.ingredients.fullInci}</p> : <p>The complete ingredient list is included on the product packaging. Contact us before purchase if you need ingredient guidance.</p>}
            </ProductAccordion>
            {product.warnings.length ? (
              <ProductAccordion title="Warnings"><ul>{product.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></ProductAccordion>
            ) : null}
            <ProductAccordion title="Delivery & Returns">
              <p>Delivery timing and return eligibility are confirmed during checkout. Please review the current Shipping and Returns pages for the applicable policy.</p>
            </ProductAccordion>
          </section>
        </div>
      </section>

      {profile ? (
        <section className="scent-profile" aria-labelledby="scent-profile-title">
          <div className="scent-profile__intro">
            <div><p>Olfactive portrait</p><h2 id="scent-profile-title">Scent Profile</h2></div>
            <blockquote>{profile.scentCharacter}</blockquote>
          </div>
          <div className="scent-profile__notes">
            <article><span>Top</span><p>{profile.topNotes.join(" · ")}</p></article>
            <article><span>Heart</span><p>{profile.heartNotes.join(" · ")}</p></article>
            <article><span>Base</span><p>{profile.baseNotes.join(" · ")}</p></article>
          </div>
          <div className="scent-profile__traits">
            <article><span>Family</span><p>{pretty(profile.family)}</p></article>
            <article><span>Mood</span><p>{profile.mood.map(pretty).join(", ")}</p></article>
            <article><span>Season</span><p>{profile.season.map(pretty).join(", ")}</p></article>
            <article><span>Occasion</span><p>{profile.occasion.map(pretty).join(", ")}</p></article>
            <article><span>Intensity</span><p>Positioned as {profile.intensity}</p></article>
          </div>
        </section>
      ) : null}

      <section className="pdp-editorial" aria-label="Product story and ritual">
        <article className="pdp-story">
          <div><p>Chapter I</p><h2>The Story</h2></div>
          <div><p>{profile?.scentStory ?? product.fullDescription}</p>{profile ? <p>{product.fullDescription}</p> : null}</div>
        </article>
        <article className="pdp-ritual">
          <div><p>Chapter II</p><h2>The Ritual</h2></div>
          <div><p>{product.usage.howToUse}</p>{layerMatch ? <p>For a layered ritual, pair with {layerMatch.name} from the same {profile?.relatedScentLine} scent line.</p> : null}</div>
        </article>
      </section>

      {layerMatch ? (
        <section className="layer-scent" aria-labelledby="layer-title">
          <div><p>Complete the ritual</p><h2 id="layer-title">Layer This Scent</h2><span>Two expressions of {profile?.relatedScentLine}, each priced individually.</span></div>
          <div className="layer-scent__products">
            {[product, layerMatch].map((item, index) => (
              <div key={item.id}>
                {index ? <b aria-hidden="true">+</b> : null}
                <div><Image src={item.image} alt={item.imageAlt} fill sizes="(max-width: 760px) 46vw, 260px" /></div>
                <h3>{item.name}</h3>
                <p>{formatCatalogPrice(item.currency, item.price)}</p>
              </div>
            ))}
          </div>
          <Link href={`/products/${layerMatch.slug}`}>Explore the pairing <span aria-hidden="true">→</span></Link>
        </section>
      ) : null}

      <section className="reviews-empty" aria-labelledby="reviews-title">
        <div><p>Customer reflections</p><h2 id="reviews-title">Reviews</h2></div>
        <div><span aria-hidden="true">☆ ☆ ☆ ☆ ☆</span><h3>No reviews yet</h3><p>We are preparing verified customer reviews. In the meantime, explore the product details, ingredients and delivery information above.</p><span className="reviews-empty__coming">Reviews coming soon</span></div>
      </section>

      {related.length > 0 ? (
        <section className="related-products" aria-labelledby="related-title">
          <p>Continue exploring</p><h2 id="related-title">You May Also Like</h2>
          <div>{related.map((item) => (
            <article key={item.id}><Link href={`/products/${item.slug}`}><div><Image src={item.image} alt={item.imageAlt} fill sizes="(max-width: 640px) 46vw, 25vw" /></div><p>{item.productType}</p><h3>{item.name}</h3><strong>{formatCatalogPrice(item.currency, item.price)}</strong></Link></article>
          ))}</div>
        </section>
      ) : null}

      <StickyBuyBar name={product.name} price={price} currency={product.currency} productId={product.id} variantId={variantId} />
    </main>
  );
}
