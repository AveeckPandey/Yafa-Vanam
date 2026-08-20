"use client";

import { createPortal } from "react-dom";
import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

function Wordmark() {
  return (
    <span className="morph-logo__type" aria-hidden="true">
      <span>YAFA</span>
      <span>VANAM</span>
    </span>
  );
}

/** Starts in the first carousel slide, then settles into the navbar on scroll. */
export default function HeroWordmarkTransition({ isActive }: { isActive: boolean }) {
  const sourceRef = useRef<HTMLDivElement>(null);
  const staticLogoRef = useRef<HTMLDivElement>(null);
  const movingLogoRef = useRef<HTMLSpanElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!mounted) return;

    const source = sourceRef.current;
    const staticLogo = staticLogoRef.current;
    const movingLogo = movingLogoRef.current;
    const target = document.querySelector<HTMLElement>("[data-logo-target]");
    if (!source || !staticLogo || !movingLogo || !target) return;

    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();

    media.add("(prefers-reduced-motion: no-preference)", () => {
      const sourceType = staticLogo.querySelector<HTMLElement>(".morph-logo__type");
      const targetType = target.querySelector<HTMLElement>(".wordmark");
      const movingType = movingLogo.querySelector<HTMLElement>(".morph-logo__type");
      if (!sourceType || !targetType || !movingType) return;

      target.classList.add("is-logo-target-hidden");
      staticLogo.classList.add("is-hidden");
      movingLogo.classList.add("is-ready");

      const sourceBox = () => sourceType.getBoundingClientRect();
      const targetBox = () => targetType.getBoundingClientRect();
      const movingTypeOffset = () => {
        const linkRect = movingLogo.getBoundingClientRect();
        const typeRect = movingType.getBoundingClientRect();
        return { left: typeRect.left - linkRect.left, top: typeRect.top - linkRect.top };
      };

      const animation = gsap.fromTo(
        movingLogo,
        {
          x: () => sourceBox().left - movingTypeOffset().left,
          y: () => sourceBox().top + window.scrollY - movingTypeOffset().top,
          "--morph-logo-scale": 1,
        },
        {
          x: () => targetBox().left - movingTypeOffset().left,
          y: () => targetBox().top - movingTypeOffset().top,
          "--morph-logo-scale": () => targetBox().width / sourceBox().width,
          ease: "none",
          scrollTrigger: {
            trigger: document.documentElement,
            start: "top top",
            end: "+=260",
            scrub: 0.45,
            invalidateOnRefresh: true,
          },
        },
      );

      const resizeObserver = new ResizeObserver(() => ScrollTrigger.refresh());
      resizeObserver.observe(sourceType);
      resizeObserver.observe(targetType);
      document.fonts?.ready.then(() => ScrollTrigger.refresh());

      return () => {
        resizeObserver.disconnect();
        animation.scrollTrigger?.kill();
        animation.kill();
        movingLogo.classList.remove("is-ready");
        staticLogo.classList.remove("is-hidden");
        target.classList.remove("is-logo-target-hidden");
      };
    });

    return () => media.revert();
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;

    const movingLogo = movingLogoRef.current;
    const target = document.querySelector<HTMLElement>("[data-logo-target]");
    if (!movingLogo || !target) return;

    // The portal is outside the slide, so explicitly hide it when the carousel
    // advances and restore the ordinary navbar wordmark.
    if (isActive) {
      movingLogo.style.opacity = "1";
      movingLogo.style.visibility = "visible";
      target.classList.add("is-logo-target-hidden");
    } else {
      movingLogo.style.opacity = "0";
      movingLogo.style.visibility = "hidden";
      target.classList.remove("is-logo-target-hidden");
    }
  }, [isActive, mounted]);

  return (
    <div className="hero-carousel__wordmark-source" ref={sourceRef} aria-label="YAFA VANAM">
      <div className="hero-carousel__wordmark-static" ref={staticLogoRef}>
        <Wordmark />
      </div>
      {mounted &&
        createPortal(
          <span className="morph-logo" aria-hidden="true" ref={movingLogoRef}>
            <Wordmark />
          </span>,
          document.body,
        )}
    </div>
  );
}
