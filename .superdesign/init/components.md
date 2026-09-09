# Shared UI Components

The web app uses custom React components and vanilla global CSS rather than a third-party component library.

## AuthModal
- Source: `apps/web/components/auth/AuthModal.tsx`
- Reusable responsive sign-in, sign-up, confirmation and password-reset dialog.
- Key props: `open`, `onClose`, `returnTo`.
- Actual implementation is the complete source file at the path above; it contains labeled text inputs, native select/date controls, password visibility buttons, verification/resend states and accessible error/status regions.

## AuthProvider
- Source: `apps/web/components/auth/AuthProvider.tsx`
- Shared Cognito/native authentication context used by all routes and the modal.
- Key API: `login`, `register`, `confirmRegistration`, `resendConfirmationCode`, password reset, logout and guarded actions.

## AccountGate
- Source: `apps/web/components/auth/AccountGate.tsx`
- Protected-area loading/authentication gate used by account pages.
