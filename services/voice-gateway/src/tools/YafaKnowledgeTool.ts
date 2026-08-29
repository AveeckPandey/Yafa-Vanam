import { YafaConfig } from "../consts";
import type { Tool } from "./Tool";

type KnowledgeParams = {
    query?: unknown;
    productId?: unknown;
};

type Grounding = {
    product_id?: string;
    chunk_type?: string;
    content?: string;
    trust_level?: string;
    requires_qualification?: boolean;
};

type YafaChatResponse = {
    intent?: string;
    message?: string;
    grounding?: Grounding[];
    citation_required_topics?: string[];
    medical_escalation_topics?: string[];
    requires?: { domain?: string; product_id?: string | null } | null;
};

function cleanOptionalString(value: unknown, maxLength: number): string | undefined {
    if (typeof value !== "string") return undefined;
    const cleaned = value.trim();
    return cleaned ? cleaned.slice(0, maxLength) : undefined;
}

function unavailableResult(reason: "not_configured" | "temporarily_unavailable") {
    return {
        status: "unavailable",
        reason,
        answer: "I can still help with your preferences, but I can't verify that product detail right now.",
        grounding: [],
    };
}

export function createYafaKnowledgeTool(): Tool {
    return {
        name: "consult_yafa_knowledge",
        description:
            "Retrieve verified YAFA VANAM product, ingredient, usage, safety, vegan, cruelty-free, charity, and brand-policy information. Use this for factual YAFA VANAM questions. Do not use it for greetings or casual conversation. Never use semantic result order as a product recommendation ranking.",
        inputSchema: {
            type: "object",
            additionalProperties: false,
            properties: {
                query: {
                    type: "string",
                    minLength: 1,
                    maxLength: 1000,
                    description: "The customer's complete factual question in their own words.",
                },
                productId: {
                    type: "string",
                    minLength: 1,
                    maxLength: 128,
                    description: "Optional canonical product ID when it is already present in trusted session context.",
                },
            },
            required: ["query"],
        },
        async execute(params: unknown): Promise<unknown> {
            const parsed = (params && typeof params === "object" ? params : {}) as KnowledgeParams;
            const query = cleanOptionalString(parsed.query, 1000);
            const productId = cleanOptionalString(parsed.productId, 128);
            if (!query) {
                return {
                    status: "invalid_request",
                    answer: "Please ask a complete YAFA VANAM product or policy question.",
                    grounding: [],
                };
            }

            if (!YafaConfig.recommendationServiceUrl || !YafaConfig.internalServiceToken) {
                return unavailableResult("not_configured");
            }

            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), YafaConfig.knowledgeTimeoutMs);
            try {
                const response = await fetch(
                    `${YafaConfig.recommendationServiceUrl}/internal/yafa/chat`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-Yafa-Service-Token": YafaConfig.internalServiceToken,
                        },
                        body: JSON.stringify({
                            message: query,
                            ...(productId
                                ? { page_context: { type: "product", product_id: productId } }
                                : {}),
                        }),
                        signal: controller.signal,
                    },
                );

                if (!response.ok) return unavailableResult("temporarily_unavailable");
                const payload = (await response.json()) as YafaChatResponse;
                const answer = cleanOptionalString(payload.message, 4000);
                if (!answer) return unavailableResult("temporarily_unavailable");

                return {
                    status: "ok",
                    intent: payload.intent || "product_information",
                    answer,
                    grounding: (payload.grounding || []).slice(0, 4).map((chunk) => ({
                        productId: chunk.product_id,
                        type: chunk.chunk_type,
                        content: cleanOptionalString(chunk.content, 1800),
                        trustLevel: chunk.trust_level,
                        requiresQualification: Boolean(chunk.requires_qualification),
                    })),
                    citationRequiredTopics: payload.citation_required_topics || [],
                    medicalEscalationTopics: payload.medical_escalation_topics || [],
                    requiresLiveData: payload.requires || null,
                };
            } catch {
                return unavailableResult("temporarily_unavailable");
            } finally {
                clearTimeout(timeout);
            }
        },
    };
}
