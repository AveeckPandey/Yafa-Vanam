"use client";

import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../../lib/yafa-chat";
import { trackEvent } from "../../lib/analytics";

export type MicState =
  | "idle"
  | "requesting_permission"
  | "recording"
  | "uploading"
  | "transcribing"
  | "ready"
  | "error";

const STATE_LABELS: Record<MicState, string> = {
  idle: "Ask Yafa with your voice",
  requesting_permission: "Allow microphone access…",
  recording: "Recording — tap stop when done",
  uploading: "Sending audio…",
  transcribing: "Transcribing…",
  ready: "Transcript ready",
  error: "Voice input problem",
};

type ErrorKind = "permission_denied" | "no_microphone" | "unsupported" | "backend" | null;

/**
 * Voice input (Browser MediaRecorder -> Next proxy -> Go API -> Faster-Whisper).
 * Raw audio lives in memory only; nothing is persisted. Transcript lands in
 * the composer EDITABLE before sending.
 */
export default function YafaMicrophone({
  onTranscript,
  disabled,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const [state, setState] = useState<MicState>("idle");
  const [errorKind, setErrorKind] = useState<ErrorKind>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const readyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (readyTimerRef.current) clearTimeout(readyTimerRef.current);
    };
  }, []);

  const fail = (kind: Exclude<ErrorKind, null>) => {
    setErrorKind(kind);
    setState("error");
  };

  const start = async () => {
    if (disabled) return;
    setErrorKind(null);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      fail("unsupported");
      return;
    }

    setState("requesting_permission");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      const name = (error as DOMException)?.name;
      if (name === "NotAllowedError" || name === "SecurityError") fail("permission_denied");
      else if (name === "NotFoundError" || name === "OverconstrainedError") fail("no_microphone");
      else fail("backend");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];
    try {
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];
        if (blob.size === 0) {
          setState("idle");
          return;
        }
        setState("uploading");
        try {
          // Once handed to fetch, the local blob is unreferenced and dropped.
          setState("transcribing");
          const result = await transcribeAudio(blob);
          if (result.text?.trim()) {
            onTranscript(result.text.trim());
            trackEvent("yafa_voice_transcribed", { duration_ms: result.duration_ms });
            setState("ready");
            if (readyTimerRef.current) clearTimeout(readyTimerRef.current);
            readyTimerRef.current = setTimeout(() => setState("idle"), 2500);
          } else {
            fail("backend");
          }
        } catch {
          fail("backend");
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setState("recording");
      trackEvent("yafa_voice_started");
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      fail("backend");
    }
  };

  const stop = (cancelled: boolean) => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    if (cancelled) {
      chunksRef.current = [];
      recorder.onstop = () => {
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setState("idle");
      };
    }
    recorder.stop();
  };

  const busy = state === "uploading" || state === "transcribing";

  return (
    <div className="yafa-mic">
      {state === "recording" ? (
        <>
          <button
            type="button"
            className="yafa-mic__stop"
            onClick={() => stop(false)}
            aria-label="Stop recording and transcribe"
          >
            ⏹ Stop
          </button>
          <span className="yafa-mic__status" role="status">
            Recording…
          </span>
          <button type="button" className="yafa-mic__cancel" onClick={() => stop(true)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            className="yafa-mic__start"
            onClick={start}
            disabled={disabled || busy || state === "requesting_permission"}
            aria-label={STATE_LABELS[state]}
            title={STATE_LABELS[state]}
          >
            🎤
          </button>
          {state !== "idle" && state !== "ready" ? (
            <span className="yafa-mic__status" role="status">
              {STATE_LABELS[state]}
              {busy ? "…" : ""}
            </span>
          ) : null}
          {state === "ready" ? (
            <span className="yafa-mic__status yafa-mic__status--ok" role="status">
              Transcript added — edit if needed
            </span>
          ) : null}
          {state === "error" && errorKind ? (
            <>
              <span className="yafa-mic__error" role="alert">
                {errorKind === "permission_denied" &&
                  "Microphone access was blocked. Allow it in your browser settings, then retry."}
                {errorKind === "no_microphone" && "No microphone was found on this device."}
                {errorKind === "unsupported" &&
                  "This browser doesn't support voice input. Try Chrome or Edge — or just type."}
                {errorKind === "backend" &&
                  "Voice transcription is unavailable right now. Retry, or continue by typing."}
              </span>
              <button type="button" className="yafa-mic__cancel" onClick={start}>
                Retry
              </button>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
