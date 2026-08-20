import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { commerceApi, CommerceApiError } from "@/lib/commerce-api";

const responseSchema = z.object({ razorpay_payment_id: z.string().min(1), razorpay_order_id: z.string().min(1), razorpay_signature: z.string().min(1) });

export async function POST(request: NextRequest) {
  const parsed = responseSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Payment verification could not be completed." }, { status: 400 });
  try {
    const result = await commerceApi.verifyRazorpayPayment(parsed.data, request.headers.get("cookie") || undefined);
    return NextResponse.json(result);
  } catch (error) {
    if (error instanceof CommerceApiError) return NextResponse.json({ error: error.message }, { status: error.status });
    return NextResponse.json({ error: "Payment verification could not be completed." }, { status: 502 });
  }
}
