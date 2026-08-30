"use client";

import Image from "next/image";
import Link from "next/link";
import type { YafaMessage as YafaMessageType } from "./YafaProvider";

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
  const isUser = message.role === "user";
  const productCards = [...new Map(
    (message.grounding ?? [])
      .filter((chunk) => Boolean(chunk.product_card))
      .map((chunk) => [chunk.product_id, chunk] as const),
  ).values()].slice(0, 2);

  return (
    <article className={`yafa-message yafa-message--${message.role}`}>
      <span className="yafa-message__who">{isUser ? "You" : "Yafa"}</span>
      <div className="yafa-message__body">
        <p className="yafa-message__text">{message.text}</p>

        {message.requires ? (
          <p className="yafa-message__requires" data-testid="yafa-live-data">
            <strong>Live store check:</strong> Please check the current {LIVE_DOMAIN_LABELS[message.requires.domain] ?? message.requires.domain.replace("_", " ")} in the shop before you decide.
          </p>
        ) : null}
      </div>

      {productCards.length ? (
        <section className="yafa-product-cards" aria-label="Verified product links">
          <p className="yafa-product-cards__label">Verified product details</p>
          <div className="yafa-product-cards__grid">
            {productCards.map((chunk) => {
              const card = chunk.product_card!;
              const summary = chunk.content.replace(/\s+/g, " ").trim();
              return (
                <Link className="yafa-product-card" href={card.href} key={chunk.product_id}>
                  <span className="yafa-product-card__image">
                    <Image src={card.image} alt={card.image_alt} fill sizes="(max-width: 720px) 42vw, 12rem" />
                  </span>
                  <span className="yafa-product-card__copy">
                    <span className="yafa-product-card__type">{card.product_type}</span>
                    <strong>{card.name}</strong>
                    <span className="yafa-product-card__summary">
                      {summary.length > 135 ? `${summary.slice(0, 135)}…` : summary}
                    </span>
                    <span className="yafa-product-card__action">View product</span>
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}
    </article>
  );
}
