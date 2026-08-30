"use client";

/**
 * Browser-side contract for the Yafa orchestrator (Phase 2 section 36).
 * All calls go through server proxies: the service token and vector database
 * credentials never reach the browser.
 */

export type YafaPageContext = {
  type: "global" | "product" | "category" | "cart" | "account";
  product_id?: string | null;
  variant_id?: string | null;
  shade_id?: string | null;
};

export type YafaGroundingChunk = {
  product_id: string;
  chunk_type: string;
  content: string;
  similarity: number;
  trust_level: string;
  requires_qualification: boolean;
  product_card?: {
    name: string;
    product_type: string;
    image: string;
    image_alt: string;
    href: string;
  };
};

export type YafaLiveRequirement = {
  domain: string;
  product_id?: string | null;
};

export type YafaChatResponse = {
  conversation_id: string;
  intent: string;
  message: string;
  requires: YafaLiveRequirement | null;
  grounding: YafaGroundingChunk[];
  citation_required_topics: string[];
  medical_escalation_topics: string[];
};

export async function sendYafaMessage(input: {
  message: string;
  conversationId: string | null;
  pageContext: YafaPageContext | null;
}): Promise<YafaChatResponse> {
  const response = await fetch("/api/yafa/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      conversation_id: input.conversationId,
      user_id: null,
      message: input.message,
      page_context: input.pageContext ?? { type: "global" },
    }),
  });
  if (!response.ok) {
    throw new Error(`yafa_chat_failed_${response.status}`);
  }
  return (await response.json()) as YafaChatResponse;
}
