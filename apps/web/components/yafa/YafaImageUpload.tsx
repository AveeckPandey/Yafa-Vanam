"use client";

import { useRef } from "react";

/**
 * Selects an outfit image for the chat composer. Analysis is deliberately
 * deferred until send so the shopper can inspect or remove the preview first.
 */
export default function YafaImageUpload({
  onImageSelected,
  onError,
  disabled = false,
}: {
  onImageSelected: (file: File, previewUrl: string) => void;
  onError: (message: string) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const handleFile = (file: File) => {
    if (!file.type.startsWith("image/")) {
      onError("Please choose an image file.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      onError("That image is too large — please keep it under 8 MB.");
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    onImageSelected(file, previewUrl);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <>
      <button
        type="button"
        className="yafa-image-upload__button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        aria-label="Add an outfit photo"
        title="Add an outfit photo"
      >
        Add image
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
