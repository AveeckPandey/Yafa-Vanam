"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";
import { useRouter } from "next/navigation";
import { type YafaAnswerMap, visibleYafaSteps } from "./steps";
import { useYafaResults } from "./YafaResultsContext";
import { trackEvent } from "@/lib/analytics";

const MAX_SELFIE_BYTES = 5 * 1024 * 1024;
const acceptedSelfieTypes = new Set(["image/jpeg", "image/png"]);

export default function YafaWizard() {
  const router = useRouter();
  const { startSession, saveAnswer, uploadSelfie, analyze } = useYafaResults();
  const [answers, setAnswers] = useState<YafaAnswerMap>({});
  const [stepIndex, setStepIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [selfieFile, setSelfieFile] = useState<File | null>(null);
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const visibleSteps = useMemo(() => visibleYafaSteps(answers), [answers]);
  const current = visibleSteps[Math.min(stepIndex, visibleSteps.length - 1)];

  useEffect(() => {
    if (!contentRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const context = gsap.context(() => { gsap.fromTo(contentRef.current, { autoAlpha: 0, x: direction * 22 }, { autoAlpha: 1, x: 0, duration: 0.35, ease: "power2.out" }); });
    return () => context.revert();
  }, [current.id, direction]);

  useEffect(() => {
    if (stepIndex >= visibleSteps.length) setStepIndex(visibleSteps.length - 1);
  }, [stepIndex, visibleSteps.length]);

  useEffect(() => { startSession().then(() => trackEvent("advisor_opened", { source: "yafa_wizard" })).catch(() => setError("Yafa is unavailable right now. Please try again shortly.")); }, [startSession]);

  function choose(value: string) {
    setAnswers((currentAnswers) => ({ ...currentAnswers, [current.id]: value }));
    setError("");
  }

  function readSelfie(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!acceptedSelfieTypes.has(file.type) || file.size > MAX_SELFIE_BYTES) {
      setError("Choose a JPG or PNG selfie that is 5 MB or smaller.");
      event.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : null;
      if (!result) { setError("We couldn’t read that image. Please choose another one."); return; }
      setSelfiePreview(result);
      setSelfieFile(file);
      setError("");
    };
    reader.onerror = () => setError("We couldn’t read that image. Please choose another one.");
    reader.readAsDataURL(file);
  }

  async function submitAnalysis() {
    const missingAnswer = visibleSteps.find((step) => step.type !== "image_upload" && step.type !== "results" && !answers[step.id]);
    if (missingAnswer) { setError("Please choose an answer before continuing."); return; }
    setError("");
    setIsSubmitting(true);
    try {
      if (selfieFile) { trackEvent("image_analysis_requested", { source: "yafa_wizard" }); await uploadSelfie(selfieFile); }
      await analyze();
      trackEvent("recommendations_generated", { source: "yafa_wizard" });
      router.push("/yafa/results");
    } catch {
      setError("Yafa couldn’t prepare your edit right now. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function next() {
    if (current.type === "image_upload") { void submitAnalysis(); return; }
    if (!answers[current.id]) { setError("Choose an option to continue."); return; }
    setError(""); setIsAdvancing(true);
    try { await saveAnswer(current.id, answers[current.id]); trackEvent("quiz_answered", { step_id: current.id }); setDirection(1); setStepIndex((index) => index + 1); }
    catch { setError("We couldn’t save that answer. Please try again."); }
    finally { setIsAdvancing(false); }
  }

  function back() {
    setError(""); setDirection(-1);
    setStepIndex((index) => Math.max(0, index - 1));
  }

  return <main className="yafa-wizard">
    <section className="yafa-wizard__shell" aria-live="polite">
      <header><p>YAFA VANAM</p><span>Your personal beauty guide</span></header>
      <div className="yafa-wizard__progress" aria-label={`Step ${stepIndex + 1} of ${visibleSteps.length}`}><span>{current.type === "results" ? "Complete" : `Step ${stepIndex + 1} of ${visibleSteps.length}`}</span><i><b style={{ width: `${((stepIndex + 1) / visibleSteps.length) * 100}%` }} /></i></div>
      <div className="yafa-wizard__content" ref={contentRef} key={current.id}>
        {current.type === "results" ? <Results /> : <><p className="yafa-wizard__eyebrow">YOUR BEAUTY PROFILE</p><h1>{current.question}</h1>
          {current.type === "image_upload" ? <SelfieStep preview={selfiePreview} onChange={readSelfie} onSkip={submitAnalysis} disabled={isSubmitting} /> : <div className="yafa-wizard__options" role="radiogroup" aria-label={current.question}>{current.options?.map((option) => <button type="button" key={option.value} role="radio" aria-checked={answers[current.id] === option.value} className={answers[current.id] === option.value ? "is-selected" : ""} onClick={() => choose(option.value)}>{option.label}</button>)}</div>}
          {error ? <p className="yafa-wizard__error" role="alert">{error}</p> : null}
          {current.type !== "image_upload" ? <div className="yafa-wizard__actions"><button type="button" onClick={back} disabled={stepIndex === 0 || isAdvancing}>Back</button><button type="button" onClick={() => void next()} disabled={isAdvancing}>{isAdvancing ? "Saving…" : "Continue"} <span>→</span></button></div> : null}
        </>}
      </div>
    </section>
  </main>;
}

function SelfieStep({ preview, onChange, onSkip, disabled }: { preview: string | null; onChange: (event: ChangeEvent<HTMLInputElement>) => void; onSkip: () => void; disabled: boolean }) {
  return <div className="yafa-wizard__selfie"><p>A selfie is optional. It stays in this step until you choose to continue.</p>{preview ? <img src={preview} alt="Selected selfie preview" /> : <label><input type="file" accept="image/jpeg,image/png" onChange={onChange} /><span>Choose a selfie <small>JPG or PNG · 5 MB max</small></span></label>}<div className="yafa-wizard__actions"><button type="button" onClick={onSkip} disabled={disabled}>{disabled ? "Preparing your edit…" : preview ? "Continue with this selfie" : "Skip selfie"} <span>→</span></button></div></div>;
}

function Results() {
  return <div className="yafa-wizard__results"><p className="yafa-wizard__eyebrow">YAFA EDIT</p><div className="yafa-wizard__check">✓</div><h1>Your beauty preferences are ready.</h1><span>Explore the collection to find products that suit the preferences you shared.</span><a href="/shop">Explore the collection <b>→</b></a></div>;
}
