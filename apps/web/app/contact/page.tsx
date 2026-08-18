import Link from "next/link";
import ContactForm from "./ContactForm";

export default function Page() {
  return <main id="main-content" className="utility-page contact-page"><section className="utility-page__intro"><p>YAFA VANAM / Care</p><h1>We’re here to help.</h1><span>For product questions, delivery support or thoughtful guidance on building your ritual.</span></section><section className="contact-page__content"><div><p>Care team</p><h2>We aim to reply within two business days.</h2><span>For an existing order, include the order number and the email used at checkout so we can help more quickly.</span><nav aria-label="Customer care links"><Link href="/shipping">Shipping</Link><Link href="/returns">Returns</Link><Link href="/faq">Frequently asked questions</Link></nav></div><ContactForm /></section></main>;
}
