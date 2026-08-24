import Link from "next/link";

const sets = [
  { title: "The Fragrance Duo", description: "Choose two scents for the rhythm of your day.", tag: "Mix + match", href: "/fragrance", image: "/images/home/campaign/set-fragrance-duo.png", alt: "Forest Rain and Wildgrove YAFA VANAM fragrance bottles" },
  { title: "The Fragrance Trio", description: "A three-scent wardrobe for every mood.", tag: "Mix + match", href: "/fragrance", image: "/images/home/campaign/set-fragrance-trio.png", alt: "Three YAFA VANAM fragrance bottles in Forest Rain, Soft Current and Windwater" },
  { title: "The Skin Ritual", description: "A considered ritual to calm, nourish and balance.", tag: "Ritual set", href: "/skincare", image: "/images/home/campaign/set-skin-ritual.png", alt: "Calmpath serum, Silkroot cream and Leafwell gel from YAFA VANAM" },
  { title: "Beauty Essentials", description: "Everyday colour, softly refined.", tag: "The edit", href: "/makeup", image: "/images/home/campaign/set-beauty-essentials.png", alt: "YAFA VANAM lip colour, blush, mascara and brow essentials" },
];

export default function FeaturedSets() {
  return <section className="featured-sets" aria-labelledby="featured-sets-title">
    <header className="featured-sets__header"><p>CURATED FOR YOUR RITUAL</p><h2 id="featured-sets-title">Sets worth keeping close.</h2><Link href="/shop">Shop all products <span aria-hidden="true">→</span></Link></header>
    <div className="featured-sets__grid">{sets.map((set) => <article key={set.title} className="featured-sets__card"><Link href={set.href} className="featured-sets__image"><img src={set.image} alt={set.alt}/></Link><div><span>{set.tag}</span><h3>{set.title}</h3><p>{set.description}</p><Link href={set.href}>Explore set <span aria-hidden="true">→</span></Link></div></article>)}</div>
  </section>;
}
