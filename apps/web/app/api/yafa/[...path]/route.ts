import { NextRequest, NextResponse } from "next/server";
import { getProductById } from "@/lib/catalog";

/**
 * Server-only bridge to the internal RAG service used by Yafa chat.
 * (Phase 2 section 35 / Phase 3 section 41). The service token never reaches
 * the browser: it lives in this route's environment alone.
 */
const yafaRagBase = () => (process.env.YAFA_RAG_URL || "").replace(/\/$/, "");
const serviceToken = () => process.env.YAFA_INTERNAL_SERVICE_TOKEN || "";

type ChatGrounding = { product_id?: unknown; [key: string]: unknown };
type ChatPayload = { grounding?: ChatGrounding[]; [key: string]: unknown };

function attachProductCards(payload: ChatPayload): ChatPayload {
  if (!Array.isArray(payload.grounding)) return payload;
  return {
    ...payload,
    grounding: payload.grounding.map((chunk) => {
      if (typeof chunk.product_id !== "string") return chunk;
      const product = getProductById(chunk.product_id);
      if (!product) return chunk;
      return {
        ...chunk,
        // This is a catalogue link for the already-retrieved product, never
        // a personalised recommendation or an unverified commerce answer.
        product_card: {
          name: product.name,
          product_type: product.productType,
          image: product.image,
          image_alt: product.imageAlt,
          href: `/products/${product.slug}`,
        },
      };
    }),
  };
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const base = yafaRagBase();
  if (!base) {
    return NextResponse.json({ error: "Yafa service is not configured." }, { status: 503 });
  }
  const token = serviceToken();
  if (!token) {
    return NextResponse.json({ error: "Yafa service authentication is not configured." }, { status: 503 });
  }

  const { path } = await context.params;
  if (path.length !== 1 || path[0] !== "chat") {
    return NextResponse.json({ error: "Yafa RAG endpoint not found." }, { status: 404 });
  }
  const contentType = request.headers.get("content-type");
  try {
    const upstream = await fetch(`${base}/internal/yafa/${path.map(encodeURIComponent).join("/")}`, {
      method: request.method,
      headers: {
        "x-yafa-service-token": token,
        ...(contentType ? { "content-type": contentType } : {}),
      },
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "cache-control"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    if (upstream.ok && path[0] === "chat" && upstream.headers.get("content-type")?.includes("application/json")) {
      const payload = await upstream.json() as ChatPayload;
      return NextResponse.json(attachProductCards(payload), { status: upstream.status, headers: responseHeaders });
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return NextResponse.json({ error: "Yafa service is temporarily unavailable." }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
