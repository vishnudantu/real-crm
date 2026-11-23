import test from "node:test";
import assert from "node:assert/strict";
import {
  ADMIN_ROLE_OPTIONS,
  createRoleAssignmentFields,
  updateRoleAssignmentFields,
} from "../../src/admin/adminModel.ts";

const CUSTOM_A = "00000000-0000-0000-0000-00000000000a";
const CUSTOM_B = "00000000-0000-0000-0000-00000000000b";

test("create without a custom role sends the chosen base role and null custom_role_id", () => {
  assert.deepEqual(createRoleAssignmentFields({ role: "ADMIN", customRoleId: null }), {
    role: "ADMIN",
    custom_role_id: null,
  });
});

test("create with a custom role preserves the chosen base role", () => {
  assert.deepEqual(createRoleAssignmentFields({ role: "ADMIN", customRoleId: CUSTOM_A }), {
    role: "ADMIN",
    custom_role_id: CUSTOM_A,
  });
  assert.deepEqual(createRoleAssignmentFields({ role: "SALES_EXECUTIVE", customRoleId: CUSTOM_A }), {
    role: "SALES_EXECUTIVE",
    custom_role_id: CUSTOM_A,
  });
});

test("manager is available as a base-role choice", () => {
  assert.ok(ADMIN_ROLE_OPTIONS.some((option) => option.value === "MANAGER"));
  assert.deepEqual(createRoleAssignmentFields({ role: "MANAGER", customRoleId: CUSTOM_A }), {
    role: "MANAGER",
    custom_role_id: CUSTOM_A,
  });
});

test("update is a no-op when both base and custom roles are unchanged", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "SALES_EXECUTIVE", customRoleId: null },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    {},
  );
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "ADMIN", customRoleId: CUSTOM_A },
      { roleName: "ADMIN", customRoleId: CUSTOM_A },
    ),
    {},
  );
});

test("changing only the base role sends role and preserves backend clearing semantics", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "ADMIN", customRoleId: null },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    { role: "ADMIN" },
  );
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "MANAGER", customRoleId: CUSTOM_A },
      { roleName: "SALES_EXECUTIVE", customRoleId: CUSTOM_A },
    ),
    { role: "MANAGER" },
  );
});

test("clearing a custom role sends only the unchanged base role", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "ADMIN", customRoleId: null },
      { roleName: "ADMIN", customRoleId: CUSTOM_A },
    ),
    { role: "ADMIN" },
  );
});

test("adding a custom role sends only custom_role_id and never demotes the base role", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "ADMIN", customRoleId: CUSTOM_B },
      { roleName: "ADMIN", customRoleId: null },
    ),
    { custom_role_id: CUSTOM_B },
  );
});

test("switching between two custom roles sends only the new custom_role_id", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "SALES_EXECUTIVE", customRoleId: CUSTOM_B },
      { roleName: "SALES_EXECUTIVE", customRoleId: CUSTOM_A },
    ),
    { custom_role_id: CUSTOM_B },
  );
});

test("changing base role while adding a custom role sends only role to satisfy backend mutual exclusion", () => {
  assert.deepEqual(
    updateRoleAssignmentFields(
      { role: "ADMIN", customRoleId: CUSTOM_A },
      { roleName: "SALES_EXECUTIVE", customRoleId: null },
    ),
    { role: "ADMIN" },
  );
});
