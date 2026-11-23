import type { FunnelCounts, MyDayItem, Urgency } from "./api";

export type UrgencyGroup = { urgency: Urgency; label: string; items: MyDayItem[] };

export const URGENCY_LABELS: Record<Urgency, string> = {
  OVERDUE: "Overdue",
  DUE_TODAY: "Due today",
  AGING_SILENCE: "Needs a reply",
  PENDING_APPROVAL: "Pending approvals",
};

export function groupByUrgency(items: MyDayItem[]): UrgencyGroup[] {
  const order: Urgency[] = ["OVERDUE", "DUE_TODAY", "AGING_SILENCE", "PENDING_APPROVAL"];
  return order
    .map((urgency) => ({
      urgency,
      label: URGENCY_LABELS[urgency],
      items: items.filter((item) => item.urgency === urgency),
    }))
    .filter((group) => group.items.length > 0);
}

export function dailyDelta(today: number, average: number): number {
  if (average === 0) return today === 0 ? 0 : 100;
  return Math.round(((today - average) / average) * 100);
}

export function funnelRatio(counts: FunnelCounts): number {
  if (counts.enquiries === 0) return 0;
  return Math.round((counts.bookings / counts.enquiries) * 100);
}
