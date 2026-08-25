import HeroCarousel from "../components/home/HeroCarousel";
import FeaturedSets from "../components/home/FeaturedSets";
import EditorialGrid from "../components/home/EditorialGrid";
import type { Metadata } from "next";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return (
    <main id="main-content">
      <h1 className="visually-hidden">YAFA VANAM — botanical beauty, made personal</h1>
      <HeroCarousel />
      <FeaturedSets />
      <EditorialGrid />
    </main>
  );
}
