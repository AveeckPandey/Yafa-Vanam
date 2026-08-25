import Link from "next/link";

export const metadata = { title: "Order Confirmation", robots: { index: false, follow: false } };

export default function OrderConfirmationPage() {
  return <main className="yv-order-confirmation">
    <section>
      <p>YAFA VANAM</p>
      <h1>Thank you for your order.</h1>
      <span>Your payment has been verified. We’ll send your order confirmation and delivery updates by email.</span>
      <Link href="/shop">Continue shopping</Link>
    </section>
  </main>;
}
