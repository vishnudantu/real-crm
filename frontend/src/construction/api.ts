import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type { ConstructionMilestone, MilestoneCreateRequest, ProjectProgressSummary } from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const constructionKeys = {
  all: ["admin", "construction"] as const,
  milestones: (projectId: string) => ["admin", "construction", projectId, "milestones"] as const,
  progress: (projectId: string) => ["admin", "construction", projectId, "progress"] as const,
};

export function fetchMilestones(projectId: string): Promise<ConstructionMilestone[]> {
  return bearerRequest<ConstructionMilestone[]>(`/construction/projects/${projectId}/milestones`, SESSION);
}

export function fetchProgress(projectId: string): Promise<ProjectProgressSummary> {
  return bearerRequest<ProjectProgressSummary>(`/construction/projects/${projectId}/progress`, SESSION);
}

export function createMilestone(payload: MilestoneCreateRequest): Promise<ConstructionMilestone> {
  return bearerRequest<ConstructionMilestone>("/construction/milestones", SESSION, { method: "POST", body: JSON.stringify(payload) });
}

export function addMilestoneProgress(id: string, percentComplete: number, note: string): Promise<ConstructionMilestone> {
  return bearerRequest<ConstructionMilestone>(`/construction/milestones/${id}/progress`, SESSION, { method: "POST", body: JSON.stringify({ percent_complete: percentComplete, note }) });
}

export function certifyMilestone(id: string, evidenceNotes: string): Promise<ConstructionMilestone> {
  return bearerRequest<ConstructionMilestone>(`/construction/milestones/${id}/certify`, SESSION, { method: "POST", body: JSON.stringify({ evidence_notes: evidenceNotes || null }) });
}
