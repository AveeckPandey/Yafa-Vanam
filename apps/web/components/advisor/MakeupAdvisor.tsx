"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { advisorApi } from "../../lib/advisor/client";
import type { AdvisorSession, Recommendation } from "../../lib/advisor/types";
import styles from "./MakeupAdvisor.module.css";

function track(event: string, props: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return;
  const ph = (window as any).posthog;
  if (ph?.capture) ph.capture(event, props);
}

export default function MakeupAdvisor() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState<AdvisorSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [explanations, setExplanations] = useState<Record<string, string>>({});

  async function launch() {
    setOpen(true); track("advisor_opened");
    if (!session) {
      setLoading(true); setError(null);
      try { setSession(await advisorApi.create()); } catch (e) { setError(e instanceof Error ? e.message : "Could not open advisor"); }
      finally { setLoading(false); }
    }
  }

  async function answer(questionId: string, value: string) {
    if (!session) return;
    setLoading(true); setError(null);
    try {
      const next = await advisorApi.answer(session.id, questionId, value);
      setSession(next); track("quiz_answered", { session_id: session.id, question_id: questionId, answer: value });
      if (questionId === "goal") track("advisor_goal_selected", { session_id: session.id, goal: value });
      if (!next.current_step) {
        const result = await advisorApi.recommend(next.id);
        setSession(result); track("recommendations_generated", { session_id: next.id, count: result.recommendations.length });
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save answer"); }
    finally { setLoading(false); }
  }

  async function modify(changes: Record<string, unknown>) {
    if (!session) return;
    setLoading(true); setError(null);
    try { const next = await advisorApi.modify(session.id, changes); setSession(next); track("recommendation_changed", { session_id: session.id, ...changes }); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not update recommendations"); }
    finally { setLoading(false); }
  }

  async function explain(rec: Recommendation) {
    if (!session) return;
    const key = rec.variant_id || rec.product_id;
    if (explanations[key]) return;
    try { const out = await advisorApi.explain(session.id, rec.product_id, rec.variant_id); setExplanations(v => ({ ...v, [key]: out.answer })); }
    catch { setExplanations(v => ({ ...v, [key]: "The explanation service is unavailable." })); }
  }

  async function upload(kind: "selfie" | "outfit", file?: File) {
    if (!session || !file) return;
    setLoading(true); setError(null); track("image_analysis_requested", { session_id: session.id, kind });
    try {
      const base64 = await new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onload=()=>resolve(String(r.result).split(",")[1] || ""); r.onerror=reject; r.readAsDataURL(file); });
      const out = await advisorApi.analyzeImage(session.id, kind, base64);
      if (out.status === "not_configured") setError(`${out.message} Choose manual matching or skip the image for now.`);
      else track("image_analysis_confirmed", { session_id: session.id, kind });
    } catch (e) { setError(e instanceof Error ? e.message : "Image analysis failed"); }
    finally { setLoading(false); }
  }

  const step = session?.current_step;
  const isUpload = step?.id === "selfie_upload" || step?.id === "outfit_upload";
  const kind = step?.id === "selfie_upload" ? "selfie" : "outfit";

  if (pathname.startsWith("/products/")) return null;

  return <>
    <button className={styles.launcher} onClick={launch}>Ask Makeup Advisor</button>
    {open && <section className={styles.panel} aria-label="YAFA VANAM Makeup Advisor">
      <header className={styles.header}><div><span className={styles.brand}>YAFA VANAM</span><span className={styles.subtitle}>Personal Makeup Advisor</span></div><button className={styles.close} onClick={()=>setOpen(false)} aria-label="Close">×</button></header>
      <div className={styles.body}>
        <div className={styles.message}>{session?.recommendations?.length ? "These are your recommendations." : step?.prompt || "Tell me what you want to create today."}</div>
        {loading && <div className={styles.status}>Thinking through your catalogue…</div>}
        {error && <div className={styles.error}>{error}</div>}
        {step && !isUpload && <div className={styles.options}>{step.options.map(option => <button disabled={loading} className={styles.option} key={option.value} onClick={()=>answer(step.id, option.value)}>{option.label}</button>)}</div>}
        {step && isUpload && <div className={styles.upload}>
          <input type="file" accept="image/*" onChange={e=>upload(kind, e.target.files?.[0])}/>
          <div className={styles.options}>
            {kind === "selfie" && <button className={styles.option} onClick={()=>modify({match_method:"manual"})}>Choose depth manually</button>}
            <button className={styles.option} onClick={()=>answer(step.id, "skipped")}>Skip image</button>
          </div>
        </div>}
        {!!session?.recommendations?.length && <>
          <div className={styles.cards}>{session.recommendations.map(rec => { const key=rec.variant_id || rec.product_id; return <article className={styles.card} key={`${rec.product_id}:${rec.variant_id}`}>
            <div className={styles.eyebrow}>{rec.category}</div><div className={styles.name}>{rec.product_name}</div>
            {rec.shade?.name && <div className={styles.shade}>{rec.shade.code ? `${rec.shade.code} — ` : ""}{rec.shade.name}</div>}
            <button className={styles.why} onClick={()=>explain(rec)}>Why this?</button>
            {explanations[key] && <div className={styles.status}>{explanations[key]}</div>}
            <div className={styles.actions}><a className={styles.secondary} href={`/shop?product=${rec.product_slug}`} onClick={()=>track("product_clicked",{session_id:session.id,product_id:rec.product_id,variant_id:rec.variant_id})}>View Product</a><button className={styles.primary} disabled title="Requires Go commerce sellability/cart validation">Add to Bag</button></div>
          </article>})}</div>
          <div className={styles.followups}>
            <button className={styles.primary} disabled title="Requires Go commerce sellability/cart validation">Add Complete Look to Bag</button>
            <button className={styles.option} onClick={()=>modify({style:"glam"})}>Make it more glam</button>
            <button className={styles.option} onClick={()=>modify({style:"natural"})}>Make it more natural</button>
            <button className={styles.option} onClick={()=>modify({coverage:"full"})}>Give me more coverage</button>
            <button className={styles.option} onClick={()=>modify({occasion:"wedding"})}>Wedding appropriate</button>
          </div>
        </>}
      </div>
    </section>}
  </>;
}
