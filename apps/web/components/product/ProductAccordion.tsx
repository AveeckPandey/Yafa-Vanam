"use client";

import { useState, type ReactNode } from "react";

export default function ProductAccordion({ title, children, openByDefault = false }: { title: string; children: ReactNode; openByDefault?: boolean }) {
  const [open, setOpen] = useState(openByDefault);
  const id = `product-accordion-${title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="product-accordion">
      <h3><button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((value) => !value)}><span>{title}</span><span aria-hidden="true">{open ? "−" : "+"}</span></button></h3>
      <div id={id} hidden={!open}>{children}</div>
    </div>
  );
}
