import assert from "node:assert/strict";
import test from "node:test";

import { YafaConfig } from "../consts";
import { createYafaKnowledgeTool } from "./YafaKnowledgeTool";

const originalFetch = globalThis.fetch;
const originalUrl = YafaConfig.recommendationServiceUrl;
const originalToken = YafaConfig.internalServiceToken;

test.afterEach(() => {
    globalThis.fetch = originalFetch;
    YafaConfig.recommendationServiceUrl = originalUrl;
    YafaConfig.internalServiceToken = originalToken;
});

test("registerable tool exposes a strict query schema", () => {
    const tool = createYafaKnowledgeTool();
    assert.equal(tool.name, "consult_yafa_knowledge");
    assert.deepEqual((tool.inputSchema as { required: string[] }).required, ["query"]);
});

test("returns a grounded, bounded response from Yafa chat", async () => {
    YafaConfig.recommendationServiceUrl = "http://knowledge.test";
    YafaConfig.internalServiceToken = "a".repeat(32);
    let request: { url?: string; init?: RequestInit } = {};
    globalThis.fetch = async (input, init) => {
        request = { url: String(input), init };
        return new Response(JSON.stringify({
            intent: "brand_values_policy",
            message: "Only specified products are Vegan*.",
            grounding: [{
                product_id: "yv-brand-knowledge-001",
                chunk_type: "vegan_policy",
                content: "Verified policy content",
                trust_level: "brand_authoritative",
                requires_qualification: false,
            }],
        }), { status: 200, headers: { "Content-Type": "application/json" } });
    };

    const result = await createYafaKnowledgeTool().execute({ query: "Is everything vegan?" }) as any;
    assert.equal(result.status, "ok");
    assert.equal(result.answer, "Only specified products are Vegan*.");
    assert.equal(result.grounding[0].productId, "yv-brand-knowledge-001");
    assert.equal(request.url, "http://knowledge.test/internal/yafa/chat");
    assert.equal((request.init?.headers as Record<string, string>)["X-Yafa-Service-Token"], "a".repeat(32));
    assert.deepEqual(JSON.parse(String(request.init?.body)), { message: "Is everything vegan?" });
});

test("includes trusted product context without accepting extra input", async () => {
    YafaConfig.recommendationServiceUrl = "http://knowledge.test";
    YafaConfig.internalServiceToken = "b".repeat(32);
    let body: any;
    globalThis.fetch = async (_input, init) => {
        body = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ message: "Verified answer", grounding: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    };

    await createYafaKnowledgeTool().execute({
        query: "Is this vegan?",
        productId: "yv-lip-001",
        ignored: "must not be forwarded",
    });
    assert.deepEqual(body.page_context, { type: "product", product_id: "yv-lip-001" });
    assert.equal(body.ignored, undefined);
});

test("degrades safely when the service is unavailable", async () => {
    YafaConfig.recommendationServiceUrl = "http://knowledge.test";
    YafaConfig.internalServiceToken = "c".repeat(32);
    globalThis.fetch = async () => { throw new Error("connection detail must not leak"); };

    const result = await createYafaKnowledgeTool().execute({ query: "Tell me about this" }) as any;
    assert.equal(result.status, "unavailable");
    assert.equal(result.reason, "temporarily_unavailable");
    assert.equal(JSON.stringify(result).includes("connection detail"), false);
});

test("bounds grounding content so Nova receives valid JSON below its result limit", async () => {
    YafaConfig.recommendationServiceUrl = "http://knowledge.test";
    YafaConfig.internalServiceToken = "d".repeat(32);
    globalThis.fetch = async () => new Response(JSON.stringify({
        message: "A".repeat(5000),
        grounding: Array.from({ length: 8 }, (_, index) => ({
            product_id: `product-${index}`,
            chunk_type: "details",
            content: "C".repeat(4000),
            trust_level: "brand_authoritative",
        })),
    }), { status: 200, headers: { "Content-Type": "application/json" } });

    const result = await createYafaKnowledgeTool().execute({ query: "Tell me about it" }) as any;
    assert.equal(result.answer.length, 4000);
    assert.equal(result.grounding.length, 4);
    assert.equal(result.grounding[0].content.length, 1800);
    assert.ok(JSON.stringify(result).length < 20480);
});

test("rejects missing query without calling the service", async () => {
    let called = false;
    globalThis.fetch = async () => {
        called = true;
        return new Response();
    };
    const result = await createYafaKnowledgeTool().execute({}) as any;
    assert.equal(result.status, "invalid_request");
    assert.equal(called, false);
});
