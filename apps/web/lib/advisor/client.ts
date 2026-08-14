import type { AdvisorSession } from "./types";

const BASE = process.env.NEXT_PUBLIC_ADVISOR_URL || "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Advisor request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const advisorApi = {
  create: (goal?: string) => json<AdvisorSession>("/advisor/session", { method: "POST", body: JSON.stringify({ goal: goal || null }) }),
  answer: (id: string, question_id: string, answer: unknown) => json<AdvisorSession>(`/advisor/session/${id}/answer`, { method: "POST", body: JSON.stringify({ question_id, answer }) }),
  recommend: (id: string) => json<AdvisorSession>(`/advisor/session/${id}/recommend`, { method: "POST", body: "{}" }),
  modify: (id: string, changes: Record<string, unknown>) => json<AdvisorSession>(`/advisor/session/${id}/modify`, { method: "POST", body: JSON.stringify({ changes }) }),
  explain: (id: string, product_id: string, variant_id?: string | null) => json<{answer: string}>(`/advisor/session/${id}/explain`, { method: "POST", body: JSON.stringify({ product_id, variant_id: variant_id || null, question: "Why did you recommend this?" }) }),
  analyzeImage: async (id: string, kind: "selfie" | "outfit", image_base64: string) => json<{status: string; message: string}>(`/advisor/session/${id}/image-analysis`, { method: "POST", body: JSON.stringify({ kind, image_base64 }) }),
};
