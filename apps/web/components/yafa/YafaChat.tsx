"use client";

import { useEffect, useRef } from "react";
import { useYafa } from "./YafaProvider";
import YafaMessage from "./YafaMessage";
import YafaSuggestedQuestions from "./YafaSuggestedQuestions";

/**
 * Scrollable conversation transcript (Phase 3 section 29). Reads shared state
 * from YafaProvider so navigation never resets the chat.
 */
export default function YafaChat() {
  const { messages, isThinking } = useYafa();
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, isThinking]);

  if (messages.length === 0) {
    return (
      <div className="yafa-drawer__empty">
        <p>
          Hi, I&apos;m Yafa. Ask me about any product, your shade, or the look
          you&apos;re planning — voice and photos work too.
        </p>
        <YafaSuggestedQuestions />
      </div>
    );
  }

  return (
    <div className="yafa-drawer__messages" aria-live="polite">
      {messages.map((message) => (
        <YafaMessage key={message.id} message={message} />
      ))}
      {isThinking ? (
        <p className="yafa-thinking" role="status">
          Yafa is thinking…
        </p>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
