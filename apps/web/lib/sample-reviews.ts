import type { CatalogProduct } from "./catalog-types";

export type SampleReview = {
  id: string;
  rating: number;
  title: string;
  body: string;
  displayName: string;
};

const categoryCopy: Record<string, Array<[number, string, string]>> = {
  Makeup: [
    [5, "Easy to explore", "Sample text showing how a customer might discuss shade selection, finish and wear. Replace this with a moderated verified-purchase review."],
    [4, "Thoughtful presentation", "Sample text showing how a customer might describe application and how the product layers with the rest of their routine."],
    [5, "A considered choice", "Sample text showing how a customer might mention packaging, colour and the product information that helped them choose."],
  ],
  Skincare: [
    [5, "Clear ritual", "Sample text showing how a customer might discuss texture, application and where the product fits in their routine without making clinical claims."],
    [4, "Helpful details", "Sample text showing how a customer might describe the instructions, ingredient information and overall experience."],
    [5, "Beautifully presented", "Sample text showing how a customer might comment on packaging and day-to-day usability after a verified purchase."],
  ],
  Fragrance: [
    [5, "A distinctive character", "Sample text showing how a customer might describe the scent family, opening and dry-down in their own words."],
    [4, "Easy to understand", "Sample text showing how a customer might discuss occasion, intensity and personal scent preferences."],
    [5, "A lovely ritual", "Sample text showing how a customer might comment on presentation and their subjective fragrance experience."],
  ],
  "Body Care": [
    [5, "A simple daily ritual", "Sample text showing how a customer might describe texture, application and packaging after using the product."],
    [4, "Thoughtful details", "Sample text showing how a customer might discuss instructions and how the product fits into a body-care routine."],
    [5, "Beautiful presentation", "Sample text showing how a customer might comment on usability and their personal experience without unsupported claims."],
  ],
};

const fallback = categoryCopy.Skincare;

export function getSampleReviews(product: CatalogProduct): SampleReview[] {
  return (categoryCopy[product.category] ?? fallback).map(([rating, title, body], index) => ({
    id: `${product.id}-sample-${index + 1}`,
    rating,
    title,
    body,
    displayName: `Sample customer ${index + 1}`,
  }));
}
