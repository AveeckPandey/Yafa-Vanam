"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useYafaResults } from "../YafaResultsContext";
import { trackEvent } from "@/lib/analytics";

export default function ShadeResults() {
  const router = useRouter();
  const { result, confirmShade: saveConfirmedShade } = useYafaResults();
  const [selectedShadeId, setSelectedShadeId] = useState(result?.primaryRecommendation ?? "");
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState("");
  const [confirmationMessage, setConfirmationMessage] = useState("");
  const [whyOpen, setWhyOpen] = useState(false);

  if (!result) return <main className="shade-results"><section className="shade-results__empty"><p>YAFA VANAM</p><h1>Your shade edit is waiting for you.</h1><span>Start the Yafa quiz to receive your server-prepared shade options.</span><Link href="/yafa">Start Yafa</Link></section></main>;
  const shadeResult = result;

  const selectedCandidate = shadeResult.candidates.find((candidate) => candidate.shade_id === selectedShadeId);
  async function confirmShade() {
    if (!selectedCandidate || !shadeResult.candidates.some((candidate) => candidate.shade_id === selectedShadeId) || isConfirming) {
      setError("Choose one of Yafa’s shade options before continuing.");
      return;
    }
    setError("");
    setIsConfirming(true);
    try {
      const confirmation = await saveConfirmedShade(selectedShadeId);
      trackEvent("shade_selected", { shade_id: selectedShadeId, source: "yafa_results" });
      setConfirmationMessage(confirmation.saved_to_profile ? "Your results are saved to your profile." : "Your shade is confirmed. Sign in to save it to your profile.");
      window.setTimeout(() => router.push(`/shop?shade=${encodeURIComponent(selectedShadeId)}`), 900);
    } catch {
      setError("We couldn’t save your shade selection. Please try again.");
      setIsConfirming(false);
    }
  }

  return <main className="shade-results"><section className="shade-results__shell"><header><p>YAFA VANAM</p><span>Personal shade edit</span></header><p className="shade-results__eyebrow">YOUR SHADE OPTIONS</p><h1>Choose the shade that feels most like you.</h1><span className="shade-results__lead">Yafa has prepared three close options for you to compare.</span>
    <div className="shade-results__cards" role="radiogroup" aria-label="Shade candidates">{shadeResult.candidates.map((candidate) => { const selected = candidate.shade_id === selectedShadeId; return <article className={selected ? "is-selected" : ""} key={candidate.shade_id} role="radio" aria-checked={selected} tabIndex={0} onClick={() => { setSelectedShadeId(candidate.shade_id); setError(""); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedShadeId(candidate.shade_id); setError(""); } }}><div className="shade-results__swatch" style={{ backgroundColor: candidate.hex }} aria-hidden="true" /><div className="shade-results__card-top"><h2>{candidate.shade_name}</h2><span>{selected ? "Selected" : "Choose shade"}</span></div><div className="shade-results__confidence" aria-label="Yafa confidence"><i><b style={{ width: `${Math.round(Math.min(1, Math.max(0, candidate.confidence)) * 100)}%` }} /></i></div><p>{candidate.reason}</p><button type="button" onClick={(event) => { event.stopPropagation(); setSelectedShadeId(candidate.shade_id); setError(""); }}>Choose This Shade</button></article>; })}</div>
    <div className="shade-results__why"><button type="button" aria-expanded={whyOpen} onClick={() => setWhyOpen((open) => !open)}>Why these shades? <span>{whyOpen ? "−" : "+"}</span></button>{whyOpen ? <p>Yafa uses the preferences and information you provided to present a small set of nearby options. Choose the one you prefer before exploring matching products.</p> : null}</div>
    {error ? <p className="shade-results__error" role="alert">{error}</p> : null}{confirmationMessage ? <p className="shade-results__saved" role="status">{confirmationMessage}</p> : null}<button className="shade-results__confirm" type="button" onClick={confirmShade} disabled={!selectedCandidate || isConfirming}>{isConfirming ? "Saving your shade…" : "Confirm My Shade"} <span>→</span></button>
  </section></main>;
}
