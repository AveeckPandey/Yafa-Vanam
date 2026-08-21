import type { Metadata } from "next";
import "./globals.css";
import "./yafa-match.css";
import MakeupAdvisor from "../components/advisor/MakeupAdvisor";
import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import CartDrawer from "../components/cart/CartDrawer";
import { AuthProvider } from "../components/auth/AuthProvider";
import AnalyticsProvider from "../components/analytics/AnalyticsProvider";
import { CookieBanner } from "../components/consent/CookieBanner";
import { YafaResultsProvider } from "./yafa/YafaResultsContext";

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
      <body><AnalyticsProvider><AuthProvider><YafaResultsProvider>
        <a className="skip-link" href="#page-content">Skip to main content</a>
        <Navbar />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <Footer />
        <CartDrawer />
        <MakeupAdvisor />
        <CookieBanner />
      </YafaResultsProvider></AuthProvider></AnalyticsProvider></body>
    </html>
  );
}
