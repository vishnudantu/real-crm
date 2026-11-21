import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_BRANDING,
  accessiblePrimaryColor,
  brandingStyles,
  contrastRatio,
  normalizeBranding,
  normalizeTenantSlug,
} from "../../src/tenant/branding.ts";
import { profileMatchesTenant } from "../../src/tenant/profile.ts";

test("returns the current PropFlow defaults when branding is unavailable", () => {
  assert.deepEqual(normalizeBranding(null), { ...DEFAULT_BRANDING });
  assert.equal(normalizeTenantSlug(""), "default");
  assert.equal(normalizeTenantSlug("not a tenant!"), "default");
});

test("normalizes public branding without accepting user storage or mismatched responses", () => {
  assert.deepEqual(
    normalizeBranding(
      {
        id: "tenant-a",
        brand_name: "Acme Homes",
        primary_color: "#ffffff",
        logo_url: "https://cdn.example.test/logo.svg",
        default_dark_mode: true,
        currency: "USD",
        timezone: "UTC",
        date_format: "MM/dd/yyyy",
      },
      undefined,
      "acme",
    ),
    {
      id: "tenant-a",
      slug: "acme",
      brand_name: "Acme Homes",
      logo_url: "https://cdn.example.test/logo.svg",
      primary_color: "#FFFFFF",
      theme: "light",
      default_dark_mode: true,
      currency: "USD",
      timezone: "UTC",
      date_format: "MM/dd/yyyy",
    },
  );

  assert.equal(
    normalizeBranding({ slug: "other", brand_name: "Other" }, undefined, "acme").brand_name,
    "PropFlow",
  );
  assert.equal(
    normalizeBranding({ brand_name: "Acme", logo_url: "javascript:alert(1)" }).logo_url,
    null,
  );
  assert.equal(normalizeBranding({ currency: "NOTREAL" }).currency, "INR");
  assert.equal(normalizeBranding({ timezone: "Invalid/Zone" }).timezone, "Asia/Kolkata");
  assert.equal(normalizeBranding({ brand_name: 42 }).brand_name, "PropFlow");
});

test("maps the backend nested theme contract and preserves tenant slug", () => {
  const result = normalizeBranding({
    slug: "acme",
    brand_name: "Acme Realty",
    logo_path: "/media/tenants/acme/logo.svg",
    theme: { primary: "#123456", accent: "#C5A77D", default_color_scheme: "dark" },
    currency: "INR",
    timezone: "Asia/Kolkata",
    date_format: "DD/MM/YYYY",
  }, undefined, "acme");
  assert.equal(result.slug, "acme");
  assert.equal(result.brand_name, "Acme Realty");
  assert.equal(result.logo_url, "/media/tenants/acme/logo.svg");
  assert.equal(result.primary_color, "#123456");
  assert.equal(result.default_dark_mode, true);
  assert.equal(result.date_format, "DD/MM/YYYY");

  const authenticated = normalizeBranding({ slug: "acme", brand_name: "Acme Realty" });
  assert.equal(authenticated.slug, "acme");
  assert.equal(authenticated.brand_name, "Acme Realty");
});

test("provides accessible dynamic CSS variables without changing the base palette", () => {
  const color = accessiblePrimaryColor("#ffffff");
  assert.ok(contrastRatio(color, "#F5F2EB") >= 4.5);
  assert.equal(brandingStyles({ ...DEFAULT_BRANDING, primary_color: color })["--brand-primary-accessible"], color);
  const defaultStyles = brandingStyles(DEFAULT_BRANDING);
  assert.ok(contrastRatio(defaultStyles["--brand-primary-accessible"], "#F5F2EB") >= 4.5);
  assert.ok(contrastRatio(defaultStyles["--brand-on-primary"], DEFAULT_BRANDING.primary_color) >= 4.5);
});

test("keeps legacy profiles compatible and rejects only known tenant mismatches", () => {
  assert.equal(profileMatchesTenant(undefined, "tenant-a"), true);
  assert.equal(profileMatchesTenant("tenant-a", null), true);
  assert.equal(profileMatchesTenant("tenant-a", "tenant-a"), true);
  assert.equal(profileMatchesTenant("tenant-b", "tenant-a"), false);
});
