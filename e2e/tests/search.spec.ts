import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Search", () => {
  test("search page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/search");
    await expect(page.getByPlaceholder(/search|query/i)).toBeVisible();
  });
});
