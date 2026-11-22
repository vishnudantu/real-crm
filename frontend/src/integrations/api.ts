import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type { ConnectProviderConfig, ConnectionRow } from "./helpers";

const SESSION = { getToken: getSession, clearToken: clearSession };

export interface MetaPageOption {
  id: string;
  name: string;
}

export interface MetaFinalizeResult {
  connection: ConnectionRow;
  webhook_url: string;
  webhook_verify_token: string;
  subscription_checklist: string[];
}

export interface ConnectionStatus {
  connection_id: string;
  provider: string;
  configured: boolean;
  health: string;
  missing: string[];
  last_success_at: string | null;
  last_error: string | null;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
}

export function fetchConnectProviders(): Promise<ConnectProviderConfig[]> {
  return bearerRequest<ConnectProviderConfig[]>("/integrations/connect/providers", SESSION);
}

export function fetchConnections(): Promise<ConnectionRow[]> {
  return bearerRequest<ConnectionRow[]>("/integrations/connections", SESSION);
}

export function fetchConnectUrl(provider: "meta" | "google"): Promise<{ url: string }> {
  return bearerRequest<{ url: string }>(
    `/integrations/connect/${provider}/connect-url`,
    SESSION,
  );
}

export function fetchMetaPages(connectionId: string): Promise<{ pages: MetaPageOption[] }> {
  return bearerRequest<{ pages: MetaPageOption[] }>(
    `/integrations/connect/meta/pages?connection_id=${encodeURIComponent(connectionId)}`,
    SESSION,
  );
}

export function finalizeMeta(payload: {
  connection_id: string;
  page_id: string;
  project_id: string;
  verify_token?: string;
}): Promise<MetaFinalizeResult> {
  return bearerRequest<MetaFinalizeResult>("/integrations/connect/meta/finalize", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function finalizeGoogle(payload: {
  connection_id: string;
  customer_id: string;
  project_id: string;
}): Promise<ConnectionRow> {
  return bearerRequest<ConnectionRow>("/integrations/connect/google/finalize", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface GoogleManualPayload {
  developer_token: string;
  refresh_token: string;
  client_id: string;
  client_secret: string;
  customer_id: string;
  project_id: string;
}

export function connectGoogleManually(payload: GoogleManualPayload): Promise<ConnectionRow> {
  return bearerRequest<ConnectionRow>("/integrations/connect/google/manual", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchConnectionStatus(
  provider: "meta" | "google",
  connectionId: string,
): Promise<ConnectionStatus> {
  return bearerRequest<ConnectionStatus>(
    `/integrations/connect/${provider}/status/${encodeURIComponent(connectionId)}`,
    SESSION,
  );
}

export function testConnection(
  provider: "meta" | "google",
  connectionId: string,
): Promise<ConnectionTestResult> {
  return bearerRequest<ConnectionTestResult>(
    `/integrations/connect/${provider}/test?connection_id=${encodeURIComponent(connectionId)}`,
    SESSION,
    { method: "POST" },
  );
}

export function revokeConnection(connectionId: string): Promise<null> {
  return bearerRequest<null>(
    `/integrations/connect/connections/${encodeURIComponent(connectionId)}`,
    SESSION,
    { method: "DELETE" },
  );
}
