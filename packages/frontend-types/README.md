# @yafa/frontend-types

TypeScript types for the Go commerce API, generated from the OpenAPI contract.

- Contract owner: `apps/api/openapi/openapi.yaml` (kept in sync with the handlers).
- Generated output: `generated/api-types.ts` — never edit by hand.
- Regenerate after any contract change:

  ```bash
  npm run generate:api-types
  ```

Import from the barrel (`@yafa/frontend-types`) for the common aliases
(`ApiCart`, `ApiOrder`, `AuthUser`, `RazorpayCheckoutOrder`, …), or from
`@yafa/frontend-types/api-types` for the full generated `paths`/`components`/`operations`.
