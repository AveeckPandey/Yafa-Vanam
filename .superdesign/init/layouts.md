# Shared Layouts

## RootLayout
- Source: `apps/web/app/layout.tsx`
- Complete global shell: metadata, Navbar, page content, Footer, cart drawer, assistant tools, cookie banner and welcome promo inside authentication/analytics/advisor providers.

## AuthLayout
- Source: `apps/web/app/auth/layout.tsx`
- Adds no visual wrapper; sets account routes to no-index/no-follow and returns children within RootLayout.

## Navbar
- Source: `apps/web/components/layout/Navbar.tsx`
- Full responsive storefront navigation with announcement bar, YAFA VANAM wordmark, collection links, search, account and bag controls.

## Footer
- Source: `apps/web/components/layout/Footer.tsx`
- Global storefront footer.
