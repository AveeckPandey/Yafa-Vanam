import { register } from "node:module";

// Lets the node:test runner load the real "server-only"-guarded modules
// (lib/cognito-server.ts, lib/cognito-session.ts) outside Next.js, plus adds
// the explicit-.ts resolution Node's ESM loader otherwise refuses.
register(new URL("./server-only-stub.mjs", import.meta.url));
