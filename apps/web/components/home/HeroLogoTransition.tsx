"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

function LogoType() {
  return (
    <span className="morph-logo__type" aria-hidden="true">
      <span>YAFA</span>
      <span>VANAM</span>
    </span>
  );
}

export default function HeroLogoTransition() {
  const stageRef = useRef<HTMLElement>(null);
  const sourceRef = useRef<HTMLDivElement>(null);
  const staticLogoRef = useRef<HTMLDivElement>(null);
  const movingLogoRef = useRef<HTMLSpanElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!mounted) return;

    const stage = stageRef.current;
    const source = sourceRef.current;
    const staticLogo = staticLogoRef.current;
    const movingLogo = movingLogoRef.current;
    const target = document.querySelector<HTMLElement>("[data-logo-target]");

    if (!stage || !source || !staticLogo || !movingLogo || !target) return;

    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();

    media.add("(prefers-reduced-motion: no-preference)", () => {
      target.classList.add("is-logo-target-hidden");
      staticLogo.classList.add("is-hidden");
      movingLogo.classList.add("is-ready");

      const sourceType = staticLogo.querySelector<HTMLElement>(".morph-logo__type");
      const targetType = target.querySelector<HTMLElement>(".wordmark");
      if (!sourceType || !targetType) return;

      const movingType = movingLogo.querySelector<HTMLElement>(".morph-logo__type");
      if (!movingType) return;

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
          transformOrigin: "top left",
        },
        {
          x: () => targetBox().left - movingTypeOffset().left,
          y: () => targetBox().top - movingTypeOffset().top,
          "--morph-logo-scale": () => targetBox().width / sourceBox().width,
          ease: "none",
          scrollTrigger: {
            trigger: document.documentElement,
            start: "top top",
            end: () => `+=${Math.min(Math.max(stage.offsetHeight * 0.9, 190), 320)}`,
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

  return (
    <section className="brand-stage" ref={stageRef} data-logo-stage aria-label="YAFA VANAM">
      <div className="brand-stage__wash" aria-hidden="true" />
      <div className="brand-stage__source" ref={sourceRef} data-logo-source>
        <div className="brand-stage__static-logo" ref={staticLogoRef}>
          <LogoType />
        </div>
      </div>
      <p className="brand-stage__line">BOTANICAL BEAUTY · MADE PERSONAL</p>
      {mounted &&
        createPortal(
          <span
            className="morph-logo"
            aria-hidden="true"
            ref={movingLogoRef}
          >
            <LogoType />
          </span>,
          document.body,
        )}
    </section>
  );
}
