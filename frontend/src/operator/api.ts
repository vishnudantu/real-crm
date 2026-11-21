import { API_BASE_URL, ApiError } from "../auth/api";
import { bearerRequest } from "../shared/apiRequest";
import { clearOperatorSession, getOperatorSession } from "./session";
import type {
  CreateOperatorPayload,
  CreatePlanPayload,
  OperatorAuditLog,
  OperatorPlan,
  OperatorTenant,
  OperatorTenantDetail,
  OperatorTokenResponse,
  OperatorUser,
  ProvisionTenantPayload,
  ProvisionTenantResponse,
  TenantDeploymentPayload,
  TenantDeploymentResponse,
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

export function fetchOperatorAuditLogs(): Promise<OperatorAuditLog[]> {
  return bearerRequest<OperatorAuditLog[]>("/operator/audit-logs", SESSION);
}
