"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return <html lang="en"><body><main className="page-shell"><h1>Something went wrong</h1><p>We could not load this page. Please refresh and try again.</p></main></body></html>;
}
