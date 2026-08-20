"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { initializeAnalytics, trackEvent } from "../../lib/analytics";

export default function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useEffect(() => { initializeAnalytics(); }, []);
  useEffect(() => { trackEvent("page_viewed", { path: pathname }); }, [pathname]);
  return children;
}
