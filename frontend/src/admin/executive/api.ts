import { clearSession, getSession } from "../../auth/session";
import { bearerRequest } from "../../shared/apiRequest";
import type { BriefingResponse, CockpitResponse } from "./executiveModel";

const SESSION = {
  getToken: getSession,
  clearToken: clearSession,
};

export function fetchExecutiveCockpit(params: {
  projectId?: string | null;
  months?: number;
}): Promise<CockpitResponse> {
  const query = new URLSearchParams();
  if (params.projectId) query.set("project_id", params.projectId);
  if (params.months) query.set("months", String(params.months));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return bearerRequest<CockpitResponse>(`/executive/cockpit${suffix}`, SESSION);
}

export function fetchExecutiveBriefing(date?: string): Promise<BriefingResponse> {
  const suffix = date ? `?date=${encodeURIComponent(date)}` : "";
  return bearerRequest<BriefingResponse>(`/executive/briefing${suffix}`, SESSION);
}
