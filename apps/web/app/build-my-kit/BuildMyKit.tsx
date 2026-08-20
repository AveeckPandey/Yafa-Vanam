"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import VoiceKitAssistant, { type VoiceKitBrief } from "@/components/advisor/VoiceKitAssistant";
import { advisorApi } from "@/lib/advisor/client";
import type { Recommendation } from "@/lib/advisor/types";
import type { CatalogProduct } from "@/lib/catalog-types";

type Answer = { goal: string; finish: string; focus: string; budget: string };
const steps: Array<{ key: keyof Answer; label: string; question: string; options: Array<{ label: string; value: string }> }> = [
  { key: "goal", label: "Your goal", question: "What would you like your ritual to do?", options: [{ label: "Everyday ease", value: "everyday" }, { label: "Soft glow", value: "glow" }, { label: "A polished occasion", value: "occasion" }] },
  { key: "finish", label: "Your finish", question: "Which finish feels most like you?", options: [{ label: "Natural", value: "natural" }, { label: "Radiant", value: "radiant" }, { label: "Velvet", value: "velvet" }] },
  { key: "focus", label: "Your edit", question: "Where should we begin?", options: [{ label: "Complexion", value: "face" }, { label: "Eyes and lips", value: "colour" }, { label: "Skin care", value: "care" }] },
  { key: "budget", label: "Your budget", question: "How would you like to build your kit?", options: [{ label: "A considered essential", value: "essential" }, { label: "A complete ritual", value: "complete" }, { label: "Show me both", value: "both" }] },
];

export default function BuildMyKit({ products }: { products: CatalogProduct[] }) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answer>({ goal: "", finish: "", focus: "", budget: "" });
  const [voiceRecommendations, setVoiceRecommendations] = useState<Recommendation[] | null>(null);
  const current = steps[step];
  const complete = step === steps.length;
  const recommendations = useMemo(() => {
    const preferred = answers.focus === "face" ? products.filter((product) => product.makeupGroup === "face") : answers.focus === "care" ? products.filter((product) => product.category === "Skincare") : products.filter((product) => product.makeupGroup === "eyes" || product.makeupGroup === "lips");
    return [...preferred, ...products.filter((product) => !preferred.includes(product))].slice(0, answers.budget === "essential" ? 3 : 5);
  }, [answers.budget, answers.focus, products]);
  const choose = (value: string) => setAnswers((currentAnswers) => ({ ...currentAnswers, [current.key]: value }));
  const next = () => setStep((currentStep) => Math.min(steps.length, currentStep + 1));
  const applyVoiceBrief = async (brief: VoiceKitBrief) => {
    setAnswers((currentAnswers) => ({ ...currentAnswers, ...brief }));
    setStep(steps.length);
    // ElevenLabs only collects preferences. The catalogue-grounded advisor still ranks the kit.
    const session = await advisorApi.create("full_look");
    const recommended = await advisorApi.modify(session.id, {
      finish: brief.finish,
      occasion: brief.goal === "occasion" ? "special_photos" : "everyday",
      style: brief.goal === "glow" ? "soft_glam" : "natural",
    });
    setVoiceRecommendations(recommended.recommendations.slice(0, brief.budget === "essential" ? 3 : 5));
  };

  return <main id="main-content" className="kit-flow">
    <section className="kit-flow__intro"><p>YAFA VANAM / Personal ritual</p><h1>Build My Kit</h1><span>A small guided edit, shaped around how you want to feel.</span></section>
    <VoiceKitAssistant onKitReady={applyVoiceBrief} />
    {!complete ? <section className="kit-flow__step" aria-labelledby="kit-question">
      <div className="kit-flow__progress" aria-label={`Step ${step + 1} of ${steps.length}`}><span>Step {step + 1} of {steps.length}</span><ol>{steps.map((item, index) => <li key={item.key} className={index <= step ? "is-active" : ""}><span className="visually-hidden">{item.label}</span></li>)}</ol></div>
      <p>{current.label}</p><h2 id="kit-question">{current.question}</h2>
      <div className="kit-flow__options" role="radiogroup" aria-label={current.question}>{current.options.map((option) => <button key={option.value} type="button" role="radio" aria-checked={answers[current.key] === option.value} className={answers[current.key] === option.value ? "is-selected" : ""} onClick={() => choose(option.value)}>{option.label}</button>)}</div>
      <div className="kit-flow__actions"><button type="button" onClick={() => setStep((currentStep) => Math.max(0, currentStep - 1))} disabled={step === 0}>Back</button><button type="button" onClick={next} disabled={!answers[current.key]}>{step === steps.length - 1 ? "See my kit" : "Continue"}</button></div>
      <button type="button" className="kit-flow__skip" onClick={next}>Skip this question</button>
    </section> : <section className="kit-flow__results" aria-labelledby="kit-results-title"><p>Your personal edit</p><h2 id="kit-results-title">A ritual to begin with.</h2><span>Use this as a starting point, then explore each product and its shades before adding to your bag.</span><div>{voiceRecommendations?.length ? voiceRecommendations.map((product) => <article key={`${product.product_id}-${product.variant_id || "base"}`}><p>{product.category}</p><h3>{product.product_name}</h3><span>{product.shade?.name ? `${product.shade.name}. ` : ""}{product.reason_codes[0]?.replaceAll("_", " ") || "Chosen for your preferences."}</span><Link href={`/shop?product=${product.product_slug}`}>Explore product <span aria-hidden="true">→</span></Link></article>) : recommendations.map((product) => <article key={product.id}><p>{product.productType}</p><h3>{product.name}</h3><span>{product.shortDescription}</span><Link href={`/products/${product.slug}`}>Explore product <span aria-hidden="true">→</span></Link></article>)}</div><button type="button" onClick={() => { setStep(0); setAnswers({ goal: "", finish: "", focus: "", budget: "" }); setVoiceRecommendations(null); }}>Edit answers</button></section>}
  </main>;
}
