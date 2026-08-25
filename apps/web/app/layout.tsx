import type { Metadata } from "next";
import "./globals.css";
import "./yafa-match.css";
import "./yafa-drawer.css";
import MakeupAdvisor from "../components/advisor/MakeupAdvisor";
import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import CartDrawer from "../components/cart/CartDrawer";
import { AuthProvider } from "../components/auth/AuthProvider";
import WelcomePromo from "../components/promo/WelcomePromo";
import AnalyticsProvider from "../components/analytics/AnalyticsProvider";
import { CookieBanner } from "../components/consent/CookieBanner";
import { YafaProvider } from "../components/yafa/YafaProvider";
import YafaDrawer from "../components/yafa/YafaDrawer";
import { YafaResultsProvider } from "./yafa/YafaResultsContext";

// metadataBase is required on Vercel so relative OG/canonical URLs resolve —
// without it Next falls back to localhost and social previews break.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://yafavanam.com";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "YAFA VANAM | Botanical Beauty, Made Personal",
  description:
    "Discover YAFA VANAM makeup, skincare and personal beauty guidance for your complexion, preferences and colour mood.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body><AnalyticsProvider><AuthProvider><YafaResultsProvider><YafaProvider>
        <a className="skip-link" href="#page-content">Skip to main content</a>
        <Navbar />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <Footer />
        <CartDrawer />
        <MakeupAdvisor />
        <YafaDrawer />
        <CookieBanner />
        <WelcomePromo />
      </YafaProvider></YafaResultsProvider></AuthProvider></AnalyticsProvider></body>
    </html>
  );
}
