"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const MakeupAdvisor = dynamic(() => import("../advisor/MakeupAdvisor"), { ssr: false });
const YafaDrawer = dynamic(() => import("../yafa/YafaDrawer"), { ssr: false });

/**
 * The assistant interfaces are available site-wide but are not part of the
 * first visible page. Waiting briefly lets the storefront become interactive
 * before their chat and voice code is downloaded.
 */
export default function DeferredAssistantTools() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 1200);
    return () => window.clearTimeout(timer);
  }, []);

  return ready ? <><MakeupAdvisor /><YafaDrawer /></> : null;
}
