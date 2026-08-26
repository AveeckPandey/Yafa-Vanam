import { expect, test } from "@playwright/test";

test("shop search, filters, and recovery-voucher protection are available", async ({ page }) => {
  await page.goto("/shop");
  await expect(page.locator("#shop-title")).toBeVisible();
  await expect(page.getByRole("button", { name: "Quick Shop" }).first()).toBeVisible();

  await page.goto("/search?q=lip");
  await expect(page.getByRole("textbox", { name: "Search" })).toHaveValue("lip");
  await expect(page.locator("main")).toContainText(/result/i);

  await page.goto("/checkout");
  await expect(page.locator("#checkout-email")).toBeVisible();
  // Recovery vouchers are deliberately unavailable to guests: a copied code
  // must not be redeemable without the account it belongs to.
  await expect(page.getByLabel(/YV_20 code/i)).toHaveCount(0);
});

test("sign-up, sign-in, and password-reset pages render usable forms", async ({ page }) => {
  await page.goto("/auth/sign-up");
  await expect(page.getByRole("heading", { name: /create your account/i })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Email", exact: true })).toBeVisible();
  await expect(page.getByLabel("Birthday")).toBeVisible();

  await page.goto("/auth/sign-in");
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  await page.goto("/auth/reset-password");
  await expect(page.getByRole("heading", { name: /choose a new password/i })).toBeVisible();
});

test("mobile storefront has no horizontal overflow", async ({ page }) => {
  await page.goto("/shop");
  await expect(page.getByRole("button", { name: "Quick Shop" }).first()).toBeVisible();
  const overflow = await page.locator("html").evaluate((element) => element.scrollWidth > element.clientWidth);
  expect(overflow).toBeFalsy();
});
