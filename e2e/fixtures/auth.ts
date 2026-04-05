import { type Page } from "@playwright/test";
import axios from "axios";

const API_URL = "http://localhost:8000";

export interface TestUser {
  email: string;
  password: string;
  accessToken: string;
}

let userCounter = 0;

export async function createTestUser(): Promise<TestUser> {
  const email = `e2e-${Date.now()}-${userCounter++}@test.com`;
  const password = "testpass123";

  await axios.post(`${API_URL}/api/auth/register`, { email, password });

  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const loginResp = await axios.post(`${API_URL}/api/auth/login`, form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });

  return { email, password, accessToken: loginResp.data.access_token };
}

export async function loginViaUI(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await page.waitForURL("**/dashboard");
}

export async function registerViaUI(page: Page, email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign up|register|create/i }).click();
}
