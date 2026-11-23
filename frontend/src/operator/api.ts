import { API_BASE_URL, ApiError } from "../auth/api";
import { bearerRequest } from "../shared/apiRequest";
import { clearOperatorSession, getOperatorSession } from "./session";
import type {
  AuditLogFilters,
  CreateOperatorPayload,
  CreatePlanPayload,
  FeatureCatalogEntry,
  ImpersonationResult,
  OnboardTenantPayload,
  OnboardTenantResponse,
  OperatorAuditLog,
  OperatorPlan,
  OperatorTenant,
  OperatorTenantDetail,
  OperatorTokenResponse,
  OperatorUser,
  ProvisionTenantPayload,
  ProvisionTenantResponse,
  TenantConfig,
  TenantConfigPatchPayload,
  TenantDeploymentPayload,
  TenantDeploymentResponse,
  TenantFeatureEntry,
  TenantHealth,
  TenantUsage,
  TenantStatus,
  UpdateOperatorPayload,
  UpdatePlanPayload,
} from "./operatorModel";

const SESSION = {
  getToken: getOperatorSession,
  clearToken: clearOperatorSession,
};

export async function loginOperator(
  email: string,
  password: string,
): Promise<OperatorTokenResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/operator/auth/login`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
    });
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "We couldn't reach PropFlow. Check your connection and try again.",
    );
  }

  const body = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.error?.code ?? `HTTP_${response.status}`,
      body?.error?.message ??
        (response.status === 401
          ? "Invalid operator credentials."
          : "Unable to sign in. Please try again."),
    );
  }

  return body as unknown as OperatorTokenResponse;
}

export function fetchOperatorProfile(): Promise<OperatorUser> {
  return bearerRequest<OperatorUser>("/operator/auth/me", SESSION);
}

export function fetchOperatorUsers(): Promise<OperatorUser[]> {
  return bearerRequest<OperatorUser[]>("/operator/operators", SESSION);
}

export function createOperatorUser(
  payload: CreateOperatorPayload,
): Promise<OperatorUser> {
  return bearerRequest<OperatorUser>("/operator/operators", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateOperatorUser(
  operatorId: string,
  payload: UpdateOperatorPayload,
): Promise<OperatorUser> {
  return bearerRequest<OperatorUser>(
    `/operator/operators/${operatorId}`,
    SESSION,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function fetchOperatorTenants(): Promise<OperatorTenant[]> {
  return bearerRequest<OperatorTenant[]>("/operator/tenants", SESSION);
}

export function fetchOperatorTenant(
  tenantId: string,
): Promise<OperatorTenantDetail> {
  return bearerRequest<OperatorTenantDetail>(
    `/operator/tenants/${tenantId}`,
    SESSION,
  );
}

export function provisionTenant(
  payload: ProvisionTenantPayload,
): Promise<ProvisionTenantResponse> {
  return bearerRequest<ProvisionTenantResponse>("/operator/tenants", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTenantStatus(
  tenantId: string,
  status: TenantStatus,
): Promise<{ id: string; slug: string; status: TenantStatus }> {
  return bearerRequest<{ id: string; slug: string; status: TenantStatus }>(
    `/operator/tenants/${tenantId}/status`,
    SESSION,
    { method: "PATCH", body: JSON.stringify({ status }) },
  );
}

export function fetchOperatorPlans(): Promise<OperatorPlan[]> {
  return bearerRequest<OperatorPlan[]>("/operator/plans", SESSION);
}

export function createOperatorPlan(
  payload: CreatePlanPayload,
): Promise<OperatorPlan> {
  return bearerRequest<OperatorPlan>("/operator/plans", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateOperatorPlan(
  planId: string,
  payload: UpdatePlanPayload,
): Promise<OperatorPlan> {
  return bearerRequest<OperatorPlan>(`/operator/plans/${planId}`, SESSION, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function requestTenantDeployment(
  tenantId: string,
  payload: TenantDeploymentPayload,
): Promise<TenantDeploymentResponse> {
  return bearerRequest<TenantDeploymentResponse>(
    `/operator/tenants/${tenantId}/deployments`,
    SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function fetchOperatorAuditLogs(
  filters: AuditLogFilters = {},
): Promise<OperatorAuditLog[]> {
  const query = new URLSearchParams();
  if (filters.action) query.set("action", filters.action);
  if (filters.resource_type) query.set("resource_type", filters.resource_type);
  if (filters.actor_email) query.set("actor_email", filters.actor_email);
  if (filters.tenant_slug) query.set("tenant_slug", filters.tenant_slug);
  if (filters.limit) query.set("limit", String(filters.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return bearerRequest<OperatorAuditLog[]>(`/operator/audit-logs${suffix}`, SESSION);
}

export function fetchFeatureCatalog(): Promise<FeatureCatalogEntry[]> {
  return bearerRequest<FeatureCatalogEntry[]>("/operator/features/catalog", SESSION);
}

export function fetchTenantFeatures(
  tenantId: string,
): Promise<TenantFeatureEntry[]> {
  return bearerRequest<TenantFeatureEntry[]>(
    `/operator/tenants/${tenantId}/features`,
    SESSION,
  );
}

export function setTenantFeature(
  tenantId: string,
  feature: string,
  payload: { enabled: boolean; reason?: string | null },
): Promise<{ feature: string; tenant_id: string; enabled: boolean; source: string }> {
  return bearerRequest<{
    feature: string;
    tenant_id: string;
    enabled: boolean;
    source: string;
  }>(`/operator/tenants/${tenantId}/features/${feature}`, SESSION, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function bulkUpdateTenantFeatures(
  tenantId: string,
  features: Record<string, boolean>,
): Promise<TenantFeatureEntry[]> {
  return bearerRequest<TenantFeatureEntry[]>(
    `/operator/tenants/${tenantId}/features`,
    SESSION,
    { method: "PUT", body: JSON.stringify({ features }) },
  );
}

export function resetTenantFeatureOverride(
  tenantId: string,
  feature: string,
): Promise<{ feature: string; tenant_id: string; source: string }> {
  return bearerRequest<{ feature: string; tenant_id: string; source: string }>(
    `/operator/tenants/${tenantId}/features/${feature}`,
    SESSION,
    { method: "DELETE" },
  );
}

export function fetchTenantConfig(tenantId: string): Promise<TenantConfig> {
  return bearerRequest<TenantConfig>(`/operator/tenants/${tenantId}/config`, SESSION);
}

export function patchTenantConfig(
  tenantId: string,
  payload: TenantConfigPatchPayload,
): Promise<TenantConfig> {
  return bearerRequest<TenantConfig>(`/operator/tenants/${tenantId}/config`, SESSION, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function fetchTenantUsage(
  tenantId: string,
  days: number,
): Promise<TenantUsage> {
  return bearerRequest<TenantUsage>(
    `/operator/tenants/${tenantId}/usage?days=${days}`,
    SESSION,
  );
}

export function fetchTenantHealth(tenantId: string): Promise<TenantHealth> {
  return bearerRequest<TenantHealth>(`/operator/tenants/${tenantId}/health`, SESSION);
}

export function impersonateTenant(tenantId: string): Promise<ImpersonationResult> {
  return bearerRequest<ImpersonationResult>(
    `/operator/tenants/${tenantId}/impersonate`,
    SESSION,
    { method: "POST" },
  );
}

export function onboardTenant(
  payload: OnboardTenantPayload,
): Promise<OnboardTenantResponse> {
  return bearerRequest<OnboardTenantResponse>("/operator/tenants/onboard", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchRevenueSummary(months = 6): Promise<import("./revenueModel").RevenueSummaryResponse> {
  return bearerRequest<import("./revenueModel").RevenueSummaryResponse>(
    `/operator/revenue/summary?months=${months}`,
    SESSION,
  );
}
