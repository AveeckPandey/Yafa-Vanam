import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "YAFA VANAM",
    short_name: "YAFA VANAM",
    description: "Botanical beauty, made personal.",
    start_url: "/",
    display: "standalone",
    background_color: "#F9F6F0",
    theme_color: "#262220",
    icons: [{ src: "/icon.png", sizes: "32x32", type: "image/png" }],
  };
}
