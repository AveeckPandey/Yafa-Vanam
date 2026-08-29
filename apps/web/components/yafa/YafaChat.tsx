"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
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
        <p>
          Hi, I&apos;m Yafa. Ask me about any product, your shade, or the look
          you&apos;re planning — voice and photos work too.
        </p>
        <div className="yafa-drawer__journeys" aria-label="Start with Yafa">
          <Link href="/yafa">Find my shade</Link>
          <button type="button" disabled={isThinking} onClick={() => void send("Help me build a simple beauty routine")}>Build a routine</button>
          <button type="button" disabled={isThinking} onClick={() => void send("Can you match my makeup to an outfit?")}>Match an outfit</button>
        </div>
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
        <p className="yafa-thinking" role="status">
          Yafa is thinking…
        </p>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
