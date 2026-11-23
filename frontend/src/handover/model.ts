export type HandoverStatus = "CHECKLIST" | "IN_PROGRESS" | "SNAG_OPEN" | "READY" | "HANDED_OVER";
export type SnagStatus = "OPEN" | "FIXED" | "VERIFIED" | "CLOSED";
export type SnagSeverity = "MINOR" | "MAJOR" | "CRITICAL";
export type StaffRole = "ADMIN" | "MANAGER" | "SALES_EXECUTIVE" | "BUYER";

export interface HandoverCase {
  id: string;
  unit_id: string;
  unit_number?: string | null;
  booking_reference?: string | null;
  booking_id: string | null;
  status: HandoverStatus;
  readiness: Record<string, unknown>;
  registration_date: string | null;
  registration_reference: string | null;
  possession_date: string | null;
  override_reason: string | null;
  override_by_id: string | null;
  override_at: string | null;
  handed_over_at: string | null;
  handed_over_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChecklistCondition { code: string; label: string; met: boolean; detail: string }
export interface ReadinessBlocker extends ChecklistCondition { met: false }
export interface HandoverChecklist {
  case_id: string;
  score: number;
  required_count: number;
  met_count: number;
  conditions: ChecklistCondition[];
  blockers: ReadinessBlocker[];
  financials: { planned_paise: number | null; collected_paise: number | null; outstanding_paise: number | null; live_receipt_count: number };
  snag_count: number;
  unresolved_snag_count: number;
  checked_at: string;
}

export interface SnagItem {
  id: string;
  case_id: string;
  room: string;
  description: string;
  severity: SnagSeverity;
  status: SnagStatus;
  photo_evidence_path: string | null;
  assigned_user_id: string | null;
  fixed_by_id: string | null;
  fixed_at: string | null;
  verified_by_id: string | null;
  verified_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KeyHandover {
  id: string;
  case_id: string;
  keys_count: number;
  cards_count: number;
  handed_to_name: string;
  handed_at: string;
  collected_id: string | null;
  collected_at: string | null;
  collected_notes: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export function readinessDisplay(checklist: HandoverChecklist | null | undefined): { score: number; summary: string; tone: "ready" | "blocked" } {
  if (!checklist) return { score: 0, summary: "Checklist not loaded", tone: "blocked" };
  const score = Math.max(0, Math.min(100, Math.round(checklist.score)));
  return {
    score,
    summary: checklist.blockers.length ? `${checklist.met_count}/${checklist.required_count} conditions met · ${checklist.blockers.length} blocker${checklist.blockers.length === 1 ? "" : "s"}` : "All conditions met · ready for possession",
    tone: score === 100 && checklist.blockers.length === 0 ? "ready" : "blocked",
  };
}

export function snagStatusLabel(status: SnagStatus): string {
  return { OPEN: "Open", FIXED: "Fixed · needs verification", VERIFIED: "Independently verified", CLOSED: "Closed" }[status];
}

export function handoverStatusLabel(status: HandoverStatus): string {
  return { CHECKLIST: "Checklist", IN_PROGRESS: "In progress", SNAG_OPEN: "Snag open", READY: "Ready", HANDED_OVER: "Handed over" }[status];
}

export function nextSnagAction(status: SnagStatus, actorId: string, fixedById: string | null): { action: "fix" | "verify" | "close"; label: string } | null {
  if (status === "OPEN") return { action: "fix", label: "Mark fixed" };
  if (status === "FIXED") return fixedById === actorId ? null : { action: "verify", label: "Verify repair" };
  if (status === "VERIFIED") return { action: "close", label: "Close snag" };
  return null;
}

export function canManageHandover(role: string | null | undefined): boolean {
  return role === "ADMIN" || role === "MANAGER";
}

export function moneyDisplay(paise: number | null): string {
  return paise === null ? "No linked ledger" : `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
