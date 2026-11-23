// Types + pure transforms for the operator Revenue Command Centre.
// All monetary values are integer paise.

export interface AtRiskSummary {
  past_due_count: number;
  past_due_mrr_paise: number;
  halted_count: number;
  halted_mrr_paise: number;
}

export interface InvoicedMonthPoint {
  month: string; // ISO first-of-month
  invoiced_paise: number;
  invoice_count: number;
}

export interface PaymentFailureSummary {
  count_last_30_days: number;
  halted_tenants: number;
}

export interface ExpansionSignal {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  meter: "leads" | "whatsapp_sent" | "users" | string;
  used: number;
  limit: number;
  ratio: number;
  period_source: string;
}

export interface RenewalRow {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  plan_name: string;
  period_end: string;
  days_until: number;
  price_paise: number;
}

export interface RenewalsSummary {
  window_days: number;
  count: number;
  mrr_at_stake_paise: number;
  subscriptions: RenewalRow[];
}

export interface RevenueSummaryResponse {
  generated_at: string;
  window_months: number;
  mrr_paise: number;
  arr_paise: number;
  active_subscriptions: number;
  at_risk: AtRiskSummary;
  invoiced: InvoicedMonthPoint[];
  failures: PaymentFailureSummary;
  expansion_signals: ExpansionSignal[];
  renewals: RenewalsSummary;
}

// ---------------------------------------------------------------------------
// Pure helpers (unit-tested)
// ---------------------------------------------------------------------------

// 1 lakh = 1e7 paise, 1 crore = 1e9 paise (1 rupee = 100 paise).
const LAKH_PAISE = 10_000_000;
const CRORE_PAISE = 1_000_000_000;

export function formatRevenuePaise(paise: number): string {
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

export function revenueMonthLabel(isoMonth: string): string {
  const parts = isoMonth.split("-");
  if (parts.length < 3) return isoMonth;
  const year = Number(parts[0]);
  const monthIndex = Number(parts[1]) - 1;
  if (!Number.isInteger(year) || !Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11) {
    return isoMonth;
  }
  return `${MONTH_LABELS[monthIndex]} '${parts[0].slice(-2)}`;
}

export interface InvoicedSeriesPoint {
  month: string;
  label: string;
  invoicedPaise: number;
  invoices: number;
}

export function toInvoicedSeries(points: InvoicedMonthPoint[]): InvoicedSeriesPoint[] {
  return points.map((p) => ({
    month: p.month,
    label: revenueMonthLabel(p.month),
    invoicedPaise: p.invoiced_paise,
    invoices: p.invoice_count,
  }));
}

export function meterLabel(meter: string): string {
  switch (meter) {
    case "leads":
      return "Monthly leads";
    case "whatsapp_sent":
      return "WhatsApp messages";
    case "users":
      return "Active users";
    default:
      return meter;
  }
}

export function renewalUrgency(daysUntil: number): "overdue" | "soon" | "later" {
  if (daysUntil <= 0) return "overdue";
  if (daysUntil <= 7) return "soon";
  return "later";
}
