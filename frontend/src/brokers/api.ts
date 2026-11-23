import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type { Broker, BrokerCreateRequest, BrokerListResponse, BrokerPerformance, BrokerStatus } from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const brokerKeys = {
  all: ["admin", "brokers"] as const,
  list: (status: BrokerStatus | "ALL", search: string) => ["admin", "brokers", { status, search }] as const,
  detail: (id: string) => ["admin", "brokers", id] as const,
  performance: (id: string) => ["admin", "brokers", id, "performance"] as const,
};

export function fetchBrokers(status: BrokerStatus | "ALL", search: string): Promise<BrokerListResponse> {
  const query = new URLSearchParams();
  if (status !== "ALL") query.set("status", status);
  if (search.trim()) query.set("search", search.trim());
  const suffix = query.size ? `?${query}` : "";
  return bearerRequest<BrokerListResponse>(`/brokers${suffix}`, SESSION);
}

export function fetchBroker(id: string): Promise<Broker> {
  return bearerRequest<Broker>(`/brokers/${id}`, SESSION);
}

export function fetchBrokerPerformance(id: string): Promise<BrokerPerformance> {
  return bearerRequest<BrokerPerformance>(`/brokers/${id}/performance`, SESSION);
}

export function createBroker(payload: BrokerCreateRequest): Promise<Broker> {
  return bearerRequest<Broker>("/brokers", SESSION, { method: "POST", body: JSON.stringify(payload) });
}

export function updateBrokerStatus(id: string, status: BrokerStatus): Promise<Broker> {
  return bearerRequest<Broker>(`/brokers/${id}`, SESSION, { method: "PATCH", body: JSON.stringify({ status }) });
}
