export const SITE_URL = "https://yafavanam.buildwithaveeck.com";

export function absoluteUrl(path = "/") {
  return new URL(path, SITE_URL).toString();
}
