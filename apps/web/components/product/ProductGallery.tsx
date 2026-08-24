"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

export default function ProductGallery({ image, alt, className = "" }: { image: string; alt: string; className?: string }) {
  const [isUnavailable, setIsUnavailable] = useState(false);

  useEffect(() => setIsUnavailable(false), [image]);

  return (
    <div className={`pdp-gallery pdp-gallery--single ${className}`.trim()}>
      <div className="pdp-gallery__main">
        {isUnavailable ? (
          <p className="pdp-gallery__unavailable" role="img" aria-label={`${alt}. Image unavailable`}>Product image unavailable</p>
        ) : (
          <Image src={image} alt={alt} fill priority sizes="(max-width: 900px) 100vw, 58vw" onError={() => setIsUnavailable(true)} />
        )}
      </div>
    </div>
  );
}
