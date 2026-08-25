import Image from "next/image";
import Link from "next/link";

const stories = [
  { title: "The power of botanical actives", label: "Ingredient intelligence", href: "/skincare", image: "/images/home/campaign/story-botanical-actives.png", alt: "YAFA VANAM botanical serum with a dropper and golden serum texture" },
  { title: "Five effortless looks for every mood", label: "The everyday edit", href: "/makeup", image: "/images/home/campaign/story-everyday-makeup.png", alt: "YAFA VANAM blush, lipstick and pencil arranged as a makeup editorial" },
  { title: "The art of layering fragrance", label: "The fragrance ritual", href: "/fragrance", image: "/images/home/campaign/story-fragrance-layering.png", alt: "YAFA VANAM Forest Rain fragrance with weathered wood and white flowers" },
];

export default function EditorialGrid() {
  return <>
    <section className="real-skin" aria-labelledby="real-skin-title"><Image src="/images/home/campaign/real-skin-banner.png" alt="A woman with natural skin applying YAFA VANAM skincare" fill sizes="100vw"/><div><p>SKIN, UNFILTERED</p><h2 id="real-skin-title">Made for real skin.<br/>Made for real life.</h2><span>Modern skincare and clean colour, rooted in nature and made to move with you.</span><Link href="/skincare">Explore skin care <b aria-hidden="true">→</b></Link></div></section>
    <section className="editorial-grid" aria-labelledby="editorial-grid-title"><header><p>FROM THE ATELIER</p><h2 id="editorial-grid-title">Stories, rituals &amp; everything in between.</h2><Link href="/shop">Explore the collection <span aria-hidden="true">→</span></Link></header><div>{stories.map((story) => <article key={story.title}><Link href={story.href}><Image src={story.image} alt={story.alt} fill sizes="(max-width: 620px) 100vw, 33vw" /></Link><p>{story.label}</p><h3>{story.title}</h3><Link href={story.href}>Discover more <span aria-hidden="true">→</span></Link></article>)}</div></section>
  </>;
}
