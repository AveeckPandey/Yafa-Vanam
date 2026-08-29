import assert from "node:assert/strict";
import test from "node:test";
import { getLipstickShade, getLipstickVariantImage } from "../lib/lipstick-shades";

const products = [
  {
    id: "yv-lip-001",
    variants: ["petal-nude", "clay-bloom", "rose-bark", "soft-fig", "berry-veil", "amber-rose", "moss-nude", "brick-petal"],
  },
  {
    id: "yv-lip-002",
    variants: ["petal-nude", "clay-bloom", "rose-bark", "soft-fig", "berry-veil", "amber-rose", "moss-nude", "brick-petal"],
  },
  {
    id: "yv-lip-003",
    variants: ["nude-beige", "dusty-rose", "rosewood-pink", "terracotta-red", "rust-brick", "berry-wine", "plum-brown", "deep-crimson"],
  },
];

test("each lipstick product resolves the eight approved shades and images", () => {
  for (const product of products) {
    const shades = product.variants.map((variant) => {
      const variantId = `${product.id}-${variant}`;
      const shade = getLipstickShade(product.id, variantId);
      assert.ok(shade, `${variantId} should resolve to a lipstick shade`);
      assert.ok(getLipstickVariantImage(variantId), `${variantId} should resolve to its exact image`);
      return shade.name;
    });

    assert.deepEqual(shades, [
      "Berry Soft",
      "Brick Petal",
      "Clay Rose",
      "Cocoa Blush",
      "Mauve Wood",
      "Petal Nude",
      "Rose Mist",
      "Terracotta Dream",
    ]);
  }
});
