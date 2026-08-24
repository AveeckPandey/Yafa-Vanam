"use client";

import { useRef, useState } from "react";
import { analyseOutfitImage, type OutfitAttributes } from "../../lib/yafa-chat";

/**
 * Image upload for the Yafa drawer (Phase 3 sections 18-20, 35):
 * outfit photos -> structured colour attributes fed into the profile.
 * The local preview URL is handed to the caller so the image can be shown
 * inside the chat thread; the file itself is never persisted.
 */
export default function YafaImageUpload({
  onOutfitAttributes,
  onError,
}: {
  onOutfitAttributes: (attributes: OutfitAttributes, previewUrl: string) => void;
  onError: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);

  const handleFile = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      onError("Please choose an image file.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      onError("That image is too large — please keep it under 8 MB.");
      return;
    }
    setBusy(true);
    // Local preview for the chat bubble; revoked implicitly on page unload.
    const previewUrl = URL.createObjectURL(file);
    try {
      const attributes = await analyseOutfitImage(file);
      onOutfitAttributes(attributes, previewUrl);
    } catch {
      URL.revokeObjectURL(previewUrl);
      onError("I couldn't read that outfit photo. Try another one?");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <button
        type="button"
        className="yafa-image-upload__button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        aria-label="Upload an outfit photo so Yafa can match colours"
        title="Upload an outfit photo"
      >
        {busy ? "…" : "👗"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="visually-hidden-input"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void handleFile(file);
        }}
      />
    </>
  );
}
