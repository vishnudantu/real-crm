import { bearerRequest } from "../shared/apiRequest";
import { clearSession, getSession } from "../auth/session";
import type {
  ConflictResponse,
  HoldExpiryResponse,
  RecommendationResponse,
  RevenueMapResponse,
  UnsoldRiskResponse,
} from "./intelligenceModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(path, { getToken: getSession, clearToken: clearSession }, init);
}

const BASE = "/inventory/intelligence";

export function fetchRevenueMap(projectId: string): Promise<RevenueMapResponse> {
  return request<RevenueMapResponse>(`${BASE}/projects/${projectId}/revenue-map`);
}

export function fetchHoldExpiry(projectId: string): Promise<HoldExpiryResponse> {
  return request<HoldExpiryResponse>(`${BASE}/projects/${projectId}/hold-expiry`);
}

export function fetchUnsoldRisk(
  projectId: string,
  mediumDays = 60,
  highDays = 120,
): Promise<UnsoldRiskResponse> {
  return request<UnsoldRiskResponse>(
    `${BASE}/projects/${projectId}/unsold-risk?medium_days=${mediumDays}&high_days=${highDays}`,
  );
}

export function fetchConflicts(projectId: string): Promise<ConflictResponse> {
  return request<ConflictResponse>(`${BASE}/projects/${projectId}/conflicts`);
}

export function fetchRecommendations(unitId: string, limit = 5): Promise<RecommendationResponse> {
  return request<RecommendationResponse>(`${BASE}/units/${unitId}/recommendations?limit=${limit}`);
}
