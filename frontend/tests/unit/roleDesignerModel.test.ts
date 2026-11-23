import test from "node:test";
import assert from "node:assert/strict";
import type { PermissionItem } from "../../src/admin/roles/roleDesignerModel.ts";
import {
  MAX_CUSTOM_ROLE_PERMISSIONS,
  areaLabel,
  assignableKeys,
  describeApiFailure,
  groupPermissions,
  isAssignable,
  summarizePermissions,
  togglePermission,
  validateRoleDraft,
} from "../../src/admin/roles/roleDesignerModel.ts";

function perm(overrides: Partial<PermissionItem>): PermissionItem {
  return {
    key: "inventory.read",
    area: "inventory",
    description: "View property units.",
    grantable: true,
    enabled: true,
    ...overrides,
  };
}

const REGISTRY: PermissionItem[] = [
  perm({ key: "inventory.write", description: "Write units." }),
  perm({ key: "inventory.read", description: "Read units." }),
  perm({ key: "projects.read", area: "projects", description: "Read projects." }),
  perm({ key: "roles.manage", area: "roles", grantable: false, enabled: false }),
  perm({ key: "operator.access", area: "operator", grantable: false, enabled: false }),
];

test("groupPermissions sorts areas alphabetically and keys within each area", () => {
  const groups = groupPermissions(REGISTRY);
  assert.deepEqual(groups.map((g) => g.area), ["inventory", "operator", "projects", "roles"]);
  const inventory = groups.find((g) => g.area === "inventory");
  assert.deepEqual(inventory?.permissions.map((p) => p.key), ["inventory.read", "inventory.write"]);
});

test("groupPermissions does not mutate the input array or its items", () => {
  const before = [...REGISTRY];
  const groups = groupPermissions(REGISTRY);
  assert.deepEqual(REGISTRY, before);
  assert.notEqual(groups[0]?.permissions[0], REGISTRY[0]);
});

test("isAssignable mirrors the backend grantable flag", () => {
  assert.equal(isAssignable(perm({})), true);
  assert.equal(isAssignable(perm({ grantable: false })), false);
});

test("assignableKeys returns only grantable keys", () => {
  assert.deepEqual(assignableKeys(REGISTRY), [
    "inventory.write",
    "inventory.read",
    "projects.read",
  ]);
});

test("togglePermission adds and removes keys immutably", () => {
  const original = ["inventory.read"];
  const added = togglePermission(original, "inventory.write", true);
  assert.deepEqual(added, ["inventory.read", "inventory.write"]);
  assert.deepEqual(original, ["inventory.read"]);
  const removed = togglePermission(added, "inventory.read", true);
  assert.deepEqual(removed, ["inventory.write"]);
});

test("togglePermission ignores protected keys", () => {
  const original = ["inventory.read"];
  assert.deepEqual(togglePermission(original, "roles.manage", false), ["inventory.read"]);
});

test("areaLabel prettifies underscore-separated area names", () => {
  assert.equal(areaLabel("inventory"), "Inventory");
  assert.equal(areaLabel("service_desk"), "Service Desk");
  assert.equal(areaLabel("settings"), "Settings");
});

test("validateRoleDraft rejects empty or whitespace-only names", () => {
  assert.match(validateRoleDraft({ name: "", description: "", permissions: [] }) ?? "", /at least/);
  assert.match(validateRoleDraft({ name: " ", description: "", permissions: [] }) ?? "", /at least/);
  assert.match(validateRoleDraft({ name: "a", description: "", permissions: [] }) ?? "", /at least/);
});

test("validateRoleDraft accepts a minimal valid draft", () => {
  assert.equal(validateRoleDraft({ name: "Sales Lead", description: "", permissions: [] }), null);
});

test("validateRoleDraft enforces the permission cap", () => {
  const tooMany = Array.from({ length: MAX_CUSTOM_ROLE_PERMISSIONS + 1 }, (_, i) => `a.${i}`);
  assert.match(validateRoleDraft({ name: "Big", description: "", permissions: tooMany }) ?? "", /at most/);
});

test("validateRoleDraft enforces name and description limits", () => {
  assert.match(validateRoleDraft({ name: "x".repeat(65), description: "", permissions: [] }) ?? "", /64/);
  assert.match(validateRoleDraft({ name: "ok", description: "y".repeat(256), permissions: [] }) ?? "", /255/);
});

test("summarizePermissions groups selected keys by area with readable labels", () => {
  const text = summarizePermissions(["inventory.read", "projects.read", "inventory.write"], REGISTRY);
  assert.match(text, /Inventory: read, write/);
  assert.match(text, /Projects: read/);
});

test("summarizePermissions returns a placeholder for no selection", () => {
  assert.equal(summarizePermissions([], REGISTRY), "No permissions yet");
});

test("describeApiFailure returns the error message or the fallback", () => {
  assert.equal(describeApiFailure(new Error("Duplicate name."), "fallback"), "Duplicate name.");
  assert.equal(describeApiFailure(null, "fallback"), "fallback");
  assert.equal(describeApiFailure("string", "fallback"), "fallback");
});
