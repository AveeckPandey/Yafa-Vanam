// Client-side instrumentation entry point (Next.js file convention). The
// Sentry browser SDK config is a side-effect module; importing it here wires
// browser error monitoring into every page load.
import "./sentry.client.config";
