"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { CatalogProduct } from "@/lib/catalog-types";
import { formatCatalogPrice } from "@/lib/catalog-types";
import { getMakeupVariantImage } from "@/lib/makeup-variant-images";
import AddToBag from "./AddToBag";
import AskYafa from "./AskYafa";
import ProductAccordion from "./ProductAccordion";
import ProductGallery from "./ProductGallery";
import QuantitySelector from "./QuantitySelector";
import StickyBuyBar from "./StickyBuyBar";

function pretty(value: string) {
  return value.replaceAll("_", " ");
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
  const [quantity, setQuantity] = useState(1);
  const [variantId, setVariantId] = useState(product.defaultVariantId);
  const variantOptions = product.variants.filter((variant) => variant.size || variant.shade);
  const selected = product.variants.find((variant) => variant.id === variantId);
  const profile = product.fragranceProfile;
  const price = selected?.price ?? product.price;
  const selectedImage = getMakeupVariantImage(product.id, variantId);
  const galleryImages = selectedImage
    ? [selectedImage, ...product.gallery.filter((image) => image !== selectedImage)]
    : product.gallery;

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
        <ProductGallery key={product.id} images={galleryImages} selectedImage={selectedImage} alt={product.imageAlt} />

        <div className="pdp-sidebar">
          <section className="pdp-info">
            <p className="pdp-info__type">{product.productType}</p>
            <h1 id="pdp-product-name">{product.name}</h1>
            {profile ? <p className="pdp-info__family">{pretty(profile.family)}</p> : null}
            <div className="pdp-info__price">
              {formatCatalogPrice(product.currency, price)}
              {product.compareAtPrice ? <del>{formatCatalogPrice(product.currency, product.compareAtPrice)}</del> : null}
            </div>
            <p className="pdp-info__description">{product.shortDescription}</p>

            <div id="pdp-purchase" className="pdp-purchase">
              {variantOptions.length > 0 ? (
                <fieldset className="pdp-shade-selector">
                  <legend>{variantOptions.some((variant) => variant.shade) ? "Choose shade" : "Choose option"}</legend>
                  <div>{variantOptions.map((variant) => <button key={variant.id} type="button" className={variantId === variant.id ? "is-selected" : ""} aria-pressed={variantId === variant.id} aria-label={`Select ${variant.shade?.name ?? variant.size ?? "option"}`} onClick={() => setVariantId(variant.id)}>{variant.shade?.hex ? <i style={{ backgroundColor: variant.shade.hex }} aria-hidden="true" /> : null}<span>{variant.size ?? variant.shade?.name}</span></button>)}</div>
                  <p aria-live="polite">Selected: <strong>{selected?.shade?.name ?? selected?.size ?? "Default option"}</strong></p>
                </fieldset>
              ) : null}
              <div className="pdp-purchase__row">
                <QuantitySelector value={quantity} onChange={setQuantity} />
                <AddToBag className="pdp-add" productId={product.id} variantId={variantId} quantity={quantity} />
              </div>
            </div>
          </section>

          {product.ragQuestions.length > 0 ? <AskYafa productId={product.id} questions={product.ragQuestions} /> : null}

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
              {product.ingredients.fullInci ? <p>{product.ingredients.fullInci}</p> : <p>Final ingredient list will be published with the approved production formula.</p>}
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
        <div><span aria-hidden="true">☆ ☆ ☆ ☆ ☆</span><h3>No reviews yet</h3><p>Be the first to review this product when verified customer reviews become available.</p><button type="button" disabled>Write a review</button></div>
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
