"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return <html lang="en"><body><main className="route-not-found"><p>YAFA VANAM</p><h1>Something interrupted this ritual.</h1><span>We could not load this page. Please try again.</span><div><button type="button" onClick={() => window.location.reload()}>Try again</button><a href="/">Return home</a></div></main></body></html>;
}
