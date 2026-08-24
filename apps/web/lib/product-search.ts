export type SearchIndexProduct = {
  id: string;
  slug: string;
  name: string;
  category: string;
  subcategory: string;
  productType: string;
  shortDescription: string;
  benefits: string[];
  currency: string;
  price: number;
  image: string;
  imageAlt: string;
  // Lowercase catch-all: subcategory, product type, benefits, skin types and
  // primary concerns, so concern-led queries such as “sensitive skin” match.
  keywords: string;
};

// Number of image-led results shown inside the header search panel.
export const HEADER_SEARCH_LIMIT = 4;

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeSearchText(value: string) {
  return value
    .toLowerCase()
    .replace(/colou?r/g, "color")
    .replace(/moisturi[sz]er/g, "moisturizer")
    .replace(/make[\s-]?up/g, "makeup")
    .replace(/skin[\s-]?care/g, "skincare");
}

// Matches partial words as visitors type and tolerates plural terms.
function tokenPattern(token: string) {
  return new RegExp(`${escapeRegExp(token)}s?`);
}

type FieldScore = [value: string, weight: number];

function scoreToken(pattern: RegExp, fields: FieldScore[]) {
  let best = 0;
  for (const [value, weight] of fields) {
    if (pattern.test(value)) {
      best = Math.max(best, weight);
    }
  }
  return best;
}

/**
 * Deterministic token-aware ranking over the lightweight search index.
 * Every token must match somewhere; stronger fields (name, product type)
 * outweigh the keyword catch-all.
 */
export function searchIndexProducts(products: SearchIndexProduct[], query: string): SearchIndexProduct[] {
  const term = normalizeSearchText(query.trim());
  const tokens = term.split(/[^a-z0-9]+/).filter(Boolean);
  if (!tokens.length) return [];

  const scored: Array<{ product: SearchIndexProduct; score: number }> = [];

  for (const product of products) {
    const name = normalizeSearchText(product.name);
    const productType = normalizeSearchText(product.productType);
    const subcategory = normalizeSearchText(product.subcategory);
    const category = normalizeSearchText(product.category);
    const description = normalizeSearchText(product.shortDescription);
    const keywords = normalizeSearchText(product.keywords);

    let score = 0;
    if (name.startsWith(term)) score += 120;
    else if (name.includes(term)) score += 80;

    let total = 0;
    for (const token of tokens) {
      const pattern = tokenPattern(token);
      const tokenScore = scoreToken(pattern, [
        [name, 20],
        [productType, 12],
        [subcategory, 10],
        [category, 8],
        [description, 5],
        [keywords, 3],
      ]);
      if (!tokenScore) {
        total = 0;
        break;
      }
      total += tokenScore;
    }

    if (total) scored.push({ product, score: score + total });
  }

  return scored
    .sort((a, b) => b.score - a.score || a.product.name.localeCompare(b.product.name))
    .map(({ product }) => product);
}
