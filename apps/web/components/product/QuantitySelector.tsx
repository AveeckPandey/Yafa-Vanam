"use client";

export default function QuantitySelector({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <div className="quantity-selector" aria-label="Quantity">
      <button type="button" aria-label="Decrease quantity" disabled={value <= 1} onClick={() => onChange(Math.max(1, value - 1))}>−</button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="Increase quantity" disabled={value >= 20} onClick={() => onChange(Math.min(20, value + 1))}>+</button>
    </div>
  );
}
