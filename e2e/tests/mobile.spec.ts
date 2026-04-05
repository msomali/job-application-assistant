import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.use({ viewport: { width: 375, height: 812 } });

test.describe("Mobile Layout", () => {
  test("bottom nav is visible on mobile", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await expect(page.locator("nav.fixed")).toBeVisible();
    await expect(page.getByText("Home")).toBeVisible();
    await expect(page.getByText("Jobs")).toBeVisible();
  });

  test("icon rail is hidden on mobile", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    // Icon rail should not be visible on mobile
    const rail = page.locator("nav.group\\/rail");
    await expect(rail).toBeHidden();
  });

  test("more menu opens bottom sheet", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.getByText("More").click();
    await expect(page.getByText(/settings/i)).toBeVisible();
    await expect(page.getByText(/billing/i)).toBeVisible();
  });
});
