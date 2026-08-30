export type LipstickShade = {
  key: string;
  name: string;
  hex: string;
  description: string;
};

const lipstickShades: LipstickShade[] = [
  { key: "berry-soft", name: "Berry Soft", hex: "#C16A62", description: "Warm, soft terracotta-peach" },
  { key: "brick-petal", name: "Brick Petal", hex: "#9F3A44", description: "Deep brick red" },
  { key: "clay-rose", name: "Clay Rose", hex: "#A84D58", description: "Classic dusty rose" },
  { key: "cocoa-blush", name: "Cocoa Blush", hex: "#9C554F", description: "Warm, brown-toned nude" },
  { key: "mauve-wood", name: "Mauve Wood", hex: "#AD4658", description: "Vibrant pink-mauve" },
  { key: "petal-nude", name: "Petal Nude", hex: "#BC6860", description: "Muted rosy nude" },
  { key: "rose-mist", name: "Rose Mist", hex: "#C06F63", description: "Soft, warm peach-rose" },
  { key: "terracotta-dream", name: "Terracotta Dream", hex: "#83324A", description: "Deep plum-berry" },
];

const riverroseShades: Record<string, LipstickShade> = {
  "petal-nude": { key: "petal-nude", name: "Petal Nude", hex: "#C78A69", description: "Muted rosy nude" },
  "clay-bloom": { key: "clay-rose", name: "Clay Bloom", hex: "#B96E56", description: "Warm clay rose" },
  "rose-bark": { key: "cocoa-blush", name: "Rose Bark", hex: "#A85C52", description: "Rose-brown nude" },
  "soft-fig": { key: "mauve-wood", name: "Soft Fig", hex: "#9D4B58", description: "Soft berry fig" },
  "berry-veil": { key: "berry-soft", name: "Berry Veil", hex: "#B6505D", description: "Sheer berry rose" },
  "amber-rose": { key: "rose-mist", name: "Amber Rose", hex: "#C16F5B", description: "Warm amber rose" },
  "moss-nude": { key: "terracotta-dream", name: "Moss Nude", hex: "#98664E", description: "Earthy muted nude" },
  "brick-petal": { key: "brick-petal", name: "Brick Petal", hex: "#913C43", description: "Deep brick petal" },
};

const sourceVariantIdsByProduct: Record<string, string[]> = {
  "yv-lip-001": ["petal-nude", "clay-bloom", "rose-bark", "soft-fig", "berry-veil", "amber-rose", "moss-nude", "brick-petal"],
  "yv-lip-002": ["petal-nude", "clay-bloom", "rose-bark", "soft-fig", "berry-veil", "amber-rose", "moss-nude", "brick-petal"],
  "yv-lip-003": ["petal-nude", "clay-bloom", "rose-bark", "soft-fig", "berry-veil", "amber-rose", "moss-nude", "brick-petal"],
};

const lipstickImagePaths: Record<string, Record<string, string>> = {
  "yv-lip-001": {
    "berry-soft": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Berry-Soft.png",
    "brick-petal": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Brick-Petal.png",
    "clay-rose": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Clay-Rose.png",
    "cocoa-blush": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Cocoa-Blush.png",
    "mauve-wood": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Mauve-Wood.png",
    "petal-nude": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Petal-Nude.png",
    "rose-mist": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Rose-Mist.png",
    "terracotta-dream": "/images/yafavanam/lips/Petal-Velvet/Petal-Velvet-Terracotta-Dream.png",
  },
  "yv-lip-002": {
    "berry-soft": "/images/yafavanam/lips/ClayRose/ClayRose_Satin__berry_soft.png",
    "brick-petal": "/images/yafavanam/lips/ClayRose/ClayRose_Satin__brick_petal.png",
    "clay-rose": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_clay_rose.png",
    "cocoa-blush": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_cocoa_blush.png",
    "mauve-wood": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_mauve_wood.png",
    "petal-nude": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_Petal-Nude.png",
    "rose-mist": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_rose_mist.png",
    "terracotta-dream": "/images/yafavanam/lips/ClayRose/ClayRose_Satin_terracotta_dream.png",
  },
  "yv-lip-003": {
    "berry-soft": "/images/yafavanam/lips/RiverRose/RiverRose-Berry-Soft.png",
    "brick-petal": "/images/yafavanam/lips/RiverRose/RiverRose-Petal_Nude-Brick-Red.png",
    "clay-rose": "/images/yafavanam/lips/RiverRose/RiverRose-Clay-Rose.png",
    "cocoa-blush": "/images/yafavanam/lips/RiverRose/RiverRose-Cocoa-Blush.png",
    "mauve-wood": "/images/yafavanam/lips/RiverRose/RiverRose-Mauve-Wood.png",
    "petal-nude": "/images/yafavanam/lips/RiverRose/RiverRose-Petal_Nude.png",
    "rose-mist": "/images/yafavanam/lips/RiverRose/RiverRose-Rose-Mint.png",
    "terracotta-dream": "/images/yafavanam/lips/RiverRose/RiverRose-Terracotta-Dream.png",
  },
};

export function getLipstickShade(productId: string, variantId: string): LipstickShade | null {
  if (productId === "yv-lip-003") {
    const riverroseKey = variantId.replace(`${productId}-`, "");
    return riverroseShades[riverroseKey] ?? null;
  }
  const sourceIds = sourceVariantIdsByProduct[productId];
  if (!sourceIds) return null;
  const position = sourceIds.findIndex((id) => variantId === `${productId}-${id}`);
  return position >= 0 ? lipstickShades[position] ?? null : null;
}

export function getLipstickShadeByVariantId(variantId: string): LipstickShade | null {
  const productId = Object.keys(sourceVariantIdsByProduct).find((id) => variantId.startsWith(`${id}-`));
  return productId ? getLipstickShade(productId, variantId) : null;
}

export function getLipstickVariantImage(variantId: string): string | null {
  const productId = Object.keys(lipstickImagePaths).find((id) => variantId.startsWith(`${id}-`));
  if (!productId) return null;
  const shade = getLipstickShade(productId, variantId);
  return shade ? lipstickImagePaths[productId][shade.key] ?? null : null;
}
