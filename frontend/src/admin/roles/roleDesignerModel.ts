/**
 * Pure helpers and API contracts for the custom role designer, mirroring
 * backend/app/modules/users/permissions.py and role_schemas.py. Keep in sync
 * with the registry: new grantable areas appear in the checklist automatically
 * through groupPermissions(), but the protected/limit rules below are
 * duplicated intentionally so the form can block invalid submissions before
 * the API does.
 */

/** GET /roles/permissions item — backend PermissionResponse. */
export type PermissionItem = {
  key: string;
  area: string;
  description: string;
  /** False for protected system keys (settings/users/roles/operator) — never assignable. */
  grantable: boolean;
  /** True only for keys currently enforced by a router gate (backend pilot). */
  enabled: boolean;
};

export type PermissionListResponse = {
  items: PermissionItem[];
  total: number;
};

/** GET /roles/custom item — backend CustomRoleResponse. */
export type CustomRoleItem = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  permissions: string[];
  is_builtin: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type CustomRoleListResponse = {
  items: CustomRoleItem[];
  total: number;
};

/** POST /roles/custom body — backend CustomRoleCreateRequest (extra=forbid). */
export type CreateCustomRolePayload = {
  name: string;
  description?: string | null;
  permissions: string[];
};

/** PATCH /roles/custom/{id} body — backend CustomRoleUpdateRequest. */
export type UpdateCustomRolePayload = {
  name?: string;
  description?: string | null;
  permissions?: string[];
};

export const MAX_CUSTOM_ROLE_PERMISSIONS = 32;
export const MIN_ROLE_NAME_LENGTH = 2;
export const MAX_ROLE_NAME_LENGTH = 64;
export const MAX_ROLE_DESCRIPTION_LENGTH = 255;

/** Registry areas that are visible but can never be assigned (backend grantable=false). */
export const PROTECTED_AREA_LABELS: Readonly<Record<string, string>> = {
  settings: "Settings",
  users: "Users",
  roles: "Roles",
  operator: "Operator",
};

export function areaLabel(area: string): string {
  const known = PROTECTED_AREA_LABELS[area];
  if (known) return known;
  return area
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Group registry entries by area, areas sorted alphabetically and keys sorted
 * within each area — the same ordering the backend returns.
 */
export function groupPermissions(
  items: readonly PermissionItem[],
): { area: string; permissions: PermissionItem[] }[] {
  const byArea = new Map<string, PermissionItem[]>();
  for (const item of items) {
    const bucket = byArea.get(item.area) ?? [];
    bucket.push(item);
    byArea.set(item.area, bucket);
  }
  return [...byArea.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([area, permissions]) => ({
      area,
      permissions: [...permissions]
        .map((permission) => ({ ...permission }))
        .sort((a, b) => a.key.localeCompare(b.key)),
    }));
}

export function isAssignable(permission: PermissionItem): boolean {
  return permission.grantable;
}

/** Grantable keys only; protects against stale selections after a registry change. */
export function assignableKeys(items: readonly PermissionItem[]): string[] {
  return items.filter((item) => item.grantable).map((item) => item.key);
}

/** Toggle one key immutably; protected keys are ignored like the backend rejects them. */
export function togglePermission(
  selected: readonly string[],
  key: string,
  grantable: boolean,
): string[] {
  if (!grantable) return [...selected];
  return selected.includes(key)
    ? selected.filter((entry) => entry !== key)
    : [...selected, key];
}

export function validateRoleDraft(draft: {
  name: string;
  description: string;
  permissions: readonly string[];
}): string | null {
  const name = draft.name.trim();
  if (name.length < MIN_ROLE_NAME_LENGTH) {
    return `Role name must contain at least ${MIN_ROLE_NAME_LENGTH} characters.`;
  }
  if (name.length > MAX_ROLE_NAME_LENGTH) {
    return `Role name must be ${MAX_ROLE_NAME_LENGTH} characters or fewer.`;
  }
  if (draft.description.trim().length > MAX_ROLE_DESCRIPTION_LENGTH) {
    return `Description must be ${MAX_ROLE_DESCRIPTION_LENGTH} characters or fewer.`;
  }
  if (draft.permissions.length > MAX_CUSTOM_ROLE_PERMISSIONS) {
    return `A role can hold at most ${MAX_CUSTOM_ROLE_PERMISSIONS} permissions.`;
  }
  return null;
}

/** Human summary of selected keys per area, e.g. "Inventory: read, write". */
export function summarizePermissions(
  selected: readonly string[],
  items: readonly PermissionItem[],
): string {
  if (selected.length === 0) return "No permissions yet";
  const byArea = new Map<string, string[]>();
  const keyToArea = new Map(items.map((item) => [item.key, item.area]));
  for (const key of selected) {
    const area = keyToArea.get(key) ?? key.split(".")[0] ?? "Other";
    const actions = byArea.get(area) ?? [];
    actions.push(key.slice(area.length + 1) || key);
    byArea.set(area, actions);
  }
  return [...byArea.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([area, actions]) => `${areaLabel(area)}: ${actions.join(", ")}`)
    .join(" · ");
}

/**
 * Parse the backend error body for the message shown on 409 duplicate names and
 * 422 validation rejections; ApiError already carries the envelope message, so
 * this only normalises whitespace from multi-sentence inventory-style errors.
 */
export function describeApiFailure(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message.trim();
  return fallback;
}
