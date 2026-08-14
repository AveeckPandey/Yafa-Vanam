"use client";

import Image from "next/image";
import { useState } from "react";

export default function ProductGallery({ images, alt, selectedImage = null }: { images: string[]; alt: string; selectedImage?: string | null }) {
  const [active, setActive] = useState(0);
  // A shade selection always takes priority over the browse-gallery state.
  // It prevents a previously selected gallery thumbnail from masking the
  // newly selected product variant.
  const current = selectedImage ?? images[active] ?? images[0];
  const hasThumbnails = images.length > 1;

  return (
    <div className={`pdp-gallery ${hasThumbnails ? "pdp-gallery--with-thumbs" : "pdp-gallery--single"}`}>
      {hasThumbnails ? (
        <div className="pdp-gallery__thumbs" aria-label="Product images">
          {images.map((image, index) => (
            <button key={`${image}-${index}`} type="button" className={active === index ? "is-active" : ""} aria-label={`View product image ${index + 1}`} aria-pressed={active === index} onClick={() => setActive(index)}>
              <Image src={image} alt="" fill sizes="92px" />
            </button>
          ))}
        </div>
      ) : null}
      <div className="pdp-gallery__main">
        <Image key={current} src={current} alt={alt} fill priority loading="eager" unoptimized={Boolean(selectedImage)} sizes="(max-width: 900px) 100vw, 58vw" />
        {hasThumbnails ? <p aria-live="polite">{active + 1} / {images.length}</p> : null}
      </div>
    </div>
  );
}
