"use client";

import { useState } from "react";
import type { YafaMessage as YafaMessageType } from "./YafaProvider";
import YafaRecommendationCard from "./YafaRecommendationCard";

const LIVE_DOMAIN_LABELS: Record<string, string> = {
  inventory: "live stock",
  price: "current pricing",
  order_status: "your order status",
  cart: "your bag",
  reviews: "customer reviews",
  ratings: "ratings",
  shipping: "shipping",
};

export default function YafaMessage({ message }: { message: YafaMessageType }) {
  const [showGrounding, setShowGrounding] = useState(false);
  const isUser = message.role === "user";

  return (
    <article className={`yafa-message yafa-message--${message.role}`}>
      <span className="yafa-message__who">{isUser ? "You" : "Yafa"}</span>
      <div className="yafa-message__body">
        {message.attachments?.length ? (
          <div className="yafa-message__attachments">
            {message.attachments.map((attachment) => (
              // eslint-disable-next-line @next/next/no-img-element -- local object-URL preview
              <img
                key={attachment.previewUrl}
                src={attachment.previewUrl}
                alt={attachment.label ?? "Uploaded image"}
                className="yafa-message__image"
              />
            ))}
          </div>
        ) : null}
        <p className="yafa-message__text">{message.text}</p>

        {message.requires ? (
          <p className="yafa-message__requires" data-testid="yafa-live-data">
            This needs {LIVE_DOMAIN_LABELS[message.requires.domain] ?? message.requires.domain.replace("_", " ")} —
            check the shop page for the live answer.
          </p>
        ) : null}

        {message.recommendations?.length ? (
          <div className="yafa-message__recommendations">
            {message.recommendations.map((recommendation) => (
              <YafaRecommendationCard
                key={`${recommendation.product_id}-${recommendation.variant_id ?? "base"}`}
                recommendation={recommendation}
              />
            ))}
          </div>
        ) : null}

        {message.grounding?.length ? (
          <div className="yafa-message__grounding">
            <button
              type="button"
              className="yafa-grounding__toggle"
              aria-expanded={showGrounding}
              onClick={() => setShowGrounding((open) => !open)}
            >
              {showGrounding ? "Hide sources" : "Where this comes from"}
            </button>
            {showGrounding ? (
              <ul>
                {message.grounding.map((chunk, index) => (
                  <li key={`${chunk.product_id}-${chunk.chunk_type}-${index}`}>
                    <strong>{chunk.chunk_type.replace(/_/g, " ")}</strong> · trust:{" "}
                    {chunk.trust_level.toLowerCase().replace(/_/g, " ")}
                    {chunk.requires_qualification ? " · needs verification" : ""}
                    <br />
                    {chunk.content.length > 220 ? `${chunk.content.slice(0, 220)}…` : chunk.content}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
