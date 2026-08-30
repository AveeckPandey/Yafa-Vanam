import Image from "next/image";
import Link from "next/link";

export type MegaMenuKey = "skincare" | "makeup" | "body" | "fragrance";

type MenuColumn = {
  title: string;
  links: Array<{ label: string; href: string }>;
  groups?: Array<{ title: string; links: Array<{ label: string; href: string }> }>;
};

type MenuContent = {
  eyebrow: string;
  title: string;
  shopAllHref: string;
  columns: MenuColumn[];
  feature: { image: string; imagePosition: string; label: string; title: string; href: string };
};

const menuContent: Record<MegaMenuKey, MenuContent> = {
  skincare: {
    eyebrow: "Care, considered", title: "Skin Care", shopAllHref: "/skincare",
    columns: [
      { title: "Cleanse", links: [{ label: "Cleansers", href: "/skincare?category=cleansers" }] },
      { title: "Treat", links: [{ label: "Serums & Treatments", href: "/skincare?category=serums" }, { label: "Eye Care", href: "/skincare?category=eye-care" }, { label: "Lip Care", href: "/skincare?category=lip-care" }, { label: "Masks & Exfoliation", href: "/skincare?category=masks" }] },
      {
        title: "Hydrate", links: [{ label: "Moisturizers", href: "/skincare?category=moisturisers" }],
        groups: [
          { title: "Protect", links: [{ label: "Sunscreen", href: "/skincare?category=sun-care" }] },
          { title: "Scalp Care", links: [{ label: "Scalp Tonic", href: "/skincare?category=scalp-care" }] },
        ],
      },
    ],
    feature: { image: "/images/home/campaign/hero-skincare-garden.png", imagePosition: "72% center", label: "Your skin, only more seamless", title: "Meet the Earth Skin complexion ritual", href: "/makeup?category=complexion" },
  },
  makeup: {
    eyebrow: "Colour with intention", title: "Make Up", shopAllHref: "/makeup",
    columns: [
      { title: "Face", links: [{ label: "Foundation", href: "/makeup?category=face&type=foundation" }, { label: "Skin Tint", href: "/makeup?category=face&type=skin-tint" }, { label: "Powder Foundation", href: "/makeup?category=face&type=powder-foundation" }, { label: "Concealer", href: "/makeup?category=face&type=concealer" }, { label: "Color Corrector", href: "/makeup?category=face&type=color-corrector" }, { label: "Face Primer", href: "/makeup?category=face&type=face-primer" }, { label: "Setting Powder", href: "/makeup?category=face&type=setting-powder" }, { label: "Setting Spray", href: "/makeup?category=face&type=setting-spray" }, { label: "Bronzer", href: "/makeup?category=face&type=bronzer" }, { label: "Contour", href: "/makeup?category=face&type=contour" }, { label: "Highlighter", href: "/makeup?category=face&type=highlighter" }] },
      { title: "Eyes", links: [{ label: "Mascara", href: "/makeup?category=eyes&type=mascara" }, { label: "Eyeshadow", href: "/makeup?category=eyes&type=eyeshadow" }, { label: "Eyeliner", href: "/makeup?category=eyes&type=eyeliner" }, { label: "Brows", href: "/makeup?category=eyes&type=brows" }, { label: "Eye Sets", href: "/makeup?category=eyes&type=eye-sets" }] },
      { title: "Lips", links: [{ label: "Lipstick", href: "/makeup?category=lips&type=lipstick" }, { label: "Lip Oil", href: "/makeup?category=lips&type=lip-oil" }, { label: "Lip Gloss", href: "/makeup?category=lips&type=lip-gloss" }, { label: "Lip Liner", href: "/makeup?category=lips&type=lip-liner" }, { label: "Lip Stain", href: "/makeup?category=lips&type=lip-stain" }, { label: "Lip Plumper", href: "/makeup?category=lips&type=lip-plumper" }] },
      { title: "Cheeks", links: [{ label: "Blush", href: "/makeup?category=cheeks&type=blush" }, { label: "Lip + Cheek", href: "/makeup?category=cheeks&type=lip-cheek" }] },
    ],
    feature: { image: "/images/home/campaign/hero-makeup-earth.png", imagePosition: "76% center", label: "Petal-soft colour", title: "A fresh flush with a luminous finish", href: "/makeup?category=cheeks" },
  },
  body: {
    eyebrow: "Care from head to toe", title: "Body Care", shopAllHref: "/body-care",
    columns: [
      { title: "Body Moisturizers", links: [{ label: "Body Butter", href: "/body-care?type=body-butter" }] },
      { title: "Hand & Foot Care", links: [{ label: "Hand Cream", href: "/body-care?type=hand-cream" }, { label: "Foot Cream", href: "/body-care?type=foot-cream" }] },
    ],
    feature: { image: "/images/home/campaign/hero-body-care-winter.png", imagePosition: "72% center", label: "Daily rituals", title: "Care that feels as good as it performs", href: "/body-care" },
  },
  fragrance: {
    eyebrow: "A signature in every note", title: "Fragrance", shopAllHref: "/fragrance",
    columns: [
      { title: "Body & Hair Mists", links: [{ label: "Body Mist", href: "/fragrance?category=body-mist" }, { label: "Hair & Body Mist", href: "/fragrance?category=hair-body-mist" }] },
      { title: "Perfume", links: [{ label: "Eau de Parfum", href: "/fragrance?category=eau-de-parfum" }, { label: "Solid Perfume", href: "/fragrance?category=solid-perfume" }, { label: "Warm Fragrance", href: "/fragrance?category=warm-fragrance" }] },
    ],
    feature: { image: "/images/home/campaign/hero-fragrance-lakeside.png", imagePosition: "72% center", label: "Find your signature", title: "Fragrance for every mood and ritual", href: "/fragrance" },
  },
};

export default function MegaMenu({ activeMenu, labelledBy, onNavigate }: { activeMenu: MegaMenuKey; labelledBy: string; onNavigate: () => void }) {
  const content = menuContent[activeMenu];
  return <section className="mega-menu" id="desktop-mega-menu" aria-labelledby={labelledBy}>
    <div className="site-shell mega-menu__inner">
      <div className="mega-menu__intro"><p>{content.eyebrow}</p><h2>{content.title}</h2><Link href={content.shopAllHref} onClick={onNavigate}>Shop all <span aria-hidden="true">↗</span></Link></div>
      {content.columns.map((column) => <div className="mega-menu__column" key={column.title}><h3>{column.title}</h3><ul>{column.links.map((link) => <li key={link.label}><Link href={link.href} onClick={onNavigate}>{link.label}</Link></li>)}</ul>{column.groups?.map((group) => <div className="mega-menu__subgroup" key={group.title}><h3>{group.title}</h3><ul>{group.links.map((link) => <li key={link.label}><Link href={link.href} onClick={onNavigate}>{link.label}</Link></li>)}</ul></div>)}</div>)}
      <Link className="mega-menu__feature" href={content.feature.href} onClick={onNavigate}><span className="mega-menu__feature-image"><Image src={content.feature.image} alt="" fill sizes="280px" style={{ objectPosition: content.feature.imagePosition }} /></span><span className="mega-menu__feature-label">{content.feature.label}</span><strong>{content.feature.title}</strong></Link>
    </div>
  </section>;
}
