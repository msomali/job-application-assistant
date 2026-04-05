import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Profile", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/profile");
  });

  test("profile page loads with name field", async ({ page }) => {
    await expect(page.getByLabel(/full name|name/i)).toBeVisible();
  });

  test("import button exists", async ({ page }) => {
    await expect(page.getByRole("button", { name: /import/i })).toBeVisible();
  });
});
