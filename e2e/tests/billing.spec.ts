import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Billing", () => {
  test("billing overview loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/billing");
    await expect(page.getByText(/billing|plan/i)).toBeVisible();
  });

  test("plans page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/billing/plans");
    await expect(page.getByText(/free|starter|pro/i)).toBeVisible();
  });
});
