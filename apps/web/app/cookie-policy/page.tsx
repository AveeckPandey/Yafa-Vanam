import { CookiePreferences } from "@/components/consent/CookiePreferences";

export const metadata = { title: "Cookie Policy", alternates: { canonical: "/cookie-policy" } };

export default function CookiePolicyPage() {
  return <main id="main-content" className="route-page"><h1>Cookie Policy</h1><p>YAFA VANAM uses essential cookies and storage to keep your session, CSRF protection, cart, and consent settings working.</p><h2>Necessary cookies</h2><p>Authentication, security, cart, and consent cookies are required for core features. They cannot be disabled through the optional analytics controls.</p><h2>Optional analytics</h2><p>With your permission, PostHog and Google Analytics help us understand aggregate site use. We do not currently use advertising cookies. You can withdraw or change optional consent below.</p><CookiePreferences /></main>;
}
