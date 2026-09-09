# Key Page Dependency Trees

## /auth/sign-up
- `apps/web/app/auth/sign-up/page.tsx`
  - `apps/web/app/auth/AuthForm.tsx`
    - `apps/web/components/auth/AuthProvider.tsx`
      - `apps/web/components/auth/AuthModal.tsx`
    - `apps/web/lib/cognito-shared.ts`
- `apps/web/app/auth/layout.tsx`
- `apps/web/app/layout.tsx`
  - `apps/web/components/layout/Navbar.tsx`
  - `apps/web/components/layout/Footer.tsx`
- `apps/web/app/globals.css`

## /auth/sign-in
- Same AuthForm, AuthProvider, layout and theme dependency tree as `/auth/sign-up`.

## Global authentication modal
- `apps/web/components/auth/AuthModal.tsx`
  - `apps/web/components/auth/AuthProvider.tsx`
  - `apps/web/lib/cognito-shared.ts`
  - `apps/web/app/globals.css`

## Other key pages
- `/` uses RootLayout and components under `apps/web/components/home`.
- `/shop` uses `ShopCatalog`, collection and product-card components.
- `/products/[slug]` uses components under `apps/web/components/product`.
- `/checkout` uses `PremiumCheckoutExperience`, AuthProvider and checkout layout.
- `/yafa` uses `YafaWizard`, steps and results context.
- `/account` uses account layout, AccountGate and AuthProvider.
