// Types for the executive cockpit aggregation API.
// All monetary values are integer paise (INR minor units).

export interface ExecutiveMonthPoint {
  month: string; // ISO date (first of month)
  enquiries: number;
  visits_completed: number;
  bookings: number;
  booking_value_paise: number;
}

export interface CollectionsMonthPoint {
  month: string;
  collected_paise: number;
  receipt_count: number;
}

export interface InventorySummary {
  project_id: string | null;
  total_units: number;
  counts_by_status: Record<string, number>;
  available: number;
  on_hold: number;
  reserved: number;
  booked: number;
  sold: number;
  unsold_value_paise: number;
}

export interface ApprovalsSummary {
  pending_count: number;
  pending_amount_paise: number;
  by_type: Record<string, number>;
}

export interface OverdueInstallmentRow {
  installment_id: string;
  unit_number: string;
  milestone: string;
  amount_paise: number;
  due_on: string;
  days_overdue: number;
}

export interface OverdueInstallmentsSummary {
  count: number;
  amount_paise: number;
  oldest_due_on: string | null;
  sample: OverdueInstallmentRow[];
}

export interface TicketSlaSummary {
  breaching_count: number;
  open_count: number;
  by_priority: Record<string, number>;
}

export interface ProjectRankRow {
  project_id: string;
  project_name: string;
  enquiries: number;
  visits_completed: number;
  bookings: number;
  booking_value_paise: number;
  collected_paise: number;
  unsold_units: number;
  velocity_score: number;
}

export interface CockpitResponse {
  generated_at: string;
  tenant_id: string;
  project_id: string | null;
  window_months: number;
  sales_velocity: ExecutiveMonthPoint[];
  collections: CollectionsMonthPoint[];
  inventory: InventorySummary;
  approvals: ApprovalsSummary;
  overdue_installments: OverdueInstallmentsSummary;
  ticket_sla: TicketSlaSummary;
  project_ranking: ProjectRankRow[];
}

export interface BriefingCounts {
  leads: number;
  visits_completed: number;
  visit_bookings_created: number;
  visit_bookings_cancelled: number;
  sale_bookings: number;
  sale_booking_value_paise: number;
  receipts: number;
  receipts_paise: number;
  tickets_created: number;
  tickets_resolved: number;
  approvals_decided: number;
}

export interface BriefingOpenItems {
  approvals_pending: number;
  tickets_breaching_sla: number;
  overdue_installments: number;
  overdue_amount_paise: number;
  unassigned_active_leads: number;
  active_sale_bookings: number;
}

export interface BriefingResponse {
  briefing_date: string;
  generated_at: string;
  tenant_id: string;
  counts: BriefingCounts;
  open_items: BriefingOpenItems;
  lines: string[];
}

// ---------------------------------------------------------------------------
// Pure transform helpers (unit-tested)
// ---------------------------------------------------------------------------

// 1 lakh = 1e7 paise, 1 crore = 1e9 paise (1 rupee = 100 paise).
const LAKH_PAISE = 10_000_000;
const CRORE_PAISE = 1_000_000_000;

/** Format integer paise as compact Indian INR (Cr / L / grouped rupees). */
export function formatPaise(paise: number): string {
  if (!Number.isFinite(paise) || paise === 0) return "₹0";
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  if (abs >= CRORE_PAISE) return `${sign}₹${(abs / CRORE_PAISE).toFixed(2)} Cr`;
  if (abs >= LAKH_PAISE) return `${sign}₹${(abs / LAKH_PAISE).toFixed(2)} L`;
  return `${sign}₹${Math.round(abs / 100).toLocaleString("en-IN")}`;
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Render an ISO first-of-month date as a short label like "Nov '26". */
export function formatMonthLabel(isoMonth: string): string {
  const parts = isoMonth.split("-");
  if (parts.length < 3) return isoMonth;
  const year = Number(parts[0]);
  const monthIndex = Number(parts[1]) - 1;
  if (!Number.isInteger(year) || !Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11) {
    return isoMonth;
  }
  return `${MONTH_LABELS[monthIndex]} '${String(year).slice(-2)}`;
}

/** Render an ISO date as "1 Nov" for table and tick labels. */
export function formatDayLabel(isoDate: string): string {
  const parts = isoDate.split("-");
  if (parts.length < 3) return isoDate;
  const monthIndex = Number(parts[1]) - 1;
  const day = Number(parts[2]);
  if (!Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11 || !Number.isInteger(day)) {
    return isoDate;
  }
  return `${day} ${MONTH_LABELS[monthIndex]}`;
}

export interface VelocitySeriesPoint {
  month: string;
  label: string;
  enquiries: number;
  visits: number;
  bookings: number;
  valuePaise: number;
}

/** Normalize raw API month points into a chart-ready series (no gaps added — the
 * backend already emits a full month grid). */
export function toVelocitySeries(points: ExecutiveMonthPoint[]): VelocitySeriesPoint[] {
  return points.map((p) => ({
    month: p.month,
    label: formatMonthLabel(p.month),
    enquiries: p.enquiries,
    visits: p.visits_completed,
    bookings: p.bookings,
    valuePaise: p.booking_value_paise,
  }));
}

export interface CollectionsSeriesPoint {
  month: string;
  label: string;
  collectedPaise: number;
  receipts: number;
}

export function toCollectionsSeries(points: CollectionsMonthPoint[]): CollectionsSeriesPoint[] {
  return points.map((p) => ({
    month: p.month,
    label: formatMonthLabel(p.month),
    collectedPaise: p.collected_paise,
    receipts: p.receipt_count,
  }));
}

/** Sum the trailing `n` months of a series to a single KPI total. */
export function trailingSum(series: VelocitySeriesPoint[], key: "enquiries" | "visits" | "bookings" | "valuePaise", n = 3): number {
  return series.slice(-n).reduce((acc, p) => acc + p[key], 0);
}

export function collectionsTrailingSum(series: CollectionsSeriesPoint[], n = 3): number {
  return series.slice(-n).reduce((acc, p) => acc + p.collectedPaise, 0);
}

/** "Nice" y-axis maximum + step for a count chart. Deterministic. */
export function niceAxis(rawMax: number): { max: number; step: number } {
  if (rawMax <= 4) return { max: Math.max(4, rawMax), step: 1 };
  const magnitude = 10 ** Math.floor(Math.log10(rawMax));
  const normalized = rawMax / magnitude;
  const step =
    normalized <= 1 ? magnitude / 4 :
    normalized <= 2 ? magnitude / 2 :
    normalized <= 5 ? magnitude :
    magnitude * 2;
  const max = Math.ceil(rawMax / step) * step;
  return { max, step };
}

export interface ChartTick {
  value: number;
}

export function axisTicks(rawMax: number): { max: number; ticks: number[] } {
  const { max, step } = niceAxis(rawMax);
  const ticks: number[] = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);
  return { max, ticks };
}
