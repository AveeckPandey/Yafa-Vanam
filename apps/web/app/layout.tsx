import type { Metadata } from "next";
import "./globals.css";
import MakeupAdvisor from "../components/advisor/MakeupAdvisor";
import Navbar from "../components/layout/Navbar";
import CartDrawer from "../components/cart/CartDrawer";

export const metadata: Metadata = {
  title: "YAFA VANAM | Botanical Beauty, Made Personal",
  description:
    "Discover YAFA VANAM makeup, skincare and personal beauty guidance for your complexion, preferences and colour mood.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#page-content">Skip to main content</a>
        <Navbar />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <CartDrawer />
        <MakeupAdvisor />
      </body>
    </html>
  );
}
