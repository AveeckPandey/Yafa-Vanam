"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useState } from "react";
import styles from "./VoiceKitAssistant.module.css";

export type VoiceKitBrief = {
  goal?: "everyday" | "glow" | "occasion";
  finish?: "natural" | "radiant" | "velvet";
  focus?: "face" | "colour" | "care";
  budget?: "essential" | "complete" | "both";
};

type Props = { onKitReady: (brief: VoiceKitBrief) => void | Promise<void> };

function VoiceKitControls({ onKitReady }: Props) {
  const [error, setError] = useState<string | null>(null);
  const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID;
  const conversation = useConversation({
    clientTools: {
      // Configure a client tool with this exact name in the ElevenLabs agent dashboard.
      build_personal_kit: async (brief: VoiceKitBrief) => {
        await onKitReady(brief);
        return "Kit preferences saved and shown to the customer.";
      },
    },
    onError: (message) => setError(typeof message === "string" ? message : "The voice advisor could not connect."),
  });

  const active = conversation.status === "connected" || conversation.status === "connecting";

  function start() {
    if (!agentId) {
      setError("Voice advisor setup is incomplete. Add NEXT_PUBLIC_ELEVENLABS_AGENT_ID to the storefront environment.");
      return;
    }
    setError(null);
    conversation.startSession({ agentId });
  }

  return <div className={styles.voiceKit}>
    <div>
      <p>Prefer to talk it through?</p>
      <span>Our voice advisor will ask a few questions, then create your personal kit.</span>
    </div>
    <div className={styles.actions}>
      {active ? <button type="button" onClick={conversation.endSession}>End voice chat</button> : <button type="button" onClick={start}>Talk to YAFA</button>}
      {conversation.status === "connecting" && <small>Connecting…</small>}
    </div>
    {error && <small className={styles.error}>{error}</small>}
  </div>;
}

export default function VoiceKitAssistant(props: Props) {
  return <ConversationProvider><VoiceKitControls {...props} /></ConversationProvider>;
}
