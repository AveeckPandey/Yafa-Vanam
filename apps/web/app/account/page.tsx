import Link from "next/link";

export default function Page() {
  return <main id="main-content" className="utility-page account-page"><section className="utility-page__intro"><p>YAFA VANAM / Account</p><h1>Your ritual, in one place.</h1><span>Sign in to revisit your orders, saved products and personal beauty profile.</span></section><section className="account-page__cards"><article><p>Returning customer</p><h2>Welcome back.</h2><span>Track orders, view your saved ritual and update your details.</span><Link href="/auth/sign-in">Sign in</Link></article><article><p>New to YAFA VANAM</p><h2>Create your account.</h2><span>Save products, keep your details ready for checkout and build a more personal edit.</span><Link href="/auth/sign-up">Create account</Link></article></section></main>;
}
