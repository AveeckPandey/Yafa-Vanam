import type { CatalogProduct, CatalogVariant } from "./catalog-types";

function questionMatching(questions: string[], expression: RegExp) {
  return questions.find((question) => expression.test(question)) ?? null;
}

/** Product-page prompts stay grounded in the product's RAG-backed question set. */
export function getYafaProductQuestions(
  product: CatalogProduct,
  selectedShade: CatalogVariant["shade"],
) {
  const productQuestions = product.ragQuestions.map((item) => item.question).filter(Boolean);
  const routine = questionMatching(productQuestions, /routine|use|apply/i);
  const finish = questionMatching(productQuestions, /finish|look|coverage|result/i);

  if (product.makeupGroup === "lips") {
    return [
      selectedShade
        ? `How will ${selectedShade.name} work with my undertone?`
        : `Which shade of ${product.name} suits my undertone?`,
      finish ?? `What finish or look is ${product.name} designed for?`,
      routine ?? `How should I apply ${product.name} for even colour?`,
    ];
  }

  if (product.skincareGroup) {
    return [
      questionMatching(productQuestions, /skin type|best for|concern|benefit/i) ?? `Which skin types is ${product.name} best for?`,
      questionMatching(productQuestions, /ingredient/i) ?? `Which ingredients in ${product.name} should I know about?`,
      routine ?? `Where does ${product.name} fit in my routine?`,
    ];
  }

  return productQuestions.slice(0, 3).length
    ? productQuestions.slice(0, 3)
    : [
        `What is ${product.name} designed for?`,
        finish ?? `What result can I expect from ${product.name}?`,
        routine ?? `How should I use ${product.name}?`,
      ];
}
