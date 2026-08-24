"use client";

import { useYafa } from "./YafaProvider";

const DEFAULT_QUESTIONS = [
  "What does this smell like?",
  "Where does this fit in a routine?",
  "Would this work for an evening event?",
  "Build me a full look for a wedding",
];

/**
 * Suggested-question chips (Phase 3 section 30). Clicking one sends it
 * immediately with the current page context attached.
 */
export default function YafaSuggestedQuestions({
  questions,
}: {
  questions?: string[];
}) {
  const { send, isThinking } = useYafa();
  const items = questions?.length ? questions : DEFAULT_QUESTIONS;

  return (
    <div className="yafa-suggested" role="list">
      {items.map((question) => (
        <button
          key={question}
          type="button"
          role="listitem"
          disabled={isThinking}
          onClick={() => void send(question)}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
