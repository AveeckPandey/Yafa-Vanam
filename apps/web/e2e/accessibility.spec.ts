import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  { name: "home", path: "/" },
  { name: "shop", path: "/shop" },
  { name: "checkout", path: "/checkout" },
  { name: "sign-up", path: "/auth/sign-up" },
];

for (const target of pages) {
  test(`${target.name} meets WCAG 2.1 AA automated checks`, async ({ page }) => {
    await page.goto(target.path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();

    expect(results.violations, results.violations.map((violation) => `${violation.id}: ${violation.help}`).join("\n")).toEqual([]);
  });
}
