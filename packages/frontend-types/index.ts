// Barrel for the generated contract. Import from "@yafa/frontend-types" —
// never hand-edit generated/api-types.ts; regenerate it instead:
//   npm run generate:api-types
export type {
  paths,
  components,
  operations,
} from "./generated/api-types";

import type { components } from "./generated/api-types";

type Schemas = components["schemas"];

// The shapes the storefront consumes most, promoted to top-level names.
export type ApiError = Schemas["Error"];
export type ApiCartLine = Schemas["CartLine"];
export type ApiCart = Schemas["Cart"];
export type ApiOrder = Schemas["Order"];
export type ApiProduct = Schemas["Product"];
export type ApiProductList = Schemas["ProductList"];
export type ApiCategory = Schemas["Category"];
export type AuthUser = Schemas["User"];
export type RazorpayCheckoutOrder = Schemas["RazorpayCheckoutOrder"];
export type RazorpayVerificationResult = Schemas["RazorpayVerificationResult"];
export type BeautyProfile = Schemas["BeautyProfile"];
export type YafaAnalysis = Schemas["YafaAnalysis"];
export type YafaConfirmation = Schemas["YafaConfirmation"];
