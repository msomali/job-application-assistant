import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Telegram Settings", () => {
  test("connect telegram button exists", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/settings");
    await expect(page.getByRole("button", { name: /connect telegram/i })).toBeVisible();
  });
});
