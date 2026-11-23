export type AdminRoleName = "ADMIN" | "SALES_EXECUTIVE" | "BUYER";

export interface AdminRoleOption {
  value: AdminRoleName;
  label: string;
  description: string;
}

/**
 * Single source of truth for assignable roles. There is no GET /roles endpoint
 * yet, so this mirrors backend/app/modules/users/models.py RoleName. When the
 * MANAGER role lands (feat/manager-role) add it here (and to AdminRoleName);
 * user creation, editing and filters all render from this list. It should
 * become API-driven once a roles endpoint exists.
 */
export const ADMIN_ROLE_OPTIONS: readonly AdminRoleOption[] = [
  { value: "ADMIN", label: "Admin", description: "Full management" },
  { value: "SALES_EXECUTIVE", label: "Sales Exec", description: "Handles leads & visits" },
  { value: "BUYER", label: "Buyer", description: "Explores & books" },
];

export const ROLE_LABELS: Readonly<Record<AdminRoleName, string>> = {
  ADMIN: "Administrator",
  SALES_EXECUTIVE: "Sales Executive",
  BUYER: "Buyer",
};

export function roleLabel(name: string): string {
  return ROLE_LABELS[name as AdminRoleName] ?? name.replaceAll("_", " ");
}

export type RoleInfo = {
  id: string;
  name: string;
  description: string | null;
};

/** Subset of the tenant custom role returned alongside a user (UserResponse.custom_role). */
export type UserCustomRoleInfo = {
  id: string;
  name: string;
  description: string | null;
  is_builtin: boolean;
  permissions: string[];
};

export type UserItem = {
  id: string;
  tenant_id?: string | null;
  full_name: string;
  email: string;
  phone: string | null;
  role: RoleInfo;
  custom_role: UserCustomRoleInfo | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
};

export type UserListResponse = {
  items: UserItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type UserMetrics = {
  total: number;
  active: number;
  deactivated: number;
  admins: number;
  sales_executives: number;
  buyers: number;
};

export type CreateUserPayload = {
  full_name: string;
  email: string;
  password: string;
  phone?: string | null;
  role: AdminRoleName;
  custom_role_id?: string | null;
  is_active: boolean;
};

/** Backend rejects null for both role fields and rejects setting both at once. */
export type UpdateUserPayload = {
  full_name?: string;
  phone?: string | null;
  role?: AdminRoleName;
  custom_role_id?: string;
};

export type UserFilterState = {
  search: string;
  role: AdminRoleName | "ALL";
  status: "ALL" | "ACTIVE" | "DEACTIVATED";
  page: number;
  pageSize: number;
};

/** Selection state shared by the create/edit user forms: built-in role or one custom role. */
export type RoleAssignmentSelection =
  | { kind: "builtin"; role: AdminRoleName }
  | { kind: "custom"; customRoleId: string };

/**
 * Build the role fields for UserCreateRequest. Both role and custom_role_id are
 * optional to the backend (role defaults to BUYER, custom overrides the base
 * role), so create can send either independently.
 */
export function createRoleAssignmentFields(
  selection: RoleAssignmentSelection,
): Pick<CreateUserPayload, "role" | "custom_role_id"> {
  return selection.kind === "custom"
    ? { role: "SALES_EXECUTIVE", custom_role_id: selection.customRoleId }
    : { role: selection.role, custom_role_id: null };
}

/**
 * Build the role fields for UserUpdateRequest. The backend forbids sending both
 * role and custom_role_id (and forbids null), so an empty object means "leave
 * the current assignment unchanged" and exactly one key is sent on a change.
 */
export function updateRoleAssignmentFields(
  selection: RoleAssignmentSelection,
  current: { roleName: string; customRoleId: string | null },
): Pick<UpdateUserPayload, "role" | "custom_role_id"> {
  if (selection.kind === "custom") {
    return current.customRoleId === selection.customRoleId
      ? {}
      : { custom_role_id: selection.customRoleId };
  }
  return current.customRoleId === null && current.roleName === selection.role
    ? {}
    : { role: selection.role };
}

