import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

const API = "http://127.0.0.1:8000/api/v1";
const response = (body: unknown, status = 200) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});
const admin = {
  id: "user-1",
  tenant_id: "tenant-acme",
  full_name: "Admin User",
  email: "admin@example.test",
  phone: null,
  role: { id: "role-admin", name: "ADMIN", description: null },
  is_active: true,
  is_verified: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// Mirrors GET /api/v1/tenancy/settings and /tenancy/public/{slug} responses.
const acmeBranding = {
  slug: "acme",
  brand_name: "Acme Homes",
  logo_path: null,
  theme: { primary: "#123456", accent: "#C5A77D", default_color_scheme: "light" },
  currency: "USD",
  timezone: "UTC",
  date_format: "DD/MM/YYYY",
};

async function mockApi(page: Page, tenant: string, branding: Record<string, unknown>) {
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === `/api/v1/tenancy/public/${tenant}`) {
      await route.fulfill(response(branding));
      return;
    }
    if (path === "/api/v1/auth/me") {
      await route.fulfill(response(admin));
      return;
    }
    if (path === "/api/v1/tenancy/settings" && request.method() === "GET") {
      await route.fulfill(response(branding));
      return;
    }
    if (path === "/api/v1/tenancy/settings" && request.method() === "PUT") {
      await route.fulfill(response({ ...branding, ...JSON.parse(request.postData() || "{}") }));
      return;
    }
    await route.fulfill(response({ error: { code: "NOT_IMPLEMENTED", message: "Not mocked" } }, 404));
  });
}

test("configured tenant brand and color replace the PropFlow landing defaults", async ({ page }) => {
  test.info().annotations.push({ type: "tenant-slug", description: "acme" });
  await page.route(`${API}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith("/api/v1/tenancy/public/")) {
      await route.fulfill(response(acmeBranding));
    } else {
      await route.fulfill(response({ error: { code: "NOT_IMPLEMENTED" } }, 404));
    }
  });
  await page.goto("/");
  await expect(page.getByRole("main")).toContainText("Acme Homes");
  await expect
    .poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--brand-primary")))
    .toBe("#123456");
});

test("unavailable public branding falls back to PropFlow without blocking the app", async ({ page }) => {
  await page.route(`${API}/tenancy/public/default`, (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
  );
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sign in to PropFlow.");
  await expect(page.getByRole("link", { name: "PropFlow home" }).first()).toHaveAttribute("href", "/");
  await expect(page).toHaveTitle("Sign in — PropFlow");
});

test("admin saves branding with the current session and nested theme payload", async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("propflow.auth.access-token", "test-bearer-token");
    sessionStorage.setItem("propflow.auth.access-token-expires-at", String(Date.now() + 3600_000));
  });

  let saved: Record<string, unknown> | undefined;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/me") {
      await route.fulfill(response(admin));
      return;
    }
    if (path === "/api/v1/tenancy/settings" && request.method() === "PUT") {
      expect(request.headers()).toHaveProperty("authorization", "Bearer test-bearer-token");
      saved = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill(response({ ...acmeBranding, ...(saved ?? {}) }));
      return;
    }
    if (path.startsWith("/api/v1/tenancy/")) {
      await route.fulfill(response(acmeBranding));
      return;
    }
    await route.fulfill(response({ error: { code: "NOT_IMPLEMENTED", message: "Not mocked" } }, 404));
  });

  await page.goto("/admin/settings?tab=branding");
  await expect(page.getByRole("button", { name: "Save branding settings" })).toBeEnabled();
  await page.getByLabel("Brand name").fill("Acme Living");
  await page.getByLabel("Use dark mode by default for new visitors").check();
  await page.getByRole("button", { name: "Save branding settings" }).click();
  await expect(page.getByText("Tenant branding settings updated successfully.")).toBeVisible();

  expect(saved).toBeDefined();
  const theme = saved!.theme as Record<string, unknown>;
  expect(saved!.brand_name).toBe("Acme Living");
  expect(theme.primary).toBe("#123456");
  expect(theme.default_color_scheme).toBe("dark");
});
