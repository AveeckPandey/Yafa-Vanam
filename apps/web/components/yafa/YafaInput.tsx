"use client";

import { useState } from "react";
import { useYafa } from "./YafaProvider";

const MAX_LENGTH = 1000;

export default function YafaInput() {
  const { send, isThinking, error } = useYafa();
  const [value, setValue] = useState("");

  const submit = async () => {
    const text = value.trim();
    if (!text || isThinking) return;
    setValue("");
    await send(text);
  };

  return (
    <div className="yafa-input">
      <label className="visually-hidden" htmlFor="yafa-input-field">Ask Yafa anything</label>
      <textarea
        id="yafa-input-field"
        className="yafa-input__field"
        value={value}
        rows={1}
        maxLength={MAX_LENGTH}
        placeholder="Ask a verified product question…"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void submit();
          }
        }}
      />
      <div className="yafa-input__tools">
        <button type="button" className="yafa-input__send" onClick={() => void submit()} disabled={isThinking || !value.trim()}>
          Ask Yafa
        </button>
      </div>
      {error ? <p className="yafa-input__error" role="alert">{error}</p> : null}
      <p className="yafa-input__disclaimer">Product knowledge only — not personalised recommendations or medical advice.</p>
    </div>
  );
}
