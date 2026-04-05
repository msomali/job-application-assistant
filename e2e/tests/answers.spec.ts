import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Answers", () => {
  test("answers page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/answers");
    await expect(page.getByText(/answers/i)).toBeVisible();
  });

  test("add answer button exists", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/answers");
    await expect(page.getByRole("button", { name: /add/i })).toBeVisible();
  });
});
