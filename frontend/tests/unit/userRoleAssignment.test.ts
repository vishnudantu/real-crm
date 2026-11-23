import test from "node:test";
import assert from "node:assert/strict";
import {
  createRoleAssignmentFields,
  updateRoleAssignmentFields,
} from "../../src/admin/adminModel.ts";

const CUSTOM_A = "00000000-0000-0000-0000-00000000000a";
const CUSTOM_B = "00000000-0000-0000-0000-00000000000b";

test("create with a built-in role sends the role and an explicit null custom_role_id", () => {
  assert.deepEqual(createRoleAssignmentFields({ kind: "builtin", role: "ADMIN" }), {
    role: "ADMIN",
    custom_role_id: null,
  });
});

test("create with a custom role layers it on a SALES_EXECUTIVE base account", () => {
  assert.deepEqual(createRoleAssignmentFields({ kind: "custom", customRoleId: CUSTOM_A }), {
    role: "SALES_EXECUTIVE",
    custom_role_id: CUSTOM_A,
  });
});

test("update is a no-op when the built-in role is unchanged and no custom role is set", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "builtin", role: "SALES_EXECUTIVE" },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    {},
  );
});

test("update is a no-op when the same custom role is re-selected", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "custom", customRoleId: CUSTOM_A },
      { roleName: "SALES_EXECUTIVE", customRoleId: CUSTOM_A },
    ),
    {},
  );
});

test("switching built-in roles sends only role, never custom_role_id", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "builtin", role: "ADMIN" },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    { role: "ADMIN" },
  );
});

test("clearing a custom role back to a built-in role sends role even when the base name matches", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "builtin", role: "SALES_EXECUTIVE" },
      { roleName: "SALES_EXECUTIVE", customRoleId: CUSTOM_A },
    ),
    { role: "SALES_EXECUTIVE" },
  );
});

test("assigning a custom role sends only custom_role_id so the backend accepts the update", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "custom", customRoleId: CUSTOM_B },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    { custom_role_id: CUSTOM_B },
  );
});

test("switching between two custom roles sends only the new custom_role_id", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { kind: "custom", customRoleId: CUSTOM_B },
      { roleName: "SALES_EXECUTIVE", customRoleId: CUSTOM_A },
    ),
    { custom_role_id: CUSTOM_B },
  );
});
