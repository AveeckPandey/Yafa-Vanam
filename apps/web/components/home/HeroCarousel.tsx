"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const slides = [
  { eyebrow: "The fragrance edit", title: <>A garden<br />of rituals.</>, description: "Scent, colour and care composed for the pace of your everyday.", href: "/fragrance", cta: "Explore fragrance", caption: "Forest Rain · Soft Current · Windwater", image: "/images/home/campaign/hero-fragrance-lakeside.png", alt: "YAFA VANAM fragrance collection in a lakeside botanical setting" },
  { eyebrow: "The body ritual", title: <>Care that<br />keeps close.</>, description: "Thoughtful body care for hands, feet and the quieter moments in between.", href: "/body-care", cta: "Explore body care", caption: "Handgrove · Footwood · Meadowleaf", image: "/images/home/campaign/hero-body-care-winter.png", alt: "YAFA VANAM body-care collection in a soft winter landscape" },
  { eyebrow: "The colour ritual", title: <>Colour with<br />a point of view.</>, description: "Complexion, eyes and lips composed in warm, considered tones.", href: "/makeup", cta: "Explore makeup", caption: "Complexion · Eyes · Lips", image: "/images/home/campaign/hero-makeup-earth.png", alt: "YAFA VANAM makeup collection against an earthy botanical backdrop" },
  { eyebrow: "The daily skin ritual", title: <>Skin care, made<br />into a ritual.</>, description: "Thoughtful essentials for cleansing, treating, hydrating and protecting.", href: "/skincare", cta: "Explore skin care", caption: "Cleanse · Treat · Hydrate · Protect", image: "/images/home/campaign/hero-skincare-garden.png", alt: "YAFA VANAM skincare collection in a sunlit botanical garden" },
] as const;

function Wordmark() {
  return <span className="hero-logo-transition__wordmark"><span>YAFA</span><span>VANAM</span></span>;
}

export default function HeroCarousel() {
  const sectionRef = useRef<HTMLElement>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setActiveIndex((current) => (current + 1) % slides.length), 6500);
    return () => window.clearInterval(timer);
  }, [paused]);

  useEffect(() => {
    const section = sectionRef.current;
    const anchor = anchorRef.current;
    const logo = logoRef.current;
    const target = document.querySelector<HTMLElement>("[data-logo-target]");
    if (!section || !anchor || !logo || !target || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    target.classList.add("is-logo-target-hidden");
    gsap.registerPlugin(ScrollTrigger);
    const measure = () => {
      const origin = anchor.getBoundingClientRect();
      const destination = target.getBoundingClientRect();
      gsap.set(logo, { left: origin.left, top: origin.top, width: origin.width, height: origin.height, x: 0, y: 0, scale: 1, autoAlpha: 1 });
      return { x: destination.left - origin.left, y: destination.top - origin.top, scale: destination.width / origin.width };
    };
    const tween = gsap.to(logo, { x: () => measure().x, y: () => measure().y, scale: () => measure().scale, ease: "none", scrollTrigger: { trigger: section, start: "top top", end: "+=420", scrub: true, invalidateOnRefresh: true, onRefresh: measure, onUpdate: (trigger) => { const complete = trigger.progress >= 0.98; target.classList.toggle("is-logo-target-hidden", !complete); logo.classList.toggle("is-logo-transition-complete", complete); } } });
    measure();
    return () => { tween.scrollTrigger?.kill(); tween.kill(); target.classList.remove("is-logo-target-hidden"); gsap.set(logo, { clearProps: "all" }); };
  }, []);

  return <section ref={sectionRef} className="hero-campaign hero-carousel" aria-roledescription="carousel" aria-label="YAFA VANAM collections" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocusCapture={() => setPaused(true)} onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false); }}>
    <div className="hero-logo-transition__anchor" ref={anchorRef} aria-hidden="true"><Wordmark /></div>
    <div className="hero-logo-transition" ref={logoRef} data-logo-float aria-hidden="true"><Wordmark /></div>
    {slides.map((slide, index) => <article className={`hero-carousel__slide hero-carousel__slide--${index === 0 ? "fragrance" : index === 1 ? "body-care" : index === 2 ? "makeup" : "skincare"}${index === activeIndex ? " is-active" : ""}`} key={slide.href} aria-hidden={index !== activeIndex}>
      <Image className="hero-campaign__image" src={slide.image} alt={slide.alt} fill preload={index === 0} sizes="100vw" />
      <div className="hero-campaign__veil" aria-hidden="true" />
      <div className="hero-campaign__content"><p className="eyebrow">{slide.eyebrow}</p><h2>{slide.title}</h2><p className="hero-campaign__description">{slide.description}</p><Link className="button-primary" href={slide.href} tabIndex={index === activeIndex ? 0 : -1}>{slide.cta} <span aria-hidden="true">→</span></Link></div>
      <p className="hero-campaign__caption">{slide.caption}</p>
    </article>)}
    <div className="hero-carousel__controls"><button type="button" onClick={() => setActiveIndex((current) => (current - 1 + slides.length) % slides.length)} aria-label="Show previous collection">←</button><div className="hero-carousel__dots" role="tablist" aria-label="Choose a collection slide">{slides.map((slide, index) => <button key={slide.href} type="button" className={index === activeIndex ? "is-active" : ""} role="tab" aria-selected={index === activeIndex} aria-label={`Show ${slide.eyebrow.toLowerCase()}`} onClick={() => setActiveIndex(index)}><span /></button>)}</div><button type="button" onClick={() => setActiveIndex((current) => (current + 1) % slides.length)} aria-label="Show next collection">→</button></div>
  </section>;
}
