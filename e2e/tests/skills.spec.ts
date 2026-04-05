import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Skills", () => {
  test("skills page loads with tabs", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/skills");
    await expect(page.getByText(/skills/i)).toBeVisible();
  });
});
