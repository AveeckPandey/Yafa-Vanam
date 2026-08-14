import "server-only";
import productData from "../../../data/processed/Product.json";
import type { BodyCareGroup, CatalogProduct, MakeupGroup, SkincareGroup } from "./catalog-types";
import { makeupProductImageManifest } from "./makeup-assets";

type SourceProduct = {
  id: string;
  slug: string;
  name: string;
  category: string;
  subcategory: string;
  product_type: string;
  status: string;
  description: { short: string; full: string };
  commerce: { currency: string; base_price: number; compare_at_price: number | null };
  variants: Array<{
    id: string;
    size: string | null;
    shade: { name: string; hex: string | null } | null;
    price: number;
    is_active: boolean;
  }>;
  images: {
    primary: string | null;
    gallery: string[];
    lifestyle: string[];
    detail: string[];
    texture: string | null;
    alt: string;
    paths_verified: boolean;
  };
  benefits: string[];
  usage: { how_to_use: string; amount: string | null; when: string[] };
  warnings: string[];
  ingredients: {
    full_inci: string | null;
    active_ingredients: string[];
    ingredient_data_note: string | null;
  };
  fragrance_profile?: {
    family: string;
    facets: string[];
    top_notes: string[];
    heart_notes: string[];
    base_notes: string[];
    scent_character: string;
    scent_story: string;
    mood: string[];
    season: string[];
    occasion: string[];
    intensity_positioning: string;
    related_scent_line: string | null;
  } | null;
  rag: {
    customer_questions: Array<{ question: string; answer: string }>;
  };
};

const verifiedImages: Record<string, string> = {
  "Forest Rain Body Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Forest%20Rain_Body_Mist.png",
  "Greenbrook Refreshing Body Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Greenbrook_Refreshing_Body_Mist.png",
  "Soft Current Body Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Soft_Current_Body_Mist.png",
  "Wildgrove Hair & Body Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Wildgrove_Hair_%20Body_Mist.png",
  "Windwater Hair & Body Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Windwater_Hair_Body_Mist.png",
  "Forest Rain Eau de Parfum": "/images/yafavanam/No%20Shades%20Items/fragance/Forest_Rain_Eau_de_Parfum.png",
  "Mossveil Solid Perfume Balm": "/images/yafavanam/No%20Shades%20Items/fragance/Mossveil_Solid_Perfume_Balm.png",
  "Nocturne Eau de Parfum": "/images/yafavanam/No%20Shades%20Items/fragance/Nocturne_Eau_de_Parfum.png",
  "Soft Current Eau de Parfum": "/images/yafavanam/No%20Shades%20Items/fragance/Soft_Current_Eau_de_Parfum.png",
  "Soft Ember Warm Fragrance Concept": "/images/yafavanam/No%20Shades%20Items/fragance/Soft_Ember_warm_fragrance_concept.png",
  "Wildgrove Eau de Parfum": "/images/yafavanam/No%20Shades%20Items/fragance/Wildgrove_Eau_de_Parfum.png",
  "Windwater Eau de Parfum": "/images/yafavanam/No%20Shades%20Items/fragance/Windwater_Eau_de_Parfum.png",
  "Aqua Shield Barrier Lotion": "/images/yafavanam/No%20Shades%20Items/face%20Care/Aqua_Shield_Barrier_Lotion.png",
  "Dewless Oil Control Moisturizer": "/images/yafavanam/No%20Shades%20Items/face%20Care/Dewless_Oil_Copntrol_Moisturizer.png",
  "Leafwell Hydra Balance Gel": "/images/yafavanam/No%20Shades%20Items/face%20Care/Leafwell_hydra_Balance_Gel.png",
  "Leafwell Radiance Moisturizer": "/images/yafavanam/No%20Shades%20Items/face%20Care/leafwell_Radiance_Moisturizer.png",
  "Morningroot Daily Face Cleanser": "/images/yafavanam/No%20Shades%20Items/face%20Care/Morningroot_Daily_Face_Cleanser.png",
  "Silkroot Nourishing Cream": "/images/yafavanam/No%20Shades%20Items/face%20Care/Silkroot_Nourishing_Cream.png",
  "Treeline Purifying Face Wash": "/images/yafavanam/No%20Shades%20Items/face%20Care/Treeline_Purifying_Face_Wash.png",
  "Forest Kiss Lip Mask": "/images/yafavanam/No%20Shades%20Items/Masks%20%26%20Exfoliation/Forest_Kiss_Lip_Mask.png",
  "Nightpetal Overnight Mask": "/images/yafavanam/No%20Shades%20Items/Masks%20%26%20Exfoliation/Nightpetal_Overnight_Mask.png",
  "Quietmoss Clay Detox Mask": "/images/yafavanam/No%20Shades%20Items/Masks%20%26%20Exfoliation/Quietmoss_%20Clay_Detox_Mask.png",
  "Soft Soil Exfoliating Scrub": "/images/yafavanam/No%20Shades%20Items/Masks%20%26%20Exfoliation/Soft_Soil_Exfoliating_Scrub.png",
  "Brightwood Dark Spot Corrector": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Brightwood_Dark_Spot_Corrector.png",
  "Calmpath Soothing Serum": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Calmpath_Soothing_Serum.png",
  "Clarify Niacinamide Serum": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Clarify_Niacinamide_Serum.png",
  "Eyelore Under Eye Elixir": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Eyelore_Under_Eye_Elixir.png",
  "Glowbloom Vitamin C Serum": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Glowbloom_Vitamin_C_Serum.png",
  "Herbbloom Recovery Concentrate": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Herbbloom_Recovery_Concentrate.png",
  "Oilbalance Balancing Facial Oil": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Oilbalance_Balancing_Facial_Oil.png",
  "Rootrenew Retinol Night Serum": "/images/yafavanam/No%20Shades%20Items/Serums%20%26%20treatments/Rootrenew_Retinol_Night_Serum.png",
  "Sunbloom Sunscreen Spray SPF 50": "/images/yafavanam/No%20Shades%20Items/Sun%2C%20Prep%20%26%20Finish/Sunbloom_Sunscreen_Spray_SPF_50.png",
  "Wildroot Scalp Tonic Mist": "/images/yafavanam/No%20Shades%20Items/Body%20Mists/Wildroot_Scalp_Tonic_Mist.png",
  "Meadowleaf Body Butter": "/images/yafavanam/No%20Shades%20Items/Body%20Care/Meadowleaf_Body_Butter.png",
  "Handgrove Hand Cream": "/images/yafavanam/No%20Shades%20Items/Body%20Care/Handgrove_Hand_Cream.png",
  "Footwood Foot Cream": "/images/yafavanam/No%20Shades%20Items/Body%20Care/Footwood_Foot_Cream.png",
};

const skincareGroupBySubcategory: Record<string, SkincareGroup> = {
  Cleanser: "cleansers",
  "Serums & Treatments": "serums-treatments",
  "Eye Care": "eye-care",
  "Lip Care": "lip-care",
  "Masks & Exfoliation": "masks-exfoliation",
  Moisturizer: "moisturizers",
  Sunscreen: "sunscreen",
};

// Source asset folders describe storage, not the website's customer-facing taxonomy.
const skincareTaxonomyOverrides: Record<string, SkincareGroup> = {
  "eyelore-under-eye-elixir": "eye-care",
  "wildroot-scalp-tonic-mist": "scalp-care",
};

function getSkincareGroup(product: SourceProduct): SkincareGroup | null {
  const override = skincareTaxonomyOverrides[product.slug];
  if (override) return override;
  if (product.category !== "Skincare") return null;
  return skincareGroupBySubcategory[product.subcategory] ?? null;
}

const bodyCareGroupBySubcategory: Record<string, BodyCareGroup> = {
  "Body Moisturizer": "body-moisturizers",
  "Hand & Foot Care": "hand-foot-care",
};

function getBodyCareGroup(product: SourceProduct): BodyCareGroup | null {
  if (product.category !== "Body Care") return null;
  return bodyCareGroupBySubcategory[product.subcategory] ?? null;
}

const makeupGroupBySubcategory: Record<string, MakeupGroup> = {
  Complexion: "face",
  "Face Prep & Finish": "face",
  Eyes: "eyes",
  Lips: "lips",
  "Cheeks & Multi-Use": "cheeks",
};

function getMakeupGroup(product: SourceProduct): MakeupGroup | null {
  if (product.category !== "Makeup") return null;
  return makeupGroupBySubcategory[product.subcategory] ?? null;
}

const sources = productData as unknown as SourceProduct[];

function mapProduct(product: SourceProduct): CatalogProduct {
  const activeVariants = product.variants.filter((variant) => variant.is_active);
  const primary = makeupProductImageManifest[product.id]
    ?? verifiedImages[product.name]
    ?? (product.images.paths_verified && product.images.primary
      ? product.images.primary
      : "/images/hero/yafa-vanam-soft-colour.png");
  const verifiedGallery = product.images.paths_verified
    ? [
        product.images.primary,
        ...product.images.gallery,
        ...product.images.detail,
        ...product.images.lifestyle,
        product.images.texture,
      ].filter((value): value is string => Boolean(value))
    : [];

  return {
    id: product.id,
    slug: product.slug,
    name: product.name,
    category: product.category,
    subcategory: product.subcategory,
    productType: product.product_type,
    shortDescription: product.description.short,
    fullDescription: product.description.full,
    currency: product.commerce.currency,
    price: product.commerce.base_price,
    compareAtPrice: product.commerce.compare_at_price,
    defaultVariantId: activeVariants[0]?.id ?? product.id,
    variants: activeVariants.map((variant) => ({
      id: variant.id,
      size: variant.size,
      shade: variant.shade
        ? { name: variant.shade.name, hex: variant.shade.hex }
        : null,
      price: variant.price,
      isActive: variant.is_active,
    })),
    image: primary,
    gallery: Array.from(new Set([primary, ...verifiedGallery])),
    imageAlt: product.images.alt || `${product.name} by YAFA VANAM`,
    skincareGroup: getSkincareGroup(product),
    bodyCareGroup: getBodyCareGroup(product),
    makeupGroup: getMakeupGroup(product),
    benefits: product.benefits,
    usage: {
      howToUse: product.usage.how_to_use,
      amount: product.usage.amount,
      when: product.usage.when,
    },
    warnings: product.warnings,
    ingredients: {
      fullInci: product.ingredients.full_inci,
      activeIngredients: product.ingredients.active_ingredients,
      note: product.ingredients.ingredient_data_note,
    },
    fragranceProfile: product.fragrance_profile
      ? {
          family: product.fragrance_profile.family,
          facets: product.fragrance_profile.facets,
          topNotes: product.fragrance_profile.top_notes,
          heartNotes: product.fragrance_profile.heart_notes,
          baseNotes: product.fragrance_profile.base_notes,
          scentCharacter: product.fragrance_profile.scent_character,
          scentStory: product.fragrance_profile.scent_story,
          mood: product.fragrance_profile.mood,
          season: product.fragrance_profile.season,
          occasion: product.fragrance_profile.occasion,
          intensity: product.fragrance_profile.intensity_positioning,
          relatedScentLine: product.fragrance_profile.related_scent_line,
        }
      : null,
    ragQuestions: product.rag.customer_questions ?? [],
  };
}

const catalogue = sources.filter((product) => product.status === "active").map(mapProduct);

export function getAllCatalogProducts() {
  return catalogue;
}

export function getProductBySlug(slug: string) {
  return catalogue.find((product) => product.slug === slug) ?? null;
}

export function getProductById(id: string) {
  return catalogue.find((product) => product.id === id) ?? null;
}

export function getFragranceProducts() {
  return catalogue.filter((product) => product.category === "Fragrance");
}

export function getSkincareProducts() {
  return catalogue.filter((product) => product.skincareGroup !== null);
}

export function getBodyCareProducts() {
  return catalogue.filter((product) => product.bodyCareGroup !== null);
}

export function getMakeupProducts() {
  return catalogue.filter((product) => product.makeupGroup !== null);
}

export function getRelatedProducts(product: CatalogProduct, limit = 4) {
  return catalogue
    .filter((candidate) => candidate.id !== product.id && candidate.category === product.category)
    .map((candidate) => {
      let score = 0;
      if (
        product.fragranceProfile?.relatedScentLine
        && candidate.fragranceProfile?.relatedScentLine === product.fragranceProfile.relatedScentLine
      ) score += 10;
      if (candidate.fragranceProfile?.family === product.fragranceProfile?.family) score += 5;
      if (candidate.productType === product.productType) score += 2;
      return { candidate, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ candidate }) => candidate);
}
