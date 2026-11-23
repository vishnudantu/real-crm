export type AdminRoleName = "ADMIN" | "MANAGER" | "SALES_EXECUTIVE" | "BUYER";

export interface AdminRoleOption {
  value: AdminRoleName;
  label: string;
  description: string;
}

/**
 * Single source of truth for assignable base roles, mirroring
 * backend/app/modules/users/models.py RoleName. The built-in role remains the
 * user's identity and scoping even when an optional custom role is attached;
 * custom roles contribute only additional permissions.
 */
export const ADMIN_ROLE_OPTIONS: readonly AdminRoleOption[] = [
  { value: "ADMIN", label: "Admin", description: "Full management" },
  { value: "MANAGER", label: "Manager", description: "Manages team operations" },
  { value: "SALES_EXECUTIVE", label: "Sales Exec", description: "Handles leads & visits" },
  { value: "BUYER", label: "Buyer", description: "Explores & books" },
];

export const ROLE_LABELS: Readonly<Record<AdminRoleName, string>> = {
  ADMIN: "Administrator",
  MANAGER: "Manager",
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

/**
 * Selection state shared by create/edit user forms: the base role is always
 * chosen and an optional custom role can add grants without replacing it.
 */
export type RoleAssignmentSelection = {
  role: AdminRoleName;
  customRoleId: string | null;
};

/**
 * Build role fields for UserCreateRequest. Create accepts role and
 * custom_role_id together, so the selected base role is always retained.
 */
export function createRoleAssignmentFields(
  selection: RoleAssignmentSelection,
): Pick<CreateUserPayload, "role" | "custom_role_id"> {
  return {
    role: selection.role,
    custom_role_id: selection.customRoleId,
  };
}

/**
 * Build role fields for UserUpdateRequest. The backend forbids sending both
 * role and custom_role_id (and forbids null), so only the changed field is
 * returned. A base-role change always sends role, which also clears an existing
 * custom role; custom-role-only changes leave the current base role intact.
 */
export function updateRoleAssignmentFields(
  selection: RoleAssignmentSelection,
  current: { roleName: string; customRoleId: string | null },
): Pick<UpdateUserPayload, "role" | "custom_role_id"> {
  if (current.roleName !== selection.role) {
    return { role: selection.role };
  }
  if (current.customRoleId !== selection.customRoleId) {
    if (selection.customRoleId === null) {
      // The current backend exposes custom-role removal through role updates.
      // Re-sending the unchanged base role preserves the base role while
      // clearing the custom assignment, unlike the old demotion semantics.
      return { role: selection.role };
    }
    return { custom_role_id: selection.customRoleId };
  }
  return {};
}

