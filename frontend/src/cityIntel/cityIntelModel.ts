/**
 * Types and pure helpers for the City Intelligence dashboard (Phase 1).
 * Response shapes mirror backend/app/modules/city_intel/schemas.py.
 */

export interface LocalityDemand {
  project_id: string;
  locality: string;
  project_name: string;
  lead_count: number;
  booking_count: number;
  conversion_pct: number;
  median_budget_paise: number | null;
  top_price_band: string;
  top_property_type: string;
}

export interface DemandResponse {
  items: LocalityDemand[];
  total: number;
}

export interface Amenity {
  id: string;
  project_id: string;
  category: string;
  name: string;
  distance_km: number;
  travel_minutes: number;
  source_ref: string | null;
  confidence: string;
  as_of: string | null;
  created_at: string;
}

export interface AmenityListResponse {
  items: Amenity[];
  total: number;
}

export interface CategorySummary {
  category: string;
  count: number;
  nearest_km: number | null;
  nearest_travel_minutes: number | null;
}

export interface ConnectivityResponse {
  project_id: string;
  score: number;
  by_category: CategorySummary[];
  notes: string[];
}

export interface ReportSource {
  label: string;
  ref?: string | null;
  observed_on?: string | null;
  confidence: string;
}

export interface LocalityReport {
  id: string;
  project_id: string;
  title: string;
  body: string;
  sources: ReportSource[];
  status: string;
  as_of: string | null;
  created_at: string;
}

export interface LocalityReportListResponse {
  items: LocalityReport[];
  total: number;
}

// ---------------------------------------------------------------------------
// Pure helpers (unit-tested, no DOM/fetch)
// ---------------------------------------------------------------------------

export type Confidence = "verified" | "estimated" | "unverified";

/** Confidence rank for display: most certain first. */
export function confidenceRank(confidence: string): number {
  switch (confidence) {
    case "verified":
      return 0;
    case "estimated":
      return 1;
    default:
      return 2;
  }
}

/** Sort reports: verified-confidence sources first, then newest as_of. */
export function sortReports(reports: readonly LocalityReport[]): LocalityReport[] {
  return [...reports].sort((a, b) => {
    const ac = bestConfidence(a.sources);
    const bc = bestConfidence(b.sources);
    if (confidenceRank(ac) !== confidenceRank(bc)) {
      return confidenceRank(ac) - confidenceRank(bc);
    }
    return (b.as_of ?? "").localeCompare(a.as_of ?? "");
  });
}

/** The strongest confidence present among a report's sources. */
export function bestConfidence(sources: readonly ReportSource[]): Confidence {
  if (sources.some((s) => s.confidence === "verified")) return "verified";
  if (sources.some((s) => s.confidence === "estimated")) return "estimated";
  return "unverified";
}

/** Sort demand rows by lead count desc, then locality asc. */
export function sortDemand(rows: readonly LocalityDemand[]): LocalityDemand[] {
  return [...rows].sort(
    (a, b) => b.lead_count - a.lead_count || a.locality.localeCompare(b.locality),
  );
}

/** Fixed display order for the 5 amenity categories. */
export const CATEGORY_ORDER = ["school", "hospital", "transit", "employment", "amenity"] as const;

export function orderedCategories(summaries: readonly CategorySummary[]): CategorySummary[] {
  return [...summaries].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a.category as (typeof CATEGORY_ORDER)[number]) -
      CATEGORY_ORDER.indexOf(b.category as (typeof CATEGORY_ORDER)[number]),
  );
}

/** Human label for an amenity category. */
export function categoryLabel(category: string): string {
  switch (category) {
    case "school":
      return "Schools";
    case "hospital":
      return "Hospitals";
    case "transit":
      return "Transit";
    case "employment":
      return "Employment hubs";
    case "amenity":
      return "Amenities";
    default:
      return category;
  }
}

/** Format a connectivity score into a band label (advisory, not a guarantee). */
export function connectivityBand(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 60) return "Good";
  if (score >= 40) return "Moderate";
  if (score > 0) return "Limited";
  return "No data";
}

/** Distance display like "1.2 km" or "500 m". */
export function distanceLabel(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1)} km`;
}
