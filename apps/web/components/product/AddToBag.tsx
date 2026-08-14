"use client";

import { useState } from "react";
import { addCartItem } from "@/components/cart/cart-client";

export default function AddToBag({ productId, variantId, quantity, className = "" }: { productId: string; variantId: string; quantity: number; className?: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const add = async () => {
    setBusy(true);
    setMessage("");
    try {
      await addCartItem(productId, variantId, quantity);
      setMessage("Added to your bag.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to add this item.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className={className} type="button" disabled={busy} onClick={add}>{busy ? "Adding…" : "Add to Bag"}</button>
      <span className="visually-hidden" aria-live="polite">{message}</span>
    </>
  );
}
