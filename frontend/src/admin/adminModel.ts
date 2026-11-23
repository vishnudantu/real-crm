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
  name: AdminRoleName;
  description: string | null;
};

export type UserItem = {
  id: string;
  tenant_id?: string | null;
  full_name: string;
  email: string;
  phone: string | null;
  role: RoleInfo;
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
  is_active: boolean;
};

export type UpdateUserPayload = {
  full_name?: string;
  phone?: string | null;
  role?: AdminRoleName;
};

export type UserFilterState = {
  search: string;
  role: AdminRoleName | "ALL";
  status: "ALL" | "ACTIVE" | "DEACTIVATED";
  page: number;
  pageSize: number;
};

