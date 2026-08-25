import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "YAFA VANAM",
    short_name: "YAFA VANAM",
    description: "Botanical beauty, made personal.",
    start_url: "/",
    display: "standalone",
    background_color: "#fbf8f1",
    theme_color: "#173b28",
    icons: [{ src: "/icon.png", sizes: "32x32", type: "image/png" }],
  };
}
