"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { csrfToken } from "@/lib/csrf-client";

export type ShadeCandidate = { shade_id: string; shade_name: string; hex: string; confidence: number; reason: string };
type YafaResult = { candidates: ShadeCandidate[]; primaryRecommendation: string; quizSessionId: string };
type YafaSession = { id: string; token: string };
type YafaResultsContextValue = { result: YafaResult | null; setResult: (result: YafaResult | null) => void; startSession: () => Promise<YafaSession>; saveAnswer: (stepId: string, answer: string) => Promise<void>; uploadSelfie: (file: File) => Promise<void>; analyze: () => Promise<YafaResult>; confirmShade: (shadeID: string) => Promise<{ saved_to_profile: boolean }> };
const YafaResultsContext = createContext<YafaResultsContextValue | null>(null);

export function YafaResultsProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<YafaResult | null>(null);
  const sessionRef = useRef<YafaSession | null>(null);
  const startingRef = useRef<Promise<YafaSession> | null>(null);
  const start = useCallback(() => {
    if (sessionRef.current) return Promise.resolve(sessionRef.current);
    if (!startingRef.current) startingRef.current = csrfToken().then((token) => fetch("/api/v1/yafa/session/start", { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } })).then(async (response) => {
      const value = await response.json().catch(() => null) as { session_id?: string; session_token?: string } | null;
      if (!response.ok || !value?.session_id) throw new Error("yafa_session_failed");
      const session = { id: value.session_id, token: value.session_token || "" };
      sessionRef.current = session;
      return session;
    }).finally(() => { startingRef.current = null; });
    return startingRef.current;
  }, []);
  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const session = await start();
    const token = await csrfToken();
    const response = await fetch(`/api/v1/yafa/session/${session.id}${path}`, { ...init, credentials: "include", headers: { "X-Yafa-Session-Token": session.token, "X-CSRF-Token": token, ...(init.headers || {}) } });
    if (!response.ok) throw new Error("yafa_request_failed");
    return response;
  }, [start]);
  const saveAnswer = useCallback(async (stepId: string, answer: string) => { await request("/answer", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ step_id: stepId, answer }) }); }, [request]);
  const uploadSelfie = useCallback(async (file: File) => { const form = new FormData(); form.append("image", file); await request("/selfie", { method: "POST", body: form }); }, [request]);
  const analyze = useCallback(async () => { const response = await request("/analyze", { method: "POST" }); const value = await response.json() as { candidates?: ShadeCandidate[]; primary_recommendation?: string }; if (!Array.isArray(value.candidates) || value.candidates.length !== 3 || typeof value.primary_recommendation !== "string") throw new Error("yafa_result_failed"); const next = { candidates: value.candidates, primaryRecommendation: value.primary_recommendation, quizSessionId: (await start()).id }; setResult(next); return next; }, [request, start]);
  const confirmShade = useCallback(async (shadeID: string) => { const response = await request("/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shade_id: shadeID }) }); const value = await response.json().catch(() => null) as { saved_to_profile?: boolean } | null; if (!value) throw new Error("yafa_confirm_failed"); return { saved_to_profile: value.saved_to_profile === true }; }, [request]);
  return <YafaResultsContext.Provider value={{ result, setResult, startSession: start, saveAnswer, uploadSelfie, analyze, confirmShade }}>{children}</YafaResultsContext.Provider>;
}
export function useYafaResults() { const value = useContext(YafaResultsContext); if (!value) throw new Error("Yafa results must be used inside the Yafa results provider."); return value; }
