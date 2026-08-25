import type { Metadata } from "next";
import "./globals.css";
import "./yafa-match.css";
import "./yafa-drawer.css";
import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import CartDrawer from "../components/cart/CartDrawer";
import { AuthProvider } from "../components/auth/AuthProvider";
import WelcomePromo from "../components/promo/WelcomePromo";
import AnalyticsProvider from "../components/analytics/AnalyticsProvider";
import { CookieBanner } from "../components/consent/CookieBanner";
import { YafaProvider } from "../components/yafa/YafaProvider";
import { YafaResultsProvider } from "./yafa/YafaResultsContext";
import DeferredAssistantTools from "../components/layout/DeferredAssistantTools";
import { SITE_URL } from "@/lib/seo";

// metadataBase is required on Vercel so relative OG/canonical URLs resolve —
// without it Next falls back to localhost and social previews break.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "YAFA VANAM | Botanical Beauty, Made Personal",
    template: "%s | YAFA VANAM",
  },
  description:
    "Discover YAFA VANAM makeup, skincare and personal beauty guidance for your complexion, preferences and colour mood.",
  applicationName: "YAFA VANAM",
  icons: { icon: "/icon.png", apple: "/icon.png" },
  openGraph: {
    type: "website",
    locale: "en_IN",
    siteName: "YAFA VANAM",
    url: "/",
    title: "YAFA VANAM | Botanical Beauty, Made Personal",
    description: "Discover botanical makeup, skincare and fragrance made personal.",
    images: [{ url: "/images/home/campaign/hero-fragrance-collection.png", width: 1672, height: 941, alt: "YAFA VANAM botanical beauty collection" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "YAFA VANAM | Botanical Beauty, Made Personal",
    description: "Discover botanical makeup, skincare and fragrance made personal.",
    images: ["/images/home/campaign/hero-fragrance-collection.png"],
  },
};

const siteSchema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "YAFA VANAM",
      url: SITE_URL,
      logo: `${SITE_URL}/icon.png`,
    },
    {
      "@type": "WebSite",
      name: "YAFA VANAM",
      url: SITE_URL,
      potentialAction: {
        "@type": "SearchAction",
        target: `${SITE_URL}/search?q={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body><AnalyticsProvider><AuthProvider><YafaResultsProvider><YafaProvider>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(siteSchema) }} />
        <a className="skip-link" href="#page-content">Skip to main content</a>
        <Navbar />
        <div id="page-content" tabIndex={-1}>{children}</div>
        <Footer />
        <CartDrawer />
        <DeferredAssistantTools />
        <CookieBanner />
        <WelcomePromo />
      </YafaProvider></YafaResultsProvider></AuthProvider></AnalyticsProvider></body>
    </html>
  );
}
