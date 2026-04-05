import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Task Panel", () => {
  test("task badge is visible in nav", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await expect(page.getByLabel(/active tasks/i)).toBeVisible();
  });

  test("clicking task badge opens drawer", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.getByLabel(/active tasks/i).click();
    await expect(page.getByText(/tasks/i)).toBeVisible();
    await expect(page.getByText(/no tasks yet/i)).toBeVisible();
  });
});
