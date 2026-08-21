import Link from "next/link";

const columns = [
  { title: "Help", links: [["Frequently asked questions", "/faq"], ["Contact us", "/contact"], ["My account", "/account"]] },
  { title: "Shipping & returns", links: [["Shipping", "/shipping"], ["Returns", "/returns"], ["Account and orders", "/account"]] },
  { title: "About", links: [["Our story", "/about"], ["Build My Kit", "/build-my-kit"], ["Shop all", "/shop"]] },
] as const;

export default function Footer() {
  return <footer className="site-footer"><div className="site-footer__main"><div className="site-footer__brand"><p>YAFA VANAM</p><h2>Botanical beauty, made personal.</h2><span>Thoughtful rituals for colour, care and scent.</span></div>{columns.map((column) => <nav key={column.title} aria-label={column.title}><h3>{column.title}</h3>{column.links.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}</nav>)}<section className="site-footer__newsletter"><h3>Notes from the atelier</h3><p>Occasional product stories, care rituals and new arrivals.</p><form action="#"><label className="visually-hidden" htmlFor="footer-email">Email address</label><input id="footer-email" type="email" placeholder="Email address" /><button type="submit">Subscribe</button></form></section></div><div className="site-footer__bottom"><span>© {new Date().getFullYear()} YAFA VANAM</span><div><Link href="/shipping">Shipping</Link><Link href="/returns">Returns</Link><Link href="/privacy-policy">Privacy</Link><Link href="/cookie-policy">Cookies</Link><Link href="/contact">Accessibility</Link></div></div></footer>;
}
