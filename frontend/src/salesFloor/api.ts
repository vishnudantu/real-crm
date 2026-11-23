import { authenticatedRequest } from "../auth/api";

export type Urgency = "OVERDUE" | "DUE_TODAY" | "AGING_SILENCE" | "PENDING_APPROVAL";
export type MyDayKind = "FOLLOW_UP" | "VISIT" | "FIRST_RESPONSE" | "CONVERSATION" | "APPROVAL";

export type MyDayItem = {
  kind: MyDayKind;
  id: string;
  urgency: Urgency;
  priority_score: number;
  title: string;
  reason: string;
  lead_id: string | null;
  project_id: string | null;
  project_name: string | null;
  due_at: string;
  waiting_hours: number;
  link: string;
};

export type MyDayResponse = {
  date: string;
  scope: "PERSONAL" | "TEAM";
  items: MyDayItem[];
  counts: Partial<Record<MyDayKind, number>>;
  priority_explanation: string;
  promises_included: boolean;
};

export type ExecutiveActivity = {
  executive_id: string;
  full_name: string;
  visits_today: number;
  new_leads: number;
  bookings_created: number;
};

export type FunnelCounts = { enquiries: number; visits: number; bookings: number };
export type ProjectFunnel = {
  project_id: string;
  project_name: string;
  today: FunnelCounts;
  seven_day_average: FunnelCounts;
};

export type WarRoomResponse = {
  date: string;
  comparison_start: string;
  executive_activity: ExecutiveActivity[];
  new_leads_by_source: Array<{ source: string; count: number }>;
  new_leads_total: number;
  visits_today: number;
  bookings_created_today: number;
  pending_discount_approvals: number;
  unassigned_leads_count: number;
  project_funnels: ProjectFunnel[];
};

export function fetchMyDay(): Promise<MyDayResponse> {
  return authenticatedRequest<MyDayResponse>("/sales-floor/my-day");
}

export function fetchWarRoom(): Promise<WarRoomResponse> {
  return authenticatedRequest<WarRoomResponse>("/sales-floor/war-room");
}
