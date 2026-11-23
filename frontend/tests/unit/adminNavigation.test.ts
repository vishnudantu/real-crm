import test from "node:test";
import assert from "node:assert/strict";
import {
  buildAdminMobileNav,
  buildAdminNav,
  resolveSettingsTab,
} from "../../src/admin/adminNavigation.ts";

const allFeatures = {
  analytics: true,
  omnichannel_inbox: true,
  post_sales: true,
};

function pathsByGroup(features: Record<string, boolean>): string[][] {
  return buildAdminNav(features).map((group) =>
    group.items.map((item) => item.to),
  );
}

test("keeps core navigation in stable labeled groups when all optional features are off", () => {
  const groups = buildAdminNav({});

  assert.deepEqual(
    groups.map((group) => group.label),
    ["Overview", "Engage", "Catalog", "Customers", "Operations", "Property", "Team", "Revenue", "System"],
  );
  assert.deepEqual(pathsByGroup({}), [
    ["/admin"],
    ["/admin/notifications"],
    ["/admin/projects", "/admin/visits", "/admin/construction"],
    ["/admin/customers", "/admin/opportunities", "/admin/brokers"],
    ["/admin/approvals", "/admin/service-desk", "/admin/call-intelligence"],
    ["/admin/inventory", "/admin/inventory/units"],
    ["/admin/teamchat", "/admin/users"],
    ["/admin/documents", "/admin/reconciliation"],
    ["/admin/settings", "/admin/audit-logs", "/admin/account"],
  ]);
});

test("shows Inbox, Channels and Widget only when omnichannel is enabled", () => {
  const groups = buildAdminNav({ omnichannel_inbox: true });
  const items = groups.flatMap((group) => group.items);
  const settings = items.find((item) => item.to === "/admin/settings");

  assert.ok(items.some((item) => item.to === "/admin/inbox"));
  assert.ok(items.some((item) => item.to === "/admin/channels"));
  assert.ok(
    settings?.children?.some((child) => child.to === "/admin/settings/widget"),
  );
  assert.equal(groups.at(-2)?.label, "Integrate");
  assert.ok(
    !buildAdminNav({})
      .flatMap((group) => group.items)
      .some((item) => item.to === "/admin/channels"),
  );
  assert.ok(
    !buildAdminNav({})
      .flatMap((group) => group.items)
      .find((item) => item.to === "/admin/settings")
      ?.children?.some((child) => child.to === "/admin/settings/widget"),
  );
});

test("gates Analytics and Sales Bookings independently", () => {
  assert.ok(
    !pathsByGroup({}).flat().includes("/admin/sales-bookings"),
  );
  assert.ok(
    pathsByGroup({ post_sales: true }).flat().includes("/admin/sales-bookings"),
  );
  assert.ok(pathsByGroup({}).flat().includes("/admin/analytics") === false);
  assert.ok(
    pathsByGroup({ analytics: true }).flat().includes("/admin/analytics"),
  );
});

test("returns fresh groups and preserves ordering with every feature enabled", () => {
  const first = buildAdminNav(allFeatures);
  const second = buildAdminNav(allFeatures);

  assert.deepEqual(first, second);
  assert.notEqual(first, second);
  assert.notEqual(first[0], second[0]);
  assert.notEqual(first[0].items, second[0].items);
  assert.deepEqual(
    first.map((group) => group.label),
    ["Overview", "Engage", "Catalog", "Customers", "Operations", "Property", "Team", "Revenue", "Integrate", "System"],
  );
  const revenue = first.find((group) => group.label === "Revenue");
  assert.deepEqual(revenue?.items.map((item) => item.to), [
    "/admin/analytics",
    "/admin/sales-bookings",
    "/admin/documents",
    "/admin/reconciliation",
  ]);
});

test("keeps the Documents library visible regardless of feature flags", () => {
  assert.ok(pathsByGroup({}).flat().includes("/admin/documents"));
  assert.ok(pathsByGroup(allFeatures).flat().includes("/admin/documents"));
});

test("caps mobile quick navigation at five with the most-used destinations", () => {
  const items = buildAdminMobileNav(allFeatures);

  assert.equal(items.length, 5);
  assert.deepEqual(items.map((item) => item.to), [
    "/admin",
    "/admin/inbox",
    "/admin/projects",
    "/admin/visits",
    "/admin/account",
  ]);
});

test("falls back to Projects when Inbox is not enabled", () => {
  const items = buildAdminMobileNav({});

  assert.equal(items.length, 5);
  assert.deepEqual(items.map((item) => item.to), [
    "/admin",
    "/admin/projects",
    "/admin/visits",
    "/admin/notifications",
    "/admin/account",
  ]);
});

test("maps settings path segments to tabs without accepting unknown paths", () => {
  assert.equal(resolveSettingsTab("/admin/settings"), "branding");
  assert.equal(resolveSettingsTab("/admin/settings/ai"), "ai_assistant");
  assert.equal(resolveSettingsTab("/admin/settings/languages"), "languages");
  assert.equal(resolveSettingsTab("/admin/settings/assignment"), "lead_assignment");
  assert.equal(resolveSettingsTab("/admin/settings/widget"), "widget");
  assert.equal(resolveSettingsTab("/admin/settings/not-a-tab"), "branding");
});
