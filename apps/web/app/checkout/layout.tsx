import type { ReactNode } from "react";

export const metadata = {
  title: "Secure Checkout",
  description: "Review delivery details and complete your YAFA VANAM order securely.",
  robots: { index: false, follow: false },
};

export default function CheckoutLayout({ children }: { children: ReactNode }) {
  return children;
}
