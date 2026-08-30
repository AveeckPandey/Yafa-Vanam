import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(webRoot, "..", "..");
const errors = [];

function readJson(relativePath) {
  return JSON.parse(readFileSync(join(repoRoot, relativePath), "utf8"));
}

function fail(message) {
  errors.push(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function duplicateValues(values) {
  const seen = new Set();
  return values.filter((value) => seen.has(value) || !seen.add(value));
}

const processedProducts = readJson("data/processed/Product.json");
const authoritativeProducts = processedProducts;
const sourceById = new Map(authoritativeProducts.map((product) => [product.id, product]));

for (const [label, products] of [["canonical", authoritativeProducts]]) {
  for (const field of ["id", "slug"]) {
    const duplicates = [...new Set(duplicateValues(products.map((product) => product[field]).filter(Boolean)))];
    assert(duplicates.length === 0, `${label} catalogue has duplicate ${field}: ${duplicates.join(", ")}`);
  }
}

for (const product of authoritativeProducts) {
  const variants = (product.variants ?? []).filter((variant) => variant.is_active && variant.shade);
  const ids = variants.map((variant) => variant.id);
  assert(duplicateValues(ids).length === 0, `${product.slug} has duplicate shade variant IDs`);
  const completeShades = variants.map((variant) => JSON.stringify(variant.shade));
  assert(duplicateValues(completeShades).length === 0, `${product.slug} has duplicate complete shade objects`);
}

const moonveil = sourceById.get("yv-eye-006");
const moonveilVariantIds = [
  "yv-eye-006-aubergine-plum",
  "yv-eye-006-bronze",
  "yv-eye-006-deep-burgundy",
  "yv-eye-006-rose-gold",
  "yv-eye-006-smoky-charcoal",
  "yv-eye-006-antique-gold",
  "yv-eye-006-champagne-gold",
];
assert(moonveil?.variants?.length === moonveilVariantIds.length, "Moonveil must expose all seven canonical shades");
assert(moonveilVariantIds.every((id) => moonveil?.variants?.some((variant) => variant.id === id && variant.shade?.name)), "Moonveil canonical shades must have named sellable variants");

const petalVelvetIds = [
  "yv-lip-001-petal-nude",
  "yv-lip-001-clay-bloom",
  "yv-lip-001-rose-bark",
  "yv-lip-001-soft-fig",
  "yv-lip-001-berry-veil",
  "yv-lip-001-amber-rose",
  "yv-lip-001-moss-nude",
  "yv-lip-001-brick-petal",
];
const petalVelvet = sourceById.get("yv-lip-001");
assert(petalVelvetIds.length === 8 && new Set(petalVelvetIds).size === 8, "Petal Velvet storefront assortment must contain eight distinct shades");
assert(petalVelvetIds.every((id) => petalVelvet?.variants?.some((variant) => variant.id === id)), "Petal Velvet storefront shades must belong to Petal Velvet's own source record");

const velvetstem = processedProducts.find((product) => product.id === "yv-lip-006");
const clayLine = velvetstem?.variants?.find((variant) => variant.id === "yv-lip-006-clay-line");
assert(clayLine?.shade?.name === "Clay Line", "Velvetstem Clay Line must retain its own name");
assert(clayLine?.id !== "yv-lip-006-berry-root", "Velvetstem Clay Line must not resolve to Berry Root");

for (const id of ["yv-eye-013", "yv-eye-014", "yv-eye-015"]) {
  const product = sourceById.get(id);
  assert(Array.isArray(product?.palette_colors) && product.palette_colors.length > 0, `${id} must have included palette shades`);
  assert(product?.palette_colors?.every((shade) => shade.name?.trim()), `${id} has an empty included shade name`);
}

const assetFiles = ["lib/makeup-assets.ts", "lib/makeup-variant-images.ts"];
for (const relativePath of assetFiles) {
  const source = readFileSync(join(webRoot, relativePath), "utf8");
  const imagePaths = [...source.matchAll(/"(\/images\/[^"\n]+)"/g)].map((match) => match[1]);
  for (const imagePath of imagePaths) {
    assert(imagePath.startsWith("/images/"), `${relativePath} contains a non-public image path: ${imagePath}`);
    const localPath = join(webRoot, "public", decodeURIComponent(imagePath));
    assert(existsSync(localPath), `${relativePath} references missing image: ${imagePath}`);
  }
}

if (errors.length) {
  console.error("Catalogue validation failed:\n- " + errors.join("\n- "));
  process.exit(1);
}

console.log(`Catalogue validation passed (${authoritativeProducts.length} canonical products).`);
