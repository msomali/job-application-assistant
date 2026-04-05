import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Settings", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/settings");
  });

  test("account section shows email", async ({ page }) => {
    await expect(page.getByText(/account/i)).toBeVisible();
    await expect(page.getByText(/@test\.com/i)).toBeVisible();
  });

  test("theme toggle exists", async ({ page }) => {
    await expect(page.getByText(/theme/i)).toBeVisible();
  });

  test("telegram section exists", async ({ page }) => {
    await expect(page.getByText(/telegram/i)).toBeVisible();
  });

  test("notification section exists", async ({ page }) => {
    await expect(page.getByText(/notification/i)).toBeVisible();
  });
});
