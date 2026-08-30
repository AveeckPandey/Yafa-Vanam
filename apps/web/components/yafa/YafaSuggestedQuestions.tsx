"use client";

import { useYafa } from "./YafaProvider";

const DEFAULT_QUESTIONS = [
  "What does Forest Rain Body Mist smell like?",
  "How do I use Leafwell Hydra Balance Gel?",
  "What warnings should I know before using Calmpath Soothing Serum?",
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
          disabled={isThinking}
          onClick={() => void send(question)}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
