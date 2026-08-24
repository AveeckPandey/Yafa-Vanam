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

export type YafaRecommendation = {
  product_id: string;
  variant_id?: string | null;
  category: string;
  score: number;
  reason_codes: string[];
  warnings: string[];
  product_name?: string | null;
  color_family?: string | null;
  shade_name?: string | null;
  shade_hex?: string | null;
  source_file?: string | null;
  commerce_validation_required?: boolean;
};

export type YafaGroundingChunk = {
  product_id: string;
  chunk_type: string;
  content: string;
  similarity: number;
  trust_level: string;
  requires_qualification: boolean;
};

export type YafaLiveRequirement = {
  domain: string;
  product_id?: string | null;
};

export type YafaChatResponse = {
  conversation_id: string;
  intent: string;
  message: string;
  recommendations: YafaRecommendation[];
  requires: YafaLiveRequirement | null;
  grounding: YafaGroundingChunk[];
  citation_required_topics: string[];
  medical_escalation_topics: string[];
};

export type YafaChatRequestAttachment = {
  kind: "outfit" | "selfie" | "reference";
  colours?: string[];
  confidence?: number;
  runner_up_colour?: string | null;
};

export type YafaProfilePayload = Record<string, unknown>;

export async function sendYafaMessage(input: {
  message: string;
  conversationId: string | null;
  pageContext: YafaPageContext | null;
  profile?: YafaProfilePayload;
  attachment?: YafaChatRequestAttachment | null;
}): Promise<YafaChatResponse> {
  const response = await fetch("/api/yafa/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      conversation_id: input.conversationId,
      user_id: null,
      message: input.message,
      page_context: input.pageContext ?? { type: "global" },
      profile: input.profile ?? {},
      attachment: input.attachment ?? undefined,
    }),
  });
  if (!response.ok) {
    throw new Error(`yafa_chat_failed_${response.status}`);
  }
  return (await response.json()) as YafaChatResponse;
}

export type OutfitAttributes = {
  primary_colour: string | null;
  runner_up_colour?: string | null;
  secondary_colours: string[];
  colour_families: string[];
  style: string | null;
  pattern: boolean;
  confidence: number;
};

/** Outfit photo -> structured attributes ONLY (Phase 3 section 18). */
export async function analyseOutfitImage(file: File): Promise<OutfitAttributes> {
  const form = new FormData();
  form.append("image", file);
  const response = await fetch("/api/yafa/vision/outfit", { method: "POST", body: form });
  if (!response.ok) throw new Error(`outfit_analysis_failed_${response.status}`);
  return (await response.json()) as OutfitAttributes;
}

export type TranscriptionResult = { text: string; language: string | null; duration_ms: number };

/**
 * Speech -> text via Browser -> Next proxy -> Go API -> self-hosted
 * Faster-Whisper (EC2). The browser never contacts the Whisper host directly;
 * Go injects WHISPER_INTERNAL_TOKEN server-side.
 */
export async function transcribeAudio(blob: Blob): Promise<TranscriptionResult> {
  const form = new FormData();
  form.append("audio", blob, "speech.webm");
  const response = await fetch("/api/v1/yafa/transcribe", { method: "POST", body: form });
  if (!response.ok) throw new Error(`transcribe_failed_${response.status}`);
  return (await response.json()) as TranscriptionResult;
}

export type LiveProductCardData = {
  id: string;
  slug: string;
  name: string;
  image?: string | null;
  live: boolean;
  currency?: string;
  price?: number | null;
  in_stock?: boolean;
};

/** Current price/stock from the Go commerce backend (never static JSON). */
export async function fetchLiveProductCard(productId: string): Promise<LiveProductCardData> {
  const response = await fetch(`/api/yafa/product-card?id=${encodeURIComponent(productId)}`);
  if (!response.ok) throw new Error(`product_card_failed_${response.status}`);
  return (await response.json()) as LiveProductCardData;
}
