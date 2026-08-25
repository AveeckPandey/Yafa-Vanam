const EMPTY_MODULE = "data:text/javascript,";

export async function resolve(specifier, context, nextResolve) {
  // "server-only" guards against client bundles; in unit tests it is inert.
  if (specifier === "server-only") {
    return { shortCircuit: true, url: EMPTY_MODULE, format: "module" };
  }
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    // TypeScript sources import each other without extensions (bundler-style);
    // Node's ESM loader needs the explicit ".ts" to apply type stripping.
    if (specifier.startsWith(".") && !/\.[cm]?[jt]sx?$/i.test(specifier)) {
      return nextResolve(`${specifier}.ts`, context);
    }
    throw error;
  }
}
