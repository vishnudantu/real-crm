import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type { TenantAIProvider, TenantAIProviderUpsert } from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const tenantAIKeys = { provider: ["admin", "tenant-ai", "provider"] as const };

export function fetchProvider(): Promise<TenantAIProvider> {
  return bearerRequest<TenantAIProvider>("/tenant-ai/provider", SESSION);
}

export function saveProvider(payload: TenantAIProviderUpsert): Promise<TenantAIProvider> {
  return bearerRequest<TenantAIProvider>("/tenant-ai/provider", SESSION, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function clearProvider(): Promise<null> {
  return bearerRequest<null>("/tenant-ai/provider", SESSION, { method: "DELETE" });
}
