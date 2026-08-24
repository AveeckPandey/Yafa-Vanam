import Link from "next/link";

export default function NotFound() {
  return <main id="main-content" className="route-not-found"><p>YAFA VANAM</p><h1>This page has moved on.</h1><span>Try the collection, your bag, or return to the homepage.</span><div><Link href="/shop">Shop the collection</Link><Link href="/">Return home</Link></div></main>;
}
