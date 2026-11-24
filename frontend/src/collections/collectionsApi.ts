import { bearerRequest } from "../shared/apiRequest";
import { clearSession, getSession } from "../auth/session";
import type {
  CalendarResponse,
  EscalationsResponse,
  PromiseCreateRequest,
  PromiseResponse,
  StatsResponse,
} from "./collectionsModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(path, { getToken: getSession, clearToken: clearSession }, init);
}

function withProject(base: string, projectId?: string): string {
  if (!projectId) return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}project_id=${projectId}`;
}

export function fetchCalendar(month: string, projectId?: string): Promise<CalendarResponse> {
  const base = `/collections/calendar?month=${encodeURIComponent(month)}`;
  return request<CalendarResponse>(withProject(base, projectId));
}

export function fetchEscalations(projectId?: string): Promise<EscalationsResponse> {
  return request<EscalationsResponse>(withProject("/collections/escalations", projectId));
}

export function fetchStats(projectId?: string): Promise<StatsResponse> {
  return request<StatsResponse>(withProject("/collections/stats", projectId));
}

export function createPromise(
  installmentId: string,
  payload: PromiseCreateRequest,
): Promise<PromiseResponse> {
  return request<PromiseResponse>(`/collections/installments/${installmentId}/promises`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
