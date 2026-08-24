"use client";

import { useEffect, useState } from "react";
import { fetchLiveProductCard, type LiveProductCardData } from "../../lib/yafa-chat";
import type { YafaRecommendation } from "../../lib/yafa-chat";

const REASON_PHRASES: Record<string, string> = {
  warm_undertone_match: "Warm undertone match",
  cool_undertone_match: "Cool undertone match",
  neutral_undertone_match: "Neutral undertone match",
  olive_undertone_match: "Olive undertone match",
  complexion_depth_contrast_match: "Suits your depth",
  complexion_depth_intensity_tuned: "Intensity tuned to your depth",
  requested_finish_or_product_match: "Matches your finish",
  desired_intensity_match: "Right intensity",
  skin_type_best_for: "Great for your skin type",
  skin_type_compatible: "Works with your skin type",
  concern_primary_match: "Targets your concern",
  goal_direct_match: "Supports your goal",
  routine_step_time_fit: "Fits your routine step",
  brow_hair_depth_temperature_match: "Matches hair colour",
  mascara_default_neutral_tone: "Everyday definition",
  eyeliner_neutral_default: "Versatile neutral",
};

/**
 * Live product card (Phase 3 sections 37-40): identity from the canonical
 * catalogue, explanation from reason codes, price/stock from the Go API,
 * Add to Bag validated by Go.
 */
export default function YafaRecommendationCard({
  recommendation,
}: {
  recommendation: YafaRecommendation;
}) {
  const [live, setLive] = useState<LiveProductCardData | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLiveProductCard(recommendation.product_id)
      .then((data) => {
        if (!cancelled) setLive(data);
      })
      .catch(() => {
        if (!cancelled) setLive(null);
      });
    return () => {
      cancelled = true;
    };
  }, [recommendation.product_id]);

  const matchLabel =
    recommendation.score >= 0.75
      ? "Strong Match"
      : recommendation.score >= 0.55
        ? "Good Match"
        : "Alternative";

  return (
    <div className="yafa-card">
      <div className="yafa-card__main">
        {live?.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- remote catalogue image with fixed dimensions
          <img src={live.image} alt="" width={56} height={56} className="yafa-card__thumb" />
        ) : null}
        <div>
          <p className="yafa-card__name">{recommendation.product_name ?? live?.name ?? recommendation.product_id}</p>
          <p className="yafa-card__shade">
            {recommendation.shade_name ?? ""}
            {recommendation.shade_hex ? (
              <i style={{ backgroundColor: recommendation.shade_hex }} aria-hidden="true" />
            ) : null}
          </p>
          <p className="yafa-card__price" data-testid="yafa-card-price">
            {live?.live ? (
              typeof live.price === "number" ? (
                <>
                  ₹{(live.price / 100).toFixed(0)}{" "}
                  <span className={live.in_stock ? "in-stock" : "out-of-stock"}>
                    {live.in_stock ? "In stock" : "Out of stock"}
                  </span>
                </>
              ) : (
                "See product for price"
              )
            ) : (
              "Checking live price…"
            )}
          </p>
        </div>
        <span className={`yafa-card__match yafa-card__match--${matchLabel.toLowerCase().replace(" ", "-")}`}>
          {matchLabel}
        </span>
      </div>

      {recommendation.reason_codes.length ? (
        <details className="yafa-card__why">
          <summary>Why Yafa picked it</summary>
          <ul>
            {recommendation.reason_codes.slice(0, 4).map((code) => (
              <li key={code}>{REASON_PHRASES[code] ?? code.replace(/_/g, " ")}</li>
            ))}
          </ul>
        </details>
      ) : null}

      <a className="yafa-card__view" href={`/products/${live?.slug ?? ""}`}>
        View Product
      </a>
    </div>
  );
}
