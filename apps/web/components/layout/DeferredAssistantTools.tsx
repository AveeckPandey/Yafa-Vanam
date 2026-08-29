"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const YafaDrawer = dynamic(() => import("../yafa/YafaDrawer"), { ssr: false });

/**
 * The single YAFA assistant is available site-wide but is not part of the
 * first visible page. Waiting briefly lets the storefront become interactive
 * before its chat and voice code is downloaded.
 */
export default function DeferredAssistantTools() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 1200);
    return () => window.clearTimeout(timer);
  }, []);

  return ready ? <YafaDrawer /> : null;
}
