import HeroCarousel from "../components/home/HeroCarousel";
import FeaturedSets from "../components/home/FeaturedSets";

export default function HomePage() {
  return (
    <main id="main-content">
      <h1 className="visually-hidden">YAFA VANAM — botanical beauty, made personal</h1>
      <HeroCarousel />

      <section className="home-intro" aria-labelledby="home-intro-title">
        <p className="home-intro__eyebrow">BEAUTY IN YOUR RHYTHM</p>
        <h2 id="home-intro-title">Colour that feels like you.</h2>
        <p>
          Thoughtful formulas, modern finishes and personal guidance—made to meet
          your complexion, your mood and your everyday rituals.
        </p>
        <div className="home-intro__links">
          <a href="/shop">Explore all products</a>
          <a href="/build-my-kit">Build my personal kit</a>
        </div>
      </section>
      <FeaturedSets />
    </main>
  );
}
