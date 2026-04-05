import { test, expect } from "@playwright/test";

const email = `auth-${Date.now()}@test.com`;
const password = "testpass123";

test.describe("Auth", () => {
  test("register new account", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up|register|create/i }).click();
    // After registration, user should be redirected to login or auto-logged in
    await expect(page).toHaveURL(/\/(login|dashboard)/);
  });

  test("login with valid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("wrong@test.com");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page.getByText(/invalid|failed|error/i)).toBeVisible({ timeout: 5000 });
  });

  test("logout redirects to login", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");

    // Logout via user menu
    await page.getByRole("button", { name: /avatar|user/i }).first().click();
    await page.getByText("Sign out").click();
    await expect(page).toHaveURL("**/login");
  });

  test("refresh token preserves session across reload", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");

    await page.reload();
    await expect(page).toHaveURL("**/dashboard", { timeout: 5000 });
  });
});
