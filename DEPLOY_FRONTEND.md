# Frontend deployment (Vercel)

Import the repository in Vercel and select `apps/web` as the project root. Set the production domain to `yafavanam.com`; redirect `www.yafavanam.com` if it is added.

Configure these variables in Vercel:

- `NEXT_PUBLIC_API_URL=https://api.yafavanam.com`
- `COMMERCE_API_URL=https://api.yafavanam.com` (server-side only)
- `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` if analytics has consent
- `NEXT_PUBLIC_GA_MEASUREMENT_ID` only if GA is enabled after consent
- `NEXT_PUBLIC_SENTRY_DSN` for browser error monitoring
- `SENTRY_DSN` only for optional Next.js server-side error reporting
- `NEXTAUTH_URL` and `NEXTAUTH_SECRET` only if the project enables NextAuth

The root `vercel.json` proxies `/api/v1/*` to `https://api.yafavanam.com`; local Next.js `/api/*` handlers still run in Vercel. Enable Vercel Analytics in the dashboard, deploy, and verify the production homepage, authentication callback, Yafa flow, cart, checkout, and the API health endpoint before promoting the release.
