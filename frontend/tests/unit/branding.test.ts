import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_BRANDING,
  DEFAULT_TENANT_SLUG,
  accessiblePrimaryColor,
  brandingStyles,
  contrastRatio,
  isTenantBranded,
  normalizeBranding,
  normalizeTenantSlug,
  parseTenantOverride,
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

test("parseTenantOverride: query parameter wins over session and env", () => {
  assert.equal(
    parseTenantOverride("?tenant=acme", "stored-tenant", "env-tenant"),
    "acme",
  );
  assert.equal(
    parseTenantOverride("?tenant=Acme", null, null),
    "acme",
    "uppercase query slugs are normalized",
  );
});

test("parseTenantOverride: session value wins over env when no query", () => {
  assert.equal(
    parseTenantOverride("", "stored-tenant", "env-tenant"),
    "stored-tenant",
  );
  assert.equal(
    parseTenantOverride(null, "stored-tenant", "env-tenant"),
    "stored-tenant",
  );
});

test("parseTenantOverride: env used when no query or session", () => {
  assert.equal(parseTenantOverride("", null, "env-tenant"), "env-tenant");
  assert.equal(parseTenantOverride("", "", "env-tenant"), "env-tenant");
});

test("parseTenantOverride: returns null when no override is present", () => {
  assert.equal(parseTenantOverride("", null, null), null);
  assert.equal(parseTenantOverride("", null, ""), null);
  assert.equal(parseTenantOverride("", null, DEFAULT_TENANT_SLUG), null);
});

test("parseTenantOverride: ?tenant=default clears any stored/env override", () => {
  assert.equal(
    parseTenantOverride("?tenant=default", "stored-tenant", "env-tenant"),
    null,
  );
  assert.equal(
    parseTenantOverride("?tenant=DEFAULT", "stored-tenant", "env-tenant"),
    null,
    "default is matched case-insensitively after normalization",
  );
});

test("parseTenantOverride: invalid slug in query clears override", () => {
  assert.equal(
    parseTenantOverride("?tenant=not valid!", "stored-tenant", "env-tenant"),
    null,
  );
  assert.equal(
    parseTenantOverride("?tenant=", "stored-tenant", "env-tenant"),
    null,
  );
});

test("parseTenantOverride: invalid session and env values are ignored", () => {
  assert.equal(
    parseTenantOverride("", "not valid!", "env-tenant"),
    "env-tenant",
  );
  assert.equal(parseTenantOverride("", "bad value", "also bad!"), null);
});

test("parseTenantOverride: reads tenant param among other query params", () => {
  assert.equal(
    parseTenantOverride("?foo=bar&tenant=skyline-dev&baz=1", null, null),
    "skyline-dev",
  );
  assert.equal(
    parseTenantOverride("?foo=bar", null, "env-tenant"),
    "env-tenant",
  );
});

test("isTenantBranded: true only for real tenant payloads with id", () => {
  assert.equal(isTenantBranded(DEFAULT_BRANDING), false);
  assert.equal(
    isTenantBranded({ ...DEFAULT_BRANDING, id: "tenant-123", brand_name: "Acme" }),
    true,
  );
  assert.equal(isTenantBranded({ ...DEFAULT_BRANDING, brand_name: "Acme" }), false);
});
