"use client";

import { useState } from "react";
import { useYafa } from "./YafaProvider";

/**
 * Product-page guidance block (Phase 3 section 30): opens the global drawer
 * with the page context pre-attached so customers never retype the product
 * name.
 */
export default function YafaProductGuidance({
  productId,
  variantId,
  shadeId,
  questions,
}: {
  productId: string;
  variantId?: string | null;
  shadeId?: string | null;
  questions: string[];
}) {
  const { openDrawer, setPageContext, send, isThinking } = useYafa();
  const [question, setQuestion] = useState("");

  const pageContext = {
    type: "product" as const,
    product_id: productId,
    variant_id: variantId ?? null,
    shade_id: shadeId ?? null,
  };

  const ask = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isThinking) return;
    setPageContext(pageContext);
    openDrawer();
    void send(trimmed, { pageContext });
  };

  return (
    <section className="ask-yafa" aria-labelledby="ask-yafa-title">
      <h2 id="ask-yafa-title">Ask YAFA</h2>
      <div className="ask-yafa__questions">
        {questions.map((suggestion) => (
          <button key={suggestion} type="button" onClick={() => ask(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>
      <form
        className="ask-yafa__free"
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
          setQuestion("");
        }}
      >
        <label className="visually-hidden" htmlFor="yafa-pdp-question">
          Ask Yafa about this product
        </label>
        <input
          id="yafa-pdp-question"
          type="text"
          maxLength={1000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask Yafa about this product…"
        />
        <button type="submit" disabled={isThinking || !question.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
