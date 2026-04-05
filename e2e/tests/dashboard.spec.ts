import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
  });

  test("stats cards render", async ({ page }) => {
    await expect(page.getByText(/total jobs/i)).toBeVisible();
    await expect(page.getByText(/avg fit/i)).toBeVisible();
  });

  test("quick scrape bar is visible", async ({ page }) => {
    await expect(page.getByPlaceholder(/paste.*url/i)).toBeVisible();
  });
});
