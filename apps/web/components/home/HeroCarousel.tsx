"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FocusEvent } from "react";
import HeroWordmarkTransition from "./HeroWordmarkTransition";

type HeroSlide = {
  image: string;
  href: string;
  kicker: string;
  title: string;
  description: string;
  objectPosition: string;
};

const slides: HeroSlide[] = [
  {
    image: "/images/hero/yafa-vanam-soft-colour.png",
    href: "/makeup?category=cheeks",
    kicker: "Soft Colour",
    title: "Quiet glow, effortless radiance",
    description: "Glossy tint and velvet blush in buildable, petal-soft colour.",
    objectPosition: "67% center",
  },
  {
    image: "/images/hero/yafa-vanam-lip-collection.png",
    href: "/makeup?category=lips",
    kicker: "Petal Velvet",
    title: "A lip wardrobe for every mood",
    description: "Velvet colour, soft shine and modern bloom in one considered edit.",
    objectPosition: "66% center",
  },
  {
    image: "/images/hero/yafa-vanam-fragrance-trio-banner.png",
    href: "/fragrance",
    kicker: "Fragrance Trio",
    title: "A fragrance for every rhythm",
    description: "Forest Rain, Soft Current and Windwater — a three-scent wardrobe for every mood.",
    objectPosition: "center center",
  },
  {
    image: "/images/hero/yafa-vanam-cheek-collection.png",
    href: "/makeup?category=cheeks",
    kicker: "Cheek Collection",
    title: "A fresh, blooming finish",
    description: "Liquid colour and luminous powder for soft flush and seamless glow.",
    objectPosition: "54% center",
  },
];

const AUTOPLAY_DELAY = 6500;

export default function HeroCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [interactionPaused, setInteractionPaused] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const pointerStartRef = useRef<number | null>(null);
  const swipedRef = useRef(false);

  const showPrevious = useCallback(() => {
    setActiveIndex((current) => (current - 1 + slides.length) % slides.length);
  }, []);

  const showNext = useCallback(() => {
    setActiveIndex((current) => (current + 1) % slides.length);
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotionPreference = () => setPrefersReducedMotion(mediaQuery.matches);
    updateMotionPreference();
    mediaQuery.addEventListener("change", updateMotionPreference);
    return () => mediaQuery.removeEventListener("change", updateMotionPreference);
  }, []);

  useEffect(() => {
    if (interactionPaused || prefersReducedMotion) return;

    const interval = window.setInterval(showNext, AUTOPLAY_DELAY);
    return () => window.clearInterval(interval);
  }, [interactionPaused, prefersReducedMotion, showNext]);

  const handleBlur = (event: FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setInteractionPaused(false);
    }
  };

  return (
    <section
      className="hero-carousel"
      id="featured-collections"
      aria-roledescription="carousel"
      aria-label="Featured YAFA VANAM collections"
      onMouseEnter={() => setInteractionPaused(true)}
      onMouseLeave={() => setInteractionPaused(false)}
      onFocusCapture={() => setInteractionPaused(true)}
      onBlurCapture={handleBlur}
    >
      <div
        className="hero-carousel__viewport"
        onPointerDown={(event) => {
          if (event.pointerType === "mouse") return;
          pointerStartRef.current = event.clientX;
          swipedRef.current = false;
        }}
        onPointerUp={(event) => {
          if (pointerStartRef.current === null) return;
          const distance = event.clientX - pointerStartRef.current;
          pointerStartRef.current = null;
          if (Math.abs(distance) < 48) return;
          swipedRef.current = true;
          if (distance > 0) showPrevious();
          else showNext();
        }}
        onPointerCancel={() => {
          pointerStartRef.current = null;
        }}
        onClickCapture={(event) => {
          if (!swipedRef.current) return;
          event.preventDefault();
          swipedRef.current = false;
        }}
      >
        {slides.map((slide, index) => {
          const active = index === activeIndex;
          return (
            <article
              className={`hero-carousel__slide${index === 0 ? " hero-carousel__slide--warm" : ""}${active ? " is-active" : ""}`}
              key={slide.image}
              role="group"
              aria-roledescription="slide"
              aria-label={`${index + 1} of ${slides.length}: ${slide.title}`}
              aria-hidden={!active}
            >
              <Link
                className="hero-carousel__artwork"
                href={slide.href}
                tabIndex={active ? 0 : -1}
                aria-label={`${slide.title}. Shop the ${slide.kicker} collection.`}
              >
                <Image
                  src={slide.image}
                  alt=""
                  fill
                  priority={index === 0}
                  loading={index === 0 ? undefined : "eager"}
                  sizes="100vw"
                  style={{ objectPosition: slide.objectPosition }}
                />
              </Link>

              {index === 0 && <HeroWordmarkTransition isActive={active} />}

              <div className="hero-carousel__mobile-copy">
                <p>{slide.kicker}</p>
                <h2>{slide.title}</h2>
                <span>{slide.description}</span>
                <Link href={slide.href} tabIndex={active ? 0 : -1}>
                  Shop now <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </article>
          );
        })}

        <button
          className="hero-carousel__arrow hero-carousel__arrow--previous"
          type="button"
          onClick={showPrevious}
          aria-label="Show previous collection"
        >
          <span aria-hidden="true">‹</span>
        </button>
        <button
          className="hero-carousel__arrow hero-carousel__arrow--next"
          type="button"
          onClick={showNext}
          aria-label="Show next collection"
        >
          <span aria-hidden="true">›</span>
        </button>
      </div>
    </section>
  );
}
