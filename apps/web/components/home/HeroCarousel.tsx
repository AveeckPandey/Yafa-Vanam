import Image from "next/image";
import Link from "next/link";

export default function HeroCarousel() {
  return (
    <section className="hero-campaign" id="featured-collections" aria-labelledby="hero-title">
      <Image
        className="hero-campaign__image"
        src="/images/home/campaign/hero-fragrance-collection.png"
        alt="YAFA VANAM Forest Rain, Soft Current and Windwater fragrance bottles among white blossoms"
        fill
        priority
        sizes="100vw"
      />
      <div className="hero-campaign__veil" aria-hidden="true" />
      <div className="hero-campaign__content">
        <p className="eyebrow">The fragrance edit</p>
        <h2 id="hero-title">A garden<br />of rituals.</h2>
        <p className="hero-campaign__description">Scent, colour and care composed for the pace of your everyday.</p>
        <Link className="button-primary" href="/fragrance">Explore fragrance <span aria-hidden="true">→</span></Link>
      </div>
      <p className="hero-campaign__caption">Forest Rain · Soft Current · Windwater</p>
    </section>
  );
}
