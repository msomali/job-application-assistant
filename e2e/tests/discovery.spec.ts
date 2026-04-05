import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Discovery", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/discover");
  });

  test("discover page loads", async ({ page }) => {
    await expect(page.getByText(/discover/i)).toBeVisible();
  });

  test("add config button exists", async ({ page }) => {
    await expect(page.getByRole("button", { name: /add|new|config/i })).toBeVisible();
  });
});
