import { NextResponse } from "next/server";
import { getSearchIndex } from "@/lib/catalog";

export async function GET() {
  return NextResponse.json({ products: getSearchIndex() });
}
