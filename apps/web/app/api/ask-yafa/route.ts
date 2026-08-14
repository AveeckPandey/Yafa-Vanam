import { NextResponse } from "next/server";
import { z } from "zod";
import { getProductById } from "@/lib/catalog";

const questionSchema = z.object({
  product_id: z.string().min(1),
  question: z.string().trim().min(2).max(300),
});

export async function POST(request: Request) {
  const parsed = questionSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Please enter a product question." }, { status: 400 });

  const product = getProductById(parsed.data.product_id);
  if (!product) return NextResponse.json({ error: "Product not found." }, { status: 404 });

  const normalized = parsed.data.question.toLocaleLowerCase();
  const bestMatch = product.ragQuestions
    .map((entry) => ({
      entry,
      score: entry.question
        .toLocaleLowerCase()
        .split(/\W+/)
        .filter((word) => word.length > 3 && normalized.includes(word)).length,
    }))
    .sort((a, b) => b.score - a.score)[0];

  const answer = bestMatch?.score
    ? bestMatch.entry.answer
    : `I can answer from the approved ${product.name} product record. Try asking about its purpose, use, scent profile, or place in a ritual.`;

  return NextResponse.json({ answer, product_id: product.id });
}
