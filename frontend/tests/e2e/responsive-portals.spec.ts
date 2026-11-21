import { test, expect, devices } from "@playwright/test";

const API = "http://127.0.0.1:8000/api/v1";

async function mockBase(page: import("@playwright/test").Page) {
  await page.route(`${API}/**`, async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "NOT_FOUND", message: "not mocked" } }),
    });
  });
}

for (const [label, viewport] of [
  ["mobile", { width: 390, height: 844 }],
  ["desktop", { width: 1440, height: 900 }],
] as const) {
  test.describe(`${label} layout`, () => {
    test.use({ viewport });

    test("landing page renders hero and navigation without horizontal overflow", async ({ page }) => {
      await mockBase(page);
      await page.goto("/");
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      expect(overflow).toBe(false);
    });

    test("login page renders credentials form at this viewport", async ({ page }) => {
      await mockBase(page);
      await page.goto("/login");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Sign in/i);
      await expect(page.locator("#email")).toBeVisible();
      await expect(page.locator("#password")).toBeVisible();
      await expect(page.getByRole("button", { name: /^Sign in$/i })).toBeVisible();
    });
  });
}

test("operator login page renders", async ({ page }) => {
  await mockBase(page);
  await page.goto("/operator/login");
  await expect(page.locator("#operator-email")).toBeVisible();
  await expect(page.locator("#operator-password")).toBeVisible();
});
