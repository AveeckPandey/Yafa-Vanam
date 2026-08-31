"use client";

import { useEffect, useState } from "react";
import type { SampleReview } from "@/lib/sample-reviews";

type PublicReview = {
  id: string;
  rating: number;
  title: string;
  body: string;
  display_name: string;
  is_verified_purchase: boolean;
};

export default function ProductReviews({ productId, samples }: { productId: string; samples: SampleReview[] }) {
  const [reviews, setReviews] = useState<PublicReview[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/v1/products/${encodeURIComponent(productId)}/reviews?limit=20`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => response.ok ? response.json() : null)
      .then((payload: { items?: PublicReview[] } | null) => setReviews(payload?.items ?? []))
      .catch(() => undefined)
      .finally(() => setLoaded(true));
    return () => controller.abort();
  }, [productId]);

  if (reviews.length === 0 && samples.length === 0) {
    return (
      <section className="reviews-empty" aria-labelledby="reviews-title">
        <div><p>Customer reflections</p><h2 id="reviews-title">Reviews</h2></div>
        <div><span aria-hidden="true">☆ ☆ ☆ ☆ ☆</span><h3>{loaded ? "No reviews yet" : "Loading reviews"}</h3><p>Verified customer reviews will appear here after purchase and moderation.</p><span className="reviews-empty__coming">Reviews coming soon</span></div>
      </section>
    );
  }

  if (reviews.length > 0) {
    return (
      <section className="product-reviews" aria-labelledby="reviews-title">
        <header><p>Customer reflections</p><h2 id="reviews-title">Reviews</h2><span>Published after purchase verification and moderation.</span></header>
        <div className="product-reviews__grid">
          {reviews.map((review) => (
            <article key={review.id}>
              {review.is_verified_purchase ? <span className="product-reviews__verified">Verified purchase</span> : null}
              <div aria-label={`${review.rating} out of 5 stars`}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div>
              <h3>{review.title}</h3><p>{review.body}</p><footer>{review.display_name}</footer>
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="product-reviews" aria-labelledby="reviews-title">
      <header>
        <p>Customer reflections</p>
        <h2 id="reviews-title">Review preview</h2>
        <strong>Demo content</strong>
        <span>These are clearly labeled layout samples, not customer testimonials. They are excluded from ratings and production SEO.</span>
      </header>
      <div className="product-reviews__grid">
        {samples.map((review) => (
          <article key={review.id}>
            <span className="product-reviews__sample">Sample review</span>
            <div aria-label={`${review.rating} out of 5 stars`}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div>
            <h3>{review.title}</h3>
            <p>{review.body}</p>
            <footer>{review.displayName} · Illustrative only</footer>
          </article>
        ))}
      </div>
    </section>
  );
}
