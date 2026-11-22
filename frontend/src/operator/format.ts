import type { PlanFeatureInput } from "./operatorModel.ts";
import { humanizeIdentifier } from "./operatorModel.ts";

export { humanizeIdentifier };

export function paiseToRupeesInput(paise: number): string {
  const rupees = paise / 100;
  return Number.isInteger(rupees) ? String(rupees) : rupees.toFixed(2);
}

export function rupeesInputToPaise(value: string): number {
  const trimmed = value.trim();
  if (!/^\d+(\.\d{0,2})?$/.test(trimmed)) return Number.NaN;
  return Math.round(Number(trimmed) * 100);
}

export function formatInrFromPaise(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: paise % 100 === 0 ? 0 : 2,
  }).format(paise / 100);
}

/** Feature rows are validated by the plan form; only non-empty rows survive. */
export function featureRowsToRecord(
  rows: PlanFeatureInput[],
): Record<string, unknown> {
  return rows.reduce<Record<string, unknown>>((record, row) => {
    const key = row.key.trim();
    if (key) record[key] = row.value.trim() || true;
    return record;
  }, {});
}

export function featureRecordToRows(
  features: Record<string, unknown>,
): PlanFeatureInput[] {
  return Object.entries(features).map(([key, value]) => ({
    key,
    value:
      value === true
        ? ""
        : typeof value === "object" && value !== null
          ? JSON.stringify(value)
          : String(value),
  }));
}

export function formatDateTime(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
