import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Jobs", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/jobs");
  });

  test("job list page loads", async ({ page }) => {
    await expect(page.getByText(/jobs/i)).toBeVisible();
  });

  test("search input exists", async ({ page }) => {
    await expect(page.getByPlaceholder(/search/i)).toBeVisible();
  });

  test("sort select exists", async ({ page }) => {
    await expect(page.getByText(/scraped_at|sort/i)).toBeVisible();
  });
});
