"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { trackEvent } from "../../lib/analytics";
import {
  sendYafaMessage,
  type YafaChatResponse,
  type YafaChatRequestAttachment,
  type YafaPageContext,
  type YafaProfilePayload,
} from "../../lib/yafa-chat";

export type YafaRole = "user" | "yafa";

/** Client-side only: local preview URL for an uploaded image (never sent upstream). */
export type YafaAttachment = {
  kind: "outfit" | "selfie" | "reference";
  previewUrl: string;
  label?: string;
};

export type YafaMessage = {
  id: string;
  role: YafaRole;
  text: string;
  recommendations?: YafaChatResponse["recommendations"];
  grounding?: YafaChatResponse["grounding"];
  requires?: YafaChatResponse["requires"];
  attachments?: YafaAttachment[];
};

type YafaContextValue = {
  isOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  messages: YafaMessage[];
  isThinking: boolean;
  error: string | null;
  pageContext: YafaPageContext | null;
  setPageContext: (context: YafaPageContext | null) => void;
  profile: YafaProfilePayload;
  mergeProfile: (patch: YafaProfilePayload) => void;
  shadeResult: ShadeResultSummary | null;
  setShadeResult: (result: ShadeResultSummary | null) => void;
  send: (
    text: string,
    overrides?: {
      pageContext?: YafaPageContext | null;
      profile?: YafaProfilePayload;
      attachment?: YafaChatRequestAttachment | null;
      displayAttachments?: YafaAttachment[];
    },
  ) => Promise<void>;
};

export type ShadeResultSummary = {
  candidates: Array<{ code: string; name?: string | null; confidence: number }>;
  depthFamily?: string | null;
  undertone?: string | null;
  source: "selfie" | "manual";
};

const YafaContext = createContext<YafaContextValue | null>(null);

let messageCounter = 0;
const nextMessageId = () => `yafa-msg-${++messageCounter}`;

export function YafaProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<YafaMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageContext, setPageContext] = useState<YafaPageContext | null>(null);
  const [profile, setProfile] = useState<YafaProfilePayload>({});
  const [shadeResult, setShadeResult] = useState<ShadeResultSummary | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const openDrawer = useCallback(() => {
    setIsOpen(true);
    trackEvent("yafa_opened");
  }, []);
  const closeDrawer = useCallback(() => setIsOpen(false), []);
  const toggleDrawer = useCallback(() => setIsOpen((open) => !open), []);

  const mergeProfile = useCallback((patch: YafaProfilePayload) => {
    setProfile((current) => deepMerge(current, patch));
  }, []);

  const pushMessage = useCallback((message: YafaMessage) => {
    setMessages((current) => [...current, message]);
  }, []);

  const send = useCallback(
    async (
      text: string,
      overrides?: {
        pageContext?: YafaPageContext | null;
        profile?: YafaProfilePayload;
        attachment?: YafaChatRequestAttachment | null;
        displayAttachments?: YafaAttachment[];
      },
    ) => {
      const trimmed = text.trim();
      if (!trimmed || isThinking) return;
      setError(null);
      pushMessage({
        id: nextMessageId(),
        role: "user",
        text: trimmed,
        attachments: overrides?.displayAttachments,
      });
      setIsThinking(true);
      trackEvent("yafa_message_sent", {
        page_type: (overrides?.pageContext ?? pageContext)?.type ?? "global",
      });
      try {
        // Page context updates with navigation (spec Phase 3 section 32) while
        // conversation state persists inside the orchestrator.
        const effectiveContext =
          overrides?.pageContext !== undefined ? overrides.pageContext : pageContext;
        const response = await sendYafaMessage({
          message: trimmed,
          conversationId: conversationIdRef.current,
          pageContext: effectiveContext,
          profile: overrides?.profile ?? profile,
          attachment: overrides?.attachment ?? null,
        });
        conversationIdRef.current = response.conversation_id;
        pushMessage({
          id: nextMessageId(),
          role: "yafa",
          text: response.message,
          recommendations: response.recommendations.length
            ? response.recommendations
            : undefined,
          grounding: response.grounding.length ? response.grounding : undefined,
          requires: response.requires,
        });
      } catch {
        setError("Yafa is unavailable right now. Please try again in a moment.");
      } finally {
        setIsThinking(false);
      }
    },
    [isThinking, pageContext, profile, pushMessage],
  );

  const value = useMemo<YafaContextValue>(
    () => ({
      isOpen,
      openDrawer,
      closeDrawer,
      toggleDrawer,
      messages,
      isThinking,
      error,
      pageContext,
      setPageContext,
      profile,
      mergeProfile,
      shadeResult,
      setShadeResult,
      send,
    }),
    [
      isOpen,
      openDrawer,
      closeDrawer,
      toggleDrawer,
      messages,
      isThinking,
      error,
      pageContext,
      profile,
      mergeProfile,
      shadeResult,
      send,
    ],
  );

  return <YafaContext.Provider value={value}>{children}</YafaContext.Provider>;
}

export function useYafa(): YafaContextValue {
  const context = useContext(YafaContext);
  if (!context) throw new Error("useYafa must be used inside YafaProvider");
  return context;
}

function deepMerge(base: YafaProfilePayload, patch: YafaProfilePayload): YafaProfilePayload {
  const result: YafaProfilePayload = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    if (
      value && typeof value === "object" && !Array.isArray(value) &&
      result[key] && typeof result[key] === "object" && !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(
        result[key] as YafaProfilePayload,
        value as YafaProfilePayload,
      );
    } else if (value !== undefined) {
      result[key] = value;
    }
  }
  return result;
}
