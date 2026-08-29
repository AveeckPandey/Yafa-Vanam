"use client";

import { useState } from "react";
import { useYafa, type YafaAttachment } from "./YafaProvider";
import YafaImageUpload from "./YafaImageUpload";
import { analyseOutfitImage, type OutfitAttributes } from "../../lib/yafa-chat";

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
  const [pendingImage, setPendingImage] = useState<{ file: File; previewUrl: string } | null>(null);
  const [imageError, setImageError] = useState("");
  const [isPreparingImage, setIsPreparingImage] = useState(false);

  const removePendingImage = () => {
    if (pendingImage) URL.revokeObjectURL(pendingImage.previewUrl);
    setPendingImage(null);
    setImageError("");
  };

  const submit = async () => {
    const text = value.trim();
    if ((!text && !pendingImage) || isThinking || isPreparingImage) return;

    if (!pendingImage) {
      setValue("");
      await send(text);
      return;
    }

    setImageError("");
    setIsPreparingImage(true);
    try {
      const attributes = await analyseOutfitImage(pendingImage.file);
      mergeProfile({
        context: { outfit: { primary_colour: attributes.primary_colour, secondary_colours: attributes.secondary_colours } },
      });
      const colours = [attributes.primary_colour, ...attributes.secondary_colours].filter(Boolean) as string[];
      const displayAttachments: YafaAttachment[] = [{ kind: "outfit", previewUrl: pendingImage.previewUrl, label: "Outfit photo" }];
      const message = text || `${colourPhrase(attributes)} Can you match my makeup to this outfit photo?`;
      setValue("");
      setPendingImage(null);
      await send(message, {
        attachment: { kind: "outfit", colours, confidence: attributes.confidence, runner_up_colour: attributes.runner_up_colour ?? null },
        displayAttachments,
      });
    } catch {
      setImageError("I couldn't read that outfit photo. Try another image or remove it and continue without one.");
    } finally {
      setIsPreparingImage(false);
    }
  };

  return (
    <div className="yafa-input">
      <label className="visually-hidden" htmlFor="yafa-input-field">
        Ask Yafa anything
      </label>
      {pendingImage ? (
        <div className="yafa-input__image-preview">
          {/* eslint-disable-next-line @next/next/no-img-element -- temporary local object URL */}
          <img src={pendingImage.previewUrl} alt="Selected outfit preview" />
          <div>
            <strong>{isPreparingImage ? "Checking outfit photo" : "Outfit photo ready"}</strong>
            <span>{isPreparingImage ? "Yafa is reading the image before replying." : "It will be included with your next message."}</span>
          </div>
          <button type="button" onClick={removePendingImage} aria-label="Remove uploaded image" disabled={isPreparingImage}>×</button>
        </div>
      ) : null}
      <textarea
        id="yafa-input-field"
        className="yafa-input__field"
        value={value}
        rows={2}
        maxLength={MAX_LENGTH}
        placeholder="Ask about products or the look you're planning…"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void submit();
          }
        }}
      />
      <div className="yafa-input__tools">
        <YafaImageUpload
          onError={setImageError}
          disabled={isThinking || isPreparingImage}
          onImageSelected={(file, previewUrl) => {
            if (pendingImage) URL.revokeObjectURL(pendingImage.previewUrl);
            setPendingImage({ file, previewUrl });
            setImageError("");
          }}
        />
        <button
          type="button"
          className="yafa-input__send"
          onClick={() => void submit()}
          disabled={isThinking || isPreparingImage || (!value.trim() && !pendingImage)}
        >
          Send
        </button>
      </div>
      {imageError || error ? (
        <p className="yafa-input__error" role="alert">
          {imageError || error}
        </p>
      ) : null}
    </div>
  );
}
