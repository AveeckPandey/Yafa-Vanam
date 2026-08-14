"use client";

import { useState, type FormEvent } from "react";

export default function AskYafa({ productId, questions }: { productId: string; questions: Array<{ question: string; answer: string }> }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (text: string) => {
    if (!text.trim()) return;
    setQuestion(text);
    setBusy(true);
    setAnswer("");
    try {
      const response = await fetch("/api/ask-yafa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, question: text }),
      });
      const data = await response.json();
      setAnswer(data.answer ?? data.error ?? "I could not answer that yet.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(question);
  };

  return (
    <section className="ask-yafa" aria-labelledby="ask-yafa-title">
      <header>
        <div><p>✦ Product guidance</p><h2 id="ask-yafa-title">Ask YAFA</h2></div>
        <span>Grounded in this product</span>
      </header>
      <div className="ask-yafa__questions">
        {questions.slice(0, 3).map((item) => <button key={item.question} type="button" onClick={() => ask(item.question)}>{item.question}</button>)}
      </div>
      {answer ? <div className="ask-yafa__answer" aria-live="polite"><span>YAFA</span><p>{answer}</p></div> : null}
      <form onSubmit={submit}>
        <label className="visually-hidden" htmlFor="ask-yafa-input">Ask YAFA anything about this product</label>
        <input id="ask-yafa-input" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask YAFA about this product…" />
        <button type="submit" disabled={busy || !question.trim()} aria-label="Ask question">{busy ? "…" : "→"}</button>
      </form>
    </section>
  );
}
