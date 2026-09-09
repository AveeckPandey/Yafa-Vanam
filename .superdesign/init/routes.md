# Routes

Next.js App Router. Global layout: `apps/web/app/layout.tsx`.

- `/` → `apps/web/app/page.tsx`
- `/shop` → `apps/web/app/shop/page.tsx`
- `/products/[slug]` → `apps/web/app/products/[slug]/page.tsx`
- `/auth/sign-up` → `apps/web/app/auth/sign-up/page.tsx` → `apps/web/app/auth/AuthForm.tsx`
- `/auth/sign-in` → `apps/web/app/auth/sign-in/page.tsx` → `apps/web/app/auth/AuthForm.tsx`
- `/auth/reset-password` → `apps/web/app/auth/reset-password/page.tsx` → `apps/web/app/auth/AuthForm.tsx`
- `/account/**` → `apps/web/app/account/**/page.tsx`
- `/cart` → `apps/web/app/cart/page.tsx`
- `/checkout` → `apps/web/app/checkout/page.tsx`
- `/order/[orderId]` → `apps/web/app/order/[orderId]/page.tsx`
- `/yafa` and `/yafa/results` → advisor flow files under `apps/web/app/yafa`
- Makeup, skincare, fragrance and body-care catalogues live in their corresponding `apps/web/app` folders.
