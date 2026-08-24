"use client";

import { useRef, useState } from "react";
import { useYafa, type YafaAttachment } from "./YafaProvider";
import YafaMicrophone from "./YafaMicrophone";
import YafaImageUpload from "./YafaImageUpload";
import type { OutfitAttributes } from "../../lib/yafa-chat";

const MAX_LENGTH = 1000;

function colourPhrase(attributes: OutfitAttributes): string {
  const primary = (attributes.primary_colour ?? "").replace(/_/g, " ");
  const runnerUp = (attributes.runner_up_colour ?? "").replace(/_/g, " ");
  if (!primary) return "";
  // Low confidence must stay honest, never invent a certain colour.
  if (runnerUp && (attributes.confidence ?? 1) < 0.75) {
    return `This looks ${primary} to me, but if it's ${runnerUp} I can adjust the recommendation.`;
  }
  return `I'm wearing ${primary}${attributes.secondary_colours.length ? ` with ${attributes.secondary_colours.join(" and ")}` : ""}.`;
}

export default function YafaInput() {
  const { send, isThinking, mergeProfile, error } = useYafa();
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const submit = () => {
    const text = value.trim();
    if (!text || isThinking) return;
    setValue("");
    void send(text);
  };

  return (
    <div className="yafa-input">
      <label className="visually-hidden" htmlFor="yafa-input-field">
        Ask Yafa anything
      </label>
      <textarea
        id="yafa-input-field"
        ref={textareaRef}
        className="yafa-input__field"
        value={value}
        rows={2}
        maxLength={MAX_LENGTH}
        placeholder="Ask about products, shades, or the look you're planning…"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <div className="yafa-input__tools">
        <YafaMicrophone
          disabled={isThinking}
          onTranscript={(text) => {
            // Transcript is EDITABLE before sending (spec section 26).
            setValue((current) => (current ? `${current} ${text}` : text).slice(0, MAX_LENGTH));
            textareaRef.current?.focus();
          }}
        />
        <YafaImageUpload
          onError={() => undefined}
          onOutfitAttributes={(attributes, previewUrl: string) => {
            mergeProfile({
              context: {
                outfit: {
                  primary_colour: attributes.primary_colour,
                  secondary_colours: attributes.secondary_colours,
                },
              },
            });
            const colours = [attributes.primary_colour, ...attributes.secondary_colours].filter(
              Boolean,
            ) as string[];
            // The uploaded image stays visible in the user bubble; the derived
            // colours travel to the orchestrator as attachment metadata.
            const displayAttachments: YafaAttachment[] = previewUrl
              ? [{ kind: "outfit", previewUrl, label: "Outfit" }]
              : [];
            void send(
              `${colourPhrase(attributes)} Can you match my makeup to this outfit photo?`,
              {
                attachment: {
                  kind: "outfit",
                  colours,
                  confidence: attributes.confidence,
                  runner_up_colour: attributes.runner_up_colour ?? null,
                },
                displayAttachments,
              },
            );
          }}
        />
        <button
          type="button"
          className="yafa-input__send"
          onClick={submit}
          disabled={isThinking || !value.trim()}
        >
          Send
        </button>
      </div>
      {error ? (
        <p className="yafa-input__error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
