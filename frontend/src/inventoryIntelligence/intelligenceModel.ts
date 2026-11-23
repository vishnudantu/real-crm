/**
 * Types and pure helpers for the Inventory Intelligence dashboard (Module 20).
 * Response shapes mirror backend/app/modules/inventory/intelligence/schemas.py.
 */

export interface RevenueRow {
  unit_id: string;
  internal_code: string;
  status: string;
  booked_value_paise: number | null;
  age_days: number;
}

export interface RevenueMapResponse {
  total_units: number;
  by_status: Record<string, number>;
  total_booked_value_paise: number;
  avg_unit_age_days: number;
  oldest_unit_age_days: number;
  rows: RevenueRow[];
}

export interface HoldExpiryRisk {
  hold_id: string;
  unit_id: string;
  expires_at: string;
  hours_remaining: number;
  extension_count: number;
  risk: "LOW" | "MEDIUM" | "HIGH";
}

export interface HoldExpiryResponse {
  items: HoldExpiryRisk[];
  total: number;
}

export interface UnsoldRisk {
  unit_id: string;
  internal_code: string;
  status: string;
  days_available: number;
  risk: "LOW" | "MEDIUM" | "HIGH";
}

export interface UnsoldRiskResponse {
  items: UnsoldRisk[];
  total: number;
  medium_days: number;
  high_days: number;
}

export interface UnitConflict {
  unit_id: string;
  code: string;
  kind: string;
  detail: string;
}

export interface ConflictResponse {
  items: UnitConflict[];
  total: number;
}

export interface UnitRecommendation {
  unit_id: string;
  internal_code: string;
  score: number;
  reasons: string[];
}

export interface RecommendationResponse {
  requested_unit_id: string;
  items: UnitRecommendation[];
  total: number;
}

// ---------------------------------------------------------------------------
// Pure helpers (unit-tested, no DOM/fetch)
// ---------------------------------------------------------------------------

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

/** Realization = booked value as a share of total inventory value is unknown
 * without a price book, so we expose realization as the share of units that
 * have a booking (BOOKED/SOLD) out of total units, as a 0-100 percentage. */
export function realizationPercent(byStatus: Record<string, number>, totalUnits: number): number {
  if (totalUnits <= 0) return 0;
  const realized = (byStatus.BOOKED ?? 0) + (byStatus.SOLD ?? 0);
  return Math.round((realized / totalUnits) * 1000) / 10;
}

/** Order the status tiles so the most actionable states appear first. */
const STATUS_ORDER = [
  "AVAILABLE",
  "ON_HOLD",
  "RESERVED",
  "BOOKED",
  "SOLD",
  "APPROVED",
  "DRAFT",
  "BLOCKED",
  "UNDER_DISPUTE",
  "CANCELLED",
];

export function orderedStatuses(byStatus: Record<string, number>): string[] {
  return Object.keys(byStatus).sort((a, b) => {
    const ia = STATUS_ORDER.indexOf(a);
    const ib = STATUS_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

export interface StatusTile {
  status: string;
  count: number;
  label: string;
}

const STATUS_LABELS: Record<string, string> = {
  AVAILABLE: "Available",
  ON_HOLD: "On hold",
  RESERVED: "Reserved",
  BOOKED: "Booked",
  SOLD: "Sold",
  APPROVED: "Approved",
  DRAFT: "Draft",
  BLOCKED: "Blocked",
  UNDER_DISPUTE: "Under dispute",
  CANCELLED: "Cancelled",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ").toLowerCase();
}

export function statusTiles(byStatus: Record<string, number>): StatusTile[] {
  return orderedStatuses(byStatus).map((status) => ({
    status,
    count: byStatus[status] ?? 0,
    label: statusLabel(status),
  }));
}

/** Group revenue rows by tower for the aging table. */
export interface TowerAging {
  tower: string;
  units: number;
  bookedValuePaise: number;
  oldestAgeDays: number;
}

export function towerAging(rows: RevenueRow[]): TowerAging[] {
  const byTower = new Map<string, { units: number; booked: number; oldest: number }>();
  for (const row of rows) {
    // internal_code is typically "<TOWER>-<NUMBER>"; fall back to "Other".
    const tower = row.internal_code.split("-")[0]?.trim() || "Other";
    const entry = byTower.get(tower) ?? { units: 0, booked: 0, oldest: 0 };
    entry.units += 1;
    entry.booked += row.booked_value_paise ?? 0;
    entry.oldest = Math.max(entry.oldest, row.age_days);
    byTower.set(tower, entry);
  }
  return [...byTower.entries()]
    .map(([tower, e]) => ({
      tower,
      units: e.units,
      bookedValuePaise: e.booked,
      oldestAgeDays: e.oldest,
    }))
    .sort((a, b) => b.units - a.units || a.tower.localeCompare(b.tower));
}

/** Sort urgency: HIGH first, then MEDIUM, then LOW; within a band, soonest first. */
const RISK_RANK: Record<RiskLevel, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

export function sortByUrgency<T extends { risk: RiskLevel; hours_remaining: number }>(
  items: readonly T[],
): T[] {
  return [...items].sort(
    (a, b) => RISK_RANK[a.risk] - RISK_RANK[b.risk] || a.hours_remaining - b.hours_remaining,
  );
}

export function sortUnsoldByRisk<T extends { risk: RiskLevel; days_available: number }>(
  items: readonly T[],
): T[] {
  return [...items].sort(
    (a, b) => RISK_RANK[a.risk] - RISK_RANK[b.risk] || b.days_available - a.days_available,
  );
}

/** Human label for a conflict kind constant from the backend. */
export function conflictLabel(kind: string): string {
  switch (kind) {
    case "MULTIPLE_ACTIVE_HOLDS":
      return "Multiple active holds";
    case "HOLD_WITHOUT_UNIT":
      return "Hold without unit";
    case "SOLD_WITH_ACTIVE_HOLD":
      return "Sold with active hold";
    case "BOOKED_WITH_ACTIVE_HOLD":
      return "Booked with active hold";
    default:
      return kind.replace(/_/g, " ").toLowerCase();
  }
}

/** Format hours-remaining into a compact urgency string. */
export function hoursRemainingLabel(hours: number): string {
  if (hours <= 0) return "Expired";
  if (hours < 1) return `${Math.round(hours * 60)}m left`;
  if (hours < 48) return `${Math.round(hours)}h left`;
  return `${Math.round(hours / 24)}d left`;
}
