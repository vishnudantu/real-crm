import { clearSession, getSession } from "../../auth/session";
import { bearerRequest } from "../../shared/apiRequest";
import type {
  CreateCustomRolePayload,
  CustomRoleItem,
  CustomRoleListResponse,
  PermissionListResponse,
  UpdateCustomRolePayload,
} from "./roleDesignerModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(
    path,
    { getToken: getSession, clearToken: clearSession },
    init,
  );
}

/** Admin-only permission registry used to render the role designer checklist. */
export function fetchPermissionRegistry(): Promise<PermissionListResponse> {
  return request<PermissionListResponse>("/roles/permissions");
}

export function fetchCustomRoles(): Promise<CustomRoleListResponse> {
  return request<CustomRoleListResponse>("/roles/custom");
}

export function createCustomRole(
  payload: CreateCustomRolePayload,
): Promise<CustomRoleItem> {
  return request<CustomRoleItem>("/roles/custom", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCustomRole(
  roleId: string,
  payload: UpdateCustomRolePayload,
): Promise<CustomRoleItem> {
  return request<CustomRoleItem>(`/roles/custom/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/** Backend returns 204 on success and 409 while users still hold the role. */
export function deleteCustomRole(roleId: string): Promise<void> {
  return request<void>(`/roles/custom/${roleId}`, { method: "DELETE" });
}
