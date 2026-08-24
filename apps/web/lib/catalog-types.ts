export type CatalogVariant = {
  id: string;
  size: string | null;
  shade: {
    name: string;
    code: string | null;
    undertone: string | null;
    depthFamily: string | null;
    hex: string | null;
  } | null;
  price: number;
  isActive: boolean;
};

export type CatalogIncludedShade = {
  id: string;
  name: string;
  hex: string | null;
  finish: string | null;
};

export type FragranceProfile = {
  family: string;
  facets: string[];
  topNotes: string[];
  heartNotes: string[];
  baseNotes: string[];
  scentCharacter: string;
  scentStory: string;
  mood: string[];
  season: string[];
  occasion: string[];
  intensity: string;
  relatedScentLine: string | null;
};

export type SkincareGroup =
  | "cleansers"
  | "serums-treatments"
  | "eye-care"
  | "lip-care"
  | "masks-exfoliation"
  | "moisturizers"
  | "sunscreen"
  | "scalp-care";

export type BodyCareGroup = "body-moisturizers" | "hand-foot-care";

export type MakeupGroup = "face" | "eyes" | "lips" | "cheeks";

export type CatalogActiveIngredient = {
  name: string;
  role: string | null;
  concentration: string | null;
  source: string | null;
  evidenceLevel: string | null;
  verifiedForFinalFormula: boolean | null;
  concentrationDependentClaims: boolean | null;
};

export type CatalogProduct = {
  id: string;
  slug: string;
  name: string;
  category: string;
  subcategory: string;
  productType: string;
  shortDescription: string;
  fullDescription: string;
  currency: string;
  price: number;
  compareAtPrice: number | null;
  defaultVariantId: string;
  variants: CatalogVariant[];
  includedShades: CatalogIncludedShade[];
  image: string;
  gallery: string[];
  imageAlt: string;
  skincareGroup: SkincareGroup | null;
  bodyCareGroup: BodyCareGroup | null;
  makeupGroup: MakeupGroup | null;
  benefits: string[];
  usage: { howToUse: string; amount: string | null; when: string[] };
  warnings: string[];
  ingredients: {
    fullInci: string | null;
    activeIngredients: CatalogActiveIngredient[];
    note: string | null;
  };
  fragranceProfile: FragranceProfile | null;
  ragQuestions: Array<{ question: string; answer: string }>;
};

export function formatCatalogPrice(currency: string, price: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(price);
}
