/**
 * Types and pure helpers for the Collections command centre.
 * Response shapes mirror backend/app/modules/collections/schemas.py.
 */

export interface CalendarRow {
  installment_id: string;
  booking_id: string;
  plan_id: string;
  project_id: string;
  customer_name: string | null;
  unit_number: string;
  milestone: string;
  due_on: string;
  amount_paise: number;
  paid_paise: number;
  outstanding_paise: number;
  status: string;
  days_overdue: number;
  demand_letter_status: string;
  demand_letter_sent_at: string | null;
  last_reminder_at: string | null;
  has_overdue_promise: boolean;
}

export interface CalendarDay {
  date: string;
  due_paise: number;
  rows: CalendarRow[];
}

export interface CalendarResponse {
  month: string;
  project_id: string | null;
  days: CalendarDay[];
  overdue_aging: Record<string, number>;
  due_this_month_paise: number;
}

export interface EscalationRow {
  booking_id: string;
  project_id: string;
  customer_name: string | null;
  unit_number: string;
  severity: string;
  oldest_due_on: string;
  days_overdue: number;
  outstanding_paise: number;
  overdue_installments: number;
  last_actions: Record<string, unknown>;
  suggested_action: string;
}

export interface EscalationsResponse {
  groups: Record<string, EscalationRow[]>;
  thresholds: Record<string, number>;
}

export interface StatsResponse {
  project_id: string | null;
  recovered_30d_paise: number;
  recovered_90d_paise: number;
  outstanding_paise: number;
  aging_buckets_paise: Record<string, number>;
  reminder_payment_counts: Record<string, number>;
}

export interface PromiseCreateRequest {
  amount_paise: number;
  promised_on: string;
  note?: string | null;
}

export interface PromiseResponse {
  id: string;
  installment_id: string;
  amount_paise: number;
  promised_on: string;
  note: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Pure helpers (unit-tested, no DOM/fetch)
// ---------------------------------------------------------------------------

/** Aging bucket keys the backend uses; ordered for display. */
const AGING_ORDER = ["0", "1-30", "31-60", "61-90", "90+"];

export function orderedAgingBuckets(buckets: Record<string, number>): string[] {
  const keys = Object.keys(buckets);
  return keys.sort((a, b) => {
    const ia = AGING_ORDER.indexOf(a);
    const ib = AGING_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

/** Severity rank for sorting escalation groups: most severe first. */
const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

export function severityRank(severity: string): number {
  return SEVERITY_RANK[severity.toUpperCase()] ?? 4;
}

export function orderedSeverityGroups(
  groups: Record<string, EscalationRow[]>,
): { severity: string; rows: EscalationRow[] }[] {
  return Object.keys(groups)
    .sort((a, b) => severityRank(a) - severityRank(b))
    .map((severity) => ({ severity, rows: groups[severity] ?? [] }));
}

/** Sort escalation rows within a group: most overdue + largest outstanding first. */
export function sortEscalationRows(rows: readonly EscalationRow[]): EscalationRow[] {
  return [...rows].sort(
    (a, b) => b.days_overdue - a.days_overdue || b.outstanding_paise - a.outstanding_paise,
  );
}

/** Flatten a calendar response into a single list of rows, soonest due first. */
export function flattenCalendar(days: readonly CalendarDay[]): CalendarRow[] {
  return [...days]
    .sort((a, b) => a.date.localeCompare(b.date))
    .flatMap((d) => d.rows);
}

/** Only the rows that are actually overdue (days_overdue > 0). */
export function overdueRows(days: readonly CalendarDay[]): CalendarRow[] {
  return flattenCalendar(days).filter((r) => r.days_overdue > 0);
}

/** Convert a YYYY-MM month string to a friendly label like "Nov 2026". */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map((v) => Number(v));
  if (!y || !m || m < 1 || m > 12) return month;
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-IN", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Step a YYYY-MM month string by +/- n months (e.g. for prev/next month nav). */
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map((v) => Number(v));
  if (!y || !m) return month;
  const total = y * 12 + (m - 1) + delta;
  const ny = Math.floor(total / 12);
  const nm = (total % 12) + 1;
  return `${ny}-${String(nm).padStart(2, "0")}`;
}

/** Current month as YYYY-MM from a Date (defaults to now). */
export function currentMonth(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}
