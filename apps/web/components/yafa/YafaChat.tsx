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
  const { messages, isThinking, send, quickQuestions } = useYafa();
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, isThinking]);

  if (messages.length === 0) {
    return (
      <div className="yafa-drawer__empty">
        <section className="yafa-drawer__welcome" aria-labelledby="yafa-welcome-title">
          <span>YOUR RITUAL, CLARIFIED</span>
          <h3 id="yafa-welcome-title">Beauty knowledge on your terms.</h3>
          <p>Ask about a YAFA VANAM product&apos;s verified ingredients, scent, usage, warnings, or brand policies.</p>
        </section>
        <aside className="yafa-drawer__notice" aria-label="Yafa chat information">
          <p>
            Yafa uses this chat to retrieve relevant YAFA VANAM product knowledge. Please don&apos;t share personal or health information. Product guidance is not medical advice.
          </p>
        </aside>
        <p className="yafa-drawer__suggestion-label">Try a verified question</p>
        <YafaSuggestedQuestions questions={quickQuestions} />
      </div>
    );
  }

  return (
    <div className="yafa-drawer__messages" aria-live="polite">
      {messages.map((message) => (
        <YafaMessage key={message.id} message={message} />
      ))}
      {isThinking ? (
        <div className="yafa-thinking" role="status" aria-label="Yafa is checking verified product details">
          <span>Yafa is checking verified details</span>
          <span className="yafa-thinking__dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </div>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
