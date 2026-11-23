export type MilestoneStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED" | "DELAYED" | "CERTIFIED";

export interface ConstructionMilestone {
  id: string;
  project_id: string;
  name: string;
  sequence_no: number;
  planned_date: string;
  actual_date: string | null;
  status: MilestoneStatus;
  percent_complete: number;
  evidence_notes: string | null;
  certified_by_id: string | null;
  certified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectProgressSummary {
  total: number;
  by_status: Record<string, number>;
  avg_percent: number;
  delayed_count: number;
}

export interface MilestoneCreateRequest {
  project_id: string;
  name: string;
  sequence_no: number;
  planned_date: string;
}

export function milestoneStatusLabel(status: string): string {
  return status.toLowerCase().split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function milestoneStatusTone(status: string): string {
  if (status === "CERTIFIED" || status === "COMPLETED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "DELAYED") return "border-rose-200 bg-rose-50 text-rose-700";
  if (status === "IN_PROGRESS") return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-charcoal/15 bg-charcoal/5 text-charcoal/65";
}

export function nextSequence(milestones: Pick<ConstructionMilestone, "sequence_no">[]): number {
  return milestones.reduce((maximum, milestone) => Math.max(maximum, milestone.sequence_no), 0) + 1;
}
