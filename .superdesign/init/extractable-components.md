# Extractable Components

## Navbar
- Source: `apps/web/components/layout/Navbar.tsx`
- Category: layout
- Description: responsive global storefront navigation.
- Extractable props: active section, search-open state, bag count.
- Hardcoded: wordmark, menu labels and icon treatments.

## AuthModal
- Source: `apps/web/components/auth/AuthModal.tsx`
- Category: basic
- Description: sign-in, sign-up, verification and password-reset dialog.
- Extractable props: open, mode, step, error/notice state.
- Hardcoded: field labels, YAFA ritual eyebrow and leaf ornament.

## AuthForm
- Source: `apps/web/app/auth/AuthForm.tsx`
- Category: basic
- Description: dedicated account-page authentication form.
- Extractable props: mode and confirmation state.
- Hardcoded: form copy and route links.

## AccountGate
- Source: `apps/web/components/auth/AccountGate.tsx`
- Category: layout
- Description: protected account loading/authentication gate.
- Extractable props: loading and authenticated state.
