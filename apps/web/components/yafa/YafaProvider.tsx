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
  type YafaPageContext,
} from "../../lib/yafa-chat";

export type YafaRole = "user" | "yafa";

export type YafaMessage = {
  id: string;
  role: YafaRole;
  text: string;
  grounding?: YafaChatResponse["grounding"];
  requires?: YafaChatResponse["requires"];
};

type YafaContextValue = {
  isOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  messages: YafaMessage[];
  isThinking: boolean;
  error: string | null;
  quickQuestions: string[];
  setQuickQuestions: (questions: string[]) => void;
  pageContext: YafaPageContext | null;
  setPageContext: (context: YafaPageContext | null) => void;
  resetConversation: () => void;
  send: (
    text: string,
    overrides?: {
      pageContext?: YafaPageContext | null;
    },
  ) => Promise<void>;
};

const YafaContext = createContext<YafaContextValue | null>(null);

let messageCounter = 0;
const nextMessageId = () => `yafa-msg-${++messageCounter}`;

export function YafaProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<YafaMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quickQuestions, setQuickQuestions] = useState<string[]>([]);
  const [pageContext, setPageContext] = useState<YafaPageContext | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const openDrawer = useCallback(() => {
    setIsOpen(true);
    trackEvent("yafa_opened");
  }, []);
  const closeDrawer = useCallback(() => setIsOpen(false), []);
  const toggleDrawer = useCallback(() => setIsOpen((open) => !open), []);

  const resetConversation = useCallback(() => {
    conversationIdRef.current = null;
    setMessages([]);
    setError(null);
  }, []);

  const pushMessage = useCallback((message: YafaMessage) => {
    setMessages((current) => [...current, message]);
  }, []);

  const send = useCallback(
    async (
      text: string,
      overrides?: {
        pageContext?: YafaPageContext | null;
      },
    ) => {
      const trimmed = text.trim();
      if (!trimmed || isThinking) return;
      setError(null);
      pushMessage({
        id: nextMessageId(),
        role: "user",
        text: trimmed,
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
        });
        conversationIdRef.current = response.conversation_id;
        pushMessage({
          id: nextMessageId(),
          role: "yafa",
          text: response.message,
          grounding: response.grounding.length ? response.grounding : undefined,
          requires: response.requires,
        });
      } catch {
        setError("Yafa is unavailable right now. Please try again in a moment.");
      } finally {
        setIsThinking(false);
      }
    },
    [isThinking, pageContext, pushMessage],
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
      quickQuestions,
      setQuickQuestions,
      pageContext,
      setPageContext,
      resetConversation,
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
      quickQuestions,
      pageContext,
      resetConversation,
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
