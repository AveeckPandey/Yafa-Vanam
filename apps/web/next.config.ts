import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal self-contained Node server for the ECS web task.
  output: "standalone",
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "base-uri 'self'",
              "object-src 'none'",
              "frame-ancestors 'none'",
              // Next.js needs inline hydration code. Razorpay is loaded only
              // from its official checkout host when a customer pays.
              "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://checkout.razorpay.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https:",
              "font-src 'self' data:",
              "connect-src 'self' https:",
              "media-src 'self' blob:",
              "worker-src 'self' blob:",
              "frame-src 'self' https://api.razorpay.com https://checkout.razorpay.com",
              "form-action 'self'",
            ].join("; "),
          },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=()" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
