"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CatalogProduct } from "@/lib/catalog-types";
import { useAuth } from "@/components/auth/AuthProvider";
import { getConfirmedYafaProfile, type ConfirmedYafaProfile } from "@/lib/yafa-profile";
import { trackEvent } from "@/lib/analytics";
import { advisorApi } from "@/lib/advisor/client";
import type { Recommendation } from "@/lib/advisor/types";

type Answer = { goal: string; finish: string; focus: string; budget: string };
const steps: Array<{ key: keyof Answer; label: string; question: string; options: Array<{ label: string; value: string }> }> = [
  { key: "goal", label: "Your goal", question: "What would you like your ritual to do?", options: [{ label: "Everyday ease", value: "everyday" }, { label: "Soft glow", value: "glow" }, { label: "A polished occasion", value: "occasion" }] },
  { key: "finish", label: "Your finish", question: "Which finish feels most like you?", options: [{ label: "Natural", value: "natural" }, { label: "Radiant", value: "radiant" }, { label: "Velvet", value: "velvet" }] },
  { key: "focus", label: "Your edit", question: "Where should we begin?", options: [{ label: "Complexion", value: "face" }, { label: "Eyes and lips", value: "colour" }, { label: "Skin care", value: "care" }] },
  { key: "budget", label: "Your budget", question: "How would you like to build your kit?", options: [{ label: "A considered essential", value: "essential" }, { label: "A complete ritual", value: "complete" }, { label: "Show me both", value: "both" }] },
];

/** Deterministic keyword parse of a spoken/written brief into quiz answers. */
export function parseBrief(text: string): Partial<Answer> {
  const t = ` ${text.toLowerCase()} `;
  const parsed: Partial<Answer> = {};

  if (/\b(every ?day|daily|office|work|commute)\b/.test(t)) parsed.goal = "everyday";
  else if (/\b(wedding|occasion|party|event|date|evening out|bridal)\b/.test(t)) parsed.goal = "occasion";
  else if (/\bglow\b/.test(t)) parsed.goal = "glow";

  if (/\bnatural\b/.test(t)) parsed.finish = "natural";
  else if (/\b(velvet|soft matte|blurred)\b/.test(t)) parsed.finish = "velvet";
  else if (/\b(dewy|luminous|radiant|glowy|sheen)\b/.test(t)) parsed.finish = "radiant";

  if (/\b(skincare|skin ?care|serum|cleanser|moisturi[sz]er)\b/.test(t)) parsed.focus = "care";
  else if (/\b(complexion|foundation|base|skin tint|concealer)\b/.test(t)) parsed.focus = "face";
  else if (/\b(eyes?|lips?|lipstick|mascara|liner|blush|makeup colou?r)\b/.test(t)) parsed.focus = "colour";

  if (/\b(essential|minimal|just a few|one or two)\b/.test(t)) parsed.budget = "essential";
  else if (/\b(complete|full|everything|whole ritual)\b/.test(t)) parsed.budget = "complete";
  else if (/\bboth\b/.test(t)) parsed.budget = "both";

  return parsed;
}

export default function BuildMyKit({ products }: { products: CatalogProduct[] }) {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answer>({ goal: "", finish: "", focus: "", budget: "" });
  const [yafaProfile, setYafaProfile] = useState<ConfirmedYafaProfile | null>(null);
  const [useYafaMatch, setUseYafaMatch] = useState(true);
  // Live recommendation-engine results; null until a successful engine call.
  const [engineRecs, setEngineRecs] = useState<Recommendation[] | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [seeking, setSeeking] = useState(false);

  const [briefText, setBriefText] = useState("");
  const [briefError, setBriefError] = useState<string | null>(null);

  const current = steps[step];
  const complete = step === steps.length;

  useEffect(() => {
    if (!user) {
      setYafaProfile(null);
      return;
    }
    getConfirmedYafaProfile().then(setYafaProfile).catch(() => setYafaProfile(null));
  }, [user]);

  const recommendations = useMemo(() => {
    const preferred = answers.focus === "face" ? products.filter((product) => product.makeupGroup === "face") : answers.focus === "care" ? products.filter((product) => product.category === "Skincare") : products.filter((product) => product.makeupGroup === "eyes" || product.makeupGroup === "lips");
    const yafaProduct = useYafaMatch && yafaProfile?.shade_code ? products.find((product) => product.variants.some((variant) => variant.shade?.code === yafaProfile.shade_code)) : undefined;
    return [...(yafaProduct ? [yafaProduct] : []), ...preferred, ...products.filter((product) => !preferred.includes(product) && product !== yafaProduct)].filter((product, index, list) => list.indexOf(product) === index).slice(0, answers.budget === "essential" ? 3 : 5);
  }, [answers.budget, answers.focus, products, useYafaMatch, yafaProfile]);

  const choose = (value: string) => setAnswers((currentAnswers) => ({ ...currentAnswers, [current.key]: value }));

  const applyBriefToQuiz = (text: string) => {
    const parsed = parseBrief(text);
    if (!Object.keys(parsed).length) return false;
    setAnswers((currentAnswers) => ({ ...currentAnswers, ...parsed }));
    trackEvent("quiz_answered", { source: "typed_brief", fields: Object.keys(parsed).join(",") });
    return true;
  };

  // --- results: live engine first, static fallback ---------------------------
  const seekKit = async () => {
    setStep(steps.length);
    trackEvent("recommendation_viewed", { source: "kit_builder", has_yafa_match: Boolean(yafaProfile && useYafaMatch) });
    setSeeking(true);
    setEngineError(null);
    try {
      const session = await advisorApi.create("full_look");
      await advisorApi.modify(session.id, {
        finish: answers.finish || undefined,
        occasion: answers.goal === "occasion" ? "special_photos" : "everyday",
        style: answers.goal === "glow" ? "soft_glam" : "natural",
        focus_area: answers.focus || undefined,
        budget: answers.budget || undefined,
      });
      const finalSession = await advisorApi.recommend(session.id);
      const recs = (finalSession.recommendations || []).slice(0, answers.budget === "essential" ? 3 : 5);
      setEngineRecs(recs.length ? recs : null);
      if (!recs.length) setEngineError("The live stylist didn't return picks — showing catalogue suggestions instead.");
    } catch {
      setEngineRecs(null);
      setEngineError("Live stylist is unavailable right now — showing catalogue suggestions instead.");
    } finally {
      setSeeking(false);
    }
  };

  const resetAll = () => {
    setStep(0);
    setAnswers({ goal: "", finish: "", focus: "", budget: "" });
    setEngineRecs(null);
    setEngineError(null);
    setBriefText("");
  };

  const advance = () => setStep((currentStep) => Math.min(steps.length, currentStep + 1));

  return <main id="main-content" className="kit-flow">
    <section className="kit-flow__intro"><p>YAFA VANAM / Personal ritual</p><h1>Build My Kit</h1><span>A small guided edit, shaped around how you want to feel.</span>{yafaProfile && useYafaMatch ? <aside className="kit-flow__yafa">We’ve pre-selected your Yafa shade — {yafaProfile.shade_name}. <button type="button" onClick={() => setUseYafaMatch(false)}>Undo</button></aside> : !yafaProfile ? <aside className="kit-flow__yafa">Answer a few questions to shape your edit.</aside> : null}</section>

    {/* Optional typed brief — fills the quiz from the customer's words. */}
    {!complete ? (
      <section className="kit-flow__step kit-flow__brief" aria-labelledby="kit-brief-title">
        <h2 id="kit-brief-title">Tell Yafa what you need</h2>
        <label className="visually-hidden" htmlFor="kit-brief-text">Your beauty brief</label>
        <textarea
          id="kit-brief-text"
          rows={2}
          maxLength={500}
          placeholder='e.g. “I need an everyday natural kit for office weeks.”'
          value={briefText}
          onChange={(event) => {
            setBriefText(event.target.value);
            setBriefError(null);
          }}
        />
        <div className="kit-brief__actions">
          <button
            type="button"
            onClick={() => {
              if (!applyBriefToQuiz(briefText)) {
                setBriefError("Mention a goal, finish, focus, or budget so Yafa can use your brief.");
                return;
              }
              setBriefError(null);
            }}
            disabled={!briefText.trim()}
          >
            Fill the quiz from this
          </button>
          {briefError ? <span className="kit-brief__error" role="alert">{briefError}</span> : null}
        </div>
      </section>
    ) : null}

    {!complete ? <section className="kit-flow__step" aria-labelledby="kit-question">
      <div className="kit-flow__progress" aria-label={`Step ${step + 1} of ${steps.length}`}><span>Step {step + 1} of {steps.length}</span><ol>{steps.map((item, index) => <li key={item.key} className={index <= step ? "is-active" : ""}><span className="visually-hidden">{item.label}</span></li>)}</ol></div>
      <p>{current.label}</p><h2 id="kit-question">{current.question}</h2>
      <div className="kit-flow__options" role="radiogroup" aria-label={current.question}>{current.options.map((option) => <button key={option.value} type="button" role="radio" aria-checked={answers[current.key] === option.value} className={answers[current.key] === option.value ? "is-selected" : ""} onClick={() => choose(option.value)}>{option.label}</button>)}</div>
      <div className="kit-flow__actions"><button type="button" onClick={() => setStep((currentStep) => Math.max(0, currentStep - 1))} disabled={step === 0}>Back</button><button type="button" onClick={() => { if (step === steps.length - 1) void seekKit(); else advance(); }} disabled={!answers[current.key]}>{step === steps.length - 1 ? "See my kit" : "Continue"}</button></div>
      <button type="button" className="kit-flow__skip" onClick={() => { if (step === steps.length - 1) void seekKit(); else advance(); }}>Skip this question</button>
    </section> : <section className="kit-flow__results" aria-labelledby="kit-results-title"><p>Your personal edit</p><h2 id="kit-results-title">A ritual to begin with.</h2><span>Use this as a starting point, then explore each product and its shades before adding to your bag.</span>
      {seeking ? <p className="kit-brief__status" role="status">Yafa is assembling your kit…</p> : null}
      {engineError ? <p className="kit-brief__error" role="alert">{engineError}</p> : null}
      <div>
        {engineRecs
          ? engineRecs.map((recommendation) => (
            <article key={`${recommendation.product_id}-${recommendation.variant_id || "base"}`}>
              <p>{recommendation.category}</p>
              <h3>{recommendation.product_name}</h3>
              <span>
                {recommendation.shade?.name ? `${recommendation.shade.name}. ` : ""}
                {recommendation.reason_codes[0]?.replaceAll("_", " ") || "Chosen for your preferences."}
              </span>
              <Link href={`/products/${recommendation.product_slug}`}>Explore product <span aria-hidden="true">→</span></Link>
            </article>
          ))
          : recommendations.map((product) => <article key={product.id}><p>{product.productType}</p><h3>{product.name}</h3><span>{product.shortDescription}</span><Link href={`/products/${product.slug}`}>Explore product <span aria-hidden="true">→</span></Link></article>)}
      </div>
      <button type="button" onClick={resetAll}>Edit answers</button></section>}
  </main>;
}
