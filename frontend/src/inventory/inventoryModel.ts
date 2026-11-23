import type { ProjectType } from "../admin/projectModel";

export type UnitStatus =
  | "DRAFT"
  | "APPROVED"
  | "AVAILABLE"
  | "ON_HOLD"
  | "RESERVED"
  | "BOOKED"
  | "SOLD"
  | "BLOCKED"
  | "UNDER_DISPUTE"
  | "CANCELLED";

export type HoldState = "ACTIVE" | "EXPIRED" | "CONVERTED" | "RELEASED" | "CANCELLED";
export type UnitEventSource = "MANUAL" | "HOLD" | "BOOKING" | "CANCELLATION";
export type HoldReleaseSource = "EXPIRY" | "MANUAL" | "CONVERTED" | "CANCELLED";

export const UNIT_STATUSES: readonly UnitStatus[] = [
  "DRAFT",
  "APPROVED",
  "AVAILABLE",
  "ON_HOLD",
  "RESERVED",
  "BOOKED",
  "SOLD",
  "BLOCKED",
  "UNDER_DISPUTE",
  "CANCELLED",
];

export const MAX_HOLD_EXTENSIONS = 2;
export const DEFAULT_HOLD_HOURS = 48;

export interface Unit {
  id: string;
  project_id: string;
  internal_code: string;
  configuration: string | null;
  floor: string | null;
  position: string | null;
  tower: string | null;
  carpet_area_sqft: number | null;
  built_up_area_sqft: number | null;
  plot_number: string | null;
  facing: string | null;
  views: string | null;
  saleable: boolean;
  status: UnitStatus;
  status_reason: string | null;
  rera_disclosure_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface UnitListResponse {
  items: Unit[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UnitStatusEvent {
  id: string;
  unit_id: string;
  from_status: UnitStatus;
  to_status: UnitStatus;
  actor_user_id: string | null;
  reason: string | null;
  source: UnitEventSource;
  effective_at: string;
  event_meta: Record<string, unknown>;
}

export interface UnitDetail extends Unit {
  status_history: UnitStatusEvent[];
}

export interface UnitCreateRequest {
  project_id: string;
  internal_code: string;
  configuration: string | null;
  floor: string | null;
  position: string | null;
  tower: string | null;
  carpet_area_sqft: number | null;
  built_up_area_sqft: number | null;
  plot_number: string | null;
  facing: string | null;
  views: string | null;
  saleable: boolean;
  status: UnitStatus;
  status_reason: string | null;
  rera_disclosure_json: Record<string, unknown>;
}

/**
 * Mutable unit fields for the edit dialog. ``internal_code`` and ``status``
 * are intentionally absent: the code is the canonical identity and status
 * changes go through the state-machine transition endpoint only.
 */
export interface UnitUpdateRequest {
  configuration?: string | null;
  floor?: string | null;
  position?: string | null;
  tower?: string | null;
  carpet_area_sqft?: number | null;
  built_up_area_sqft?: number | null;
  plot_number?: string | null;
  facing?: string | null;
  views?: string | null;
  saleable?: boolean;
  rera_disclosure_json?: Record<string, unknown>;
}

export interface BulkRowResult {
  index: number;
  internal_code: string;
  ok: boolean;
  unit_id: string | null;
  reason: string | null;
}

export interface BulkUnitCreateResponse {
  dry_run: boolean;
  results: BulkRowResult[];
  created: number;
  failed: number;
}

export interface HoldResponse {
  id: string;
  unit_id: string;
  lead_id: string | null;
  opportunity_ref: string | null;
  owner_user_id: string;
  reason: string | null;
  state: HoldState;
  expires_at: string;
  extension_count: number;
  converted_booking_id: string | null;
  released_at: string | null;
  release_source: HoldReleaseSource | null;
  created_at: string;
}

export interface HoldConvertResponse {
  hold: HoldResponse;
  booking_id: string;
}

export interface AvailabilityResponse {
  project_id: string;
  counts: Record<string, number>;
  total: number;
}

export interface FetchUnitsParams {
  projectId: string;
  status?: UnitStatus | "ALL";
  page?: number;
  pageSize?: number;
}

/** Build the /inventory/units query string, omitting an empty/whitespace
 * `project_id`. FastAPI coerces `project_id=` (empty) to UUID and returns 422
 * "Request validation failed"; omitting it lists the tenant's units instead.
 * Pure helper so it is unit-testable without a DOM/fetch. */
export function buildUnitsQuery(params: FetchUnitsParams): string {
  const query = new URLSearchParams();
  const projectId = params.projectId.trim();
  if (projectId) query.set("project_id", projectId);
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.pageSize ?? 20));
  if (params.status && params.status !== "ALL") query.set("status", params.status);
  return query.toString();
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

/**
 * Unit authoring guidance derived from the project's type. Mirrors
 * backend/app/modules/inventory/authoring.py: tower+floor for apartment and
 * commercial units, plot_number for villa and plot units, no restrictions for
 * mixed or untyped projects. Used for form hints and for matching server
 * validation errors back to form fields.
 */
export interface UnitAuthoringGuidance {
  requiresTower: boolean;
  requiresFloor: boolean;
  requiresPlotNumber: boolean;
  disallowsPlotNumber: boolean;
  disallowsTower: boolean;
  floorHint: string | null;
  summary: string;
}

export function unitAuthoringGuidance(
  projectType: ProjectType | null | undefined,
): UnitAuthoringGuidance {
  const none: UnitAuthoringGuidance = {
    requiresTower: false,
    requiresFloor: false,
    requiresPlotNumber: false,
    disallowsPlotNumber: false,
    disallowsTower: false,
    floorHint: null,
    summary: "This project has no type restrictions; tower, floor and plot number are all optional.",
  };
  if (!projectType || projectType === "MIXED") {
    return {
      ...none,
      summary: projectType === "MIXED"
        ? "Mixed development: units may use either tower/floor or plot numbering; no per-type restrictions apply."
        : none.summary,
    };
  }
  if (projectType === "APARTMENT" || projectType === "COMMERCIAL") {
    return {
      requiresTower: true,
      requiresFloor: true,
      requiresPlotNumber: false,
      disallowsPlotNumber: projectType === "APARTMENT",
      disallowsTower: false,
      floorHint: null,
      summary: projectType === "APARTMENT"
        ? "Apartment units require tower and floor. Plot number must be left empty."
        : `Commercial units require tower and floor.`,
    };
  }
  // VILLA and PLOT
  const noun = projectType.toLowerCase();
  return {
    requiresTower: false,
    requiresFloor: false,
    requiresPlotNumber: true,
    disallowsPlotNumber: false,
    disallowsTower: true,
    floorHint: "Ground/basement blocks such as G, GF or B1 are allowed; numbered storeys are not.",
    summary: `${noun.charAt(0).toUpperCase() + noun.slice(1)} units require a plot number. Tower must be empty; floor may be empty or a ground/basement block such as G or B1.`,
  };
}

/** Map one row of CSV onto the fields relevant to the project's type, if known. */
export function plotNumberColumnRequired(projectType: ProjectType | null | undefined): boolean {
  return projectType === "VILLA" || projectType === "PLOT";
}

/** Server-side inventory errors arrive as human-readable sentences joined by spaces. */
export function splitUnitValidationMessage(message: string): string[] {
  return message
    .split(/(?<=\.)\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export type StatusTone = "emerald" | "amber" | "violet" | "blue" | "sky" | "rose" | "slate" | "stone";
export type StatusIconName =
  | "circle-check"
  | "hourglass"
  | "shield-check"
  | "book-check"
  | "badge-check"
  | "lock"
  | "gavel"
  | "file"
  | "file-check"
  | "ban"
  | "circle-alert";

export interface StatusVisual {
  label: string;
  icon: StatusIconName;
  tone: StatusTone;
}

const STATUS_VISUALS: Readonly<Record<UnitStatus, StatusVisual>> = {
  DRAFT: { label: "Draft", icon: "file", tone: "stone" },
  APPROVED: { label: "Approved", icon: "file-check", tone: "slate" },
  AVAILABLE: { label: "Available", icon: "circle-check", tone: "emerald" },
  ON_HOLD: { label: "On hold", icon: "hourglass", tone: "amber" },
  RESERVED: { label: "Reserved", icon: "shield-check", tone: "violet" },
  BOOKED: { label: "Booked", icon: "book-check", tone: "blue" },
  SOLD: { label: "Sold", icon: "badge-check", tone: "sky" },
  BLOCKED: { label: "Blocked", icon: "lock", tone: "rose" },
  UNDER_DISPUTE: { label: "Under dispute", icon: "gavel", tone: "rose" },
  CANCELLED: { label: "Cancelled", icon: "ban", tone: "stone" },
};

const UNKNOWN_STATUS_VISUAL: StatusVisual = {
  label: "Unknown",
  icon: "circle-alert",
  tone: "stone",
};

export function isUnitStatus(value: string): value is UnitStatus {
  return UNIT_STATUSES.includes(value as UnitStatus);
}

const UUID_PATTERN =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

export function statusVisual(status: string): StatusVisual {
  return isUnitStatus(status) ? STATUS_VISUALS[status] : UNKNOWN_STATUS_VISUAL;
}

export function statusLabel(status: string): string {
  if (isUnitStatus(status)) return STATUS_VISUALS[status].label;
  return status.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export interface FloorGroup {
  floor: string;
  units: Unit[];
}

export interface TowerGroup {
  tower: string;
  floors: FloorGroup[];
}

function compareNumericAware(a: string, b: string): number {
  const aNum = Number(a);
  const bNum = Number(b);
  if (Number.isFinite(aNum) && Number.isFinite(bNum)) return aNum - bNum;
  return a.localeCompare(b, undefined, { numeric: true });
}

export const UNASSIGNED_TOWER = "Unassigned tower";
export const UNASSIGNED_FLOOR = "Unassigned floor";

/** Group units into towers (alphabetical) → floors (numeric-aware descending). */
export function groupUnitsByFloorTower(units: readonly Unit[]): TowerGroup[] {
  const byTower = new Map<string, Map<string, Unit[]>>();
  for (const unit of units) {
    const tower = unit.tower?.trim() || UNASSIGNED_TOWER;
    const floor = unit.floor?.trim() || UNASSIGNED_FLOOR;
    const floors = byTower.get(tower) ?? new Map<string, Unit[]>();
    if (!byTower.has(tower)) byTower.set(tower, floors);
    floors.set(floor, [...(floors.get(floor) ?? []), unit]);
  }

  return [...byTower.keys()]
    .sort((a, b) => compareNumericAware(a, b))
    .map((tower) => {
      const floors = byTower.get(tower) ?? new Map<string, Unit[]>();
      return {
        tower,
        floors: [...floors.keys()]
          .sort((a, b) => compareNumericAware(b, a))
          .map((floor) => ({
            floor,
            units: [...(floors.get(floor) ?? [])].sort((a, b) =>
              a.internal_code.localeCompare(b.internal_code, undefined, { numeric: true }),
            ),
          })),
      };
    });
}

/**
 * Convert a rupee string to integer paise. Amounts are rounded to the nearest
 * paise (12.345 -> 1235); negative, non-numeric, or non-finite values are NaN.
 * Callers must treat NaN as a validation error before submitting.
 */
export function rupeesToPaise(rupees: string): number {
  const trimmed = rupees.trim().replace(/,/g, "");
  if (!trimmed || !/^\d+(\.\d+)?$/.test(trimmed)) return Number.NaN;
  const value = Number(trimmed) * 100;
  if (!Number.isFinite(value) || value < 0) return Number.NaN;
  return Math.round(value);
}

const rupeeFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function paiseToRupeesFormat(paise: number): string {
  if (!Number.isFinite(paise)) return "—";
  return `₹${rupeeFormatter.format(paise / 100)}`;
}

export interface CsvParseError {
  row: number;
  message: string;
}

export interface BulkCsvResult {
  rows: UnitCreateRequest[];
  errors: CsvParseError[];
}

interface CsvHeader {
  internal_code: number;
  configuration: number;
  facing: number;
  carpet_area: number;
  floor: number;
  tower: number;
  position: number;
  built_up_area: number;
  plot_number: number;
  status: number;
}

const HEADER_ALIASES: Readonly<Record<string, keyof CsvHeader>> = {
  code: "internal_code",
  internal_code: "internal_code",
  configuration: "configuration",
  config: "configuration",
  facing: "facing",
  carpet_area: "carpet_area",
  carpet_area_sqft: "carpet_area",
  floor: "floor",
  tower: "tower",
  position: "position",
  built_up_area: "built_up_area",
  built_up_area_sqft: "built_up_area",
  plot_number: "plot_number",
  plot: "plot_number",
  plot_no: "plot_number",
  status: "status",
};

/** Split one CSV line, honouring double-quoted fields and escaped quotes. */
function parseCsvLine(line: string): string[] | null {
  const fields: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      fields.push(field);
      field = "";
    } else {
      field += char;
    }
  }
  if (inQuotes) return null;
  fields.push(field);
  return fields;
}

function emptyToNull(value: string | undefined): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed || null;
}

const CREATABLE_STATUSES: readonly UnitStatus[] = ["DRAFT", "APPROVED", "AVAILABLE"];

/**
 * Parse pasted CSV (code,configuration,facing,carpet_area[,floor,tower,plot_number,...])
 * into UnitCreateRequest rows with per-row validation errors. Valid rows are
 * still returned alongside errors so the backend dry-run sees every good row.
 * plot_number (aliases plot, plot_no) is required by the server for villa and
 * plot projects and forbidden for apartment projects; that per-type check is
 * intentionally left to the server so the dry run surfaces its message verbatim.
 */
export function bulkCsvParse(csv: string, projectId: string): BulkCsvResult {
  const rows: UnitCreateRequest[] = [];
  const errors: CsvParseError[] = [];
  const lines = csv.split(/\r?\n/);
  const firstContent = lines.find((line) => line.trim());
  if (!firstContent) return { rows, errors };

  const header = parseCsvLine(firstContent);
  if (!header) {
    return { rows, errors: [{ row: 1, message: "Unclosed quoted field in header." }] };
  }
  const columns: Partial<CsvHeader> = {};
  header.forEach((name, index) => {
    const key = HEADER_ALIASES[name.trim().toLowerCase()];
    if (key !== undefined) columns[key] = index;
  });
  const headerLine = lines.indexOf(firstContent);

  if (columns.internal_code === undefined) {
    return { rows, errors: [{ row: headerLine + 1, message: "Header must include a code column." }] };
  }

  const seenCodes = new Set<string>();
  for (let i = headerLine + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.trim()) continue;
    const rowNumber = i + 1;
    const fields = parseCsvLine(line);
    if (!fields) {
      errors.push({ row: rowNumber, message: "Unclosed quoted field." });
      continue;
    }
    const cell = (key: keyof CsvHeader): string | undefined => {
      const index = columns[key];
      return index === undefined ? undefined : fields[index];
    };
    const code = cell("internal_code")?.trim() ?? "";
    if (!code) {
      errors.push({ row: rowNumber, message: "Unit code is required." });
      continue;
    }
    if (code.length > 64) {
      errors.push({ row: rowNumber, message: "Unit code must be 64 characters or fewer." });
      continue;
    }
    if (seenCodes.has(code)) {
      errors.push({ row: rowNumber, message: `Duplicate code "${code}" in this import.` });
      continue;
    }
    const carpetRaw = cell("carpet_area")?.trim() ?? "";
    const builtUpRaw = cell("built_up_area")?.trim() ?? "";
    const carpet = carpetRaw ? Number(carpetRaw) : null;
    const builtUp = builtUpRaw ? Number(builtUpRaw) : null;
    if (carpet !== null && (!Number.isInteger(carpet) || carpet <= 0)) {
      errors.push({ row: rowNumber, message: "carpet_area must be a positive whole number (sqft)." });
      continue;
    }
    if (builtUp !== null && (!Number.isInteger(builtUp) || builtUp <= 0)) {
      errors.push({ row: rowNumber, message: "built_up_area must be a positive whole number (sqft)." });
      continue;
    }
    const statusRaw = (cell("status")?.trim() || "AVAILABLE").toUpperCase();
    if (!CREATABLE_STATUSES.includes(statusRaw as UnitStatus)) {
      errors.push({ row: rowNumber, message: "status must be DRAFT, APPROVED, or AVAILABLE." });
      continue;
    }
    seenCodes.add(code);
    rows.push({
      project_id: projectId,
      internal_code: code,
      configuration: emptyToNull(cell("configuration")),
      floor: emptyToNull(cell("floor")),
      position: emptyToNull(cell("position")),
      tower: emptyToNull(cell("tower")),
      carpet_area_sqft: carpet,
      built_up_area_sqft: builtUp,
      plot_number: emptyToNull(cell("plot_number")),
      facing: emptyToNull(cell("facing")),
      views: null,
      saleable: true,
      status: statusRaw as UnitStatus,
      status_reason: null,
      rera_disclosure_json: {},
    });
  }
  return { rows, errors };
}

/** Format a countdown like "47h 12m" / "12m 05s" / "Expired" for hold expiry. */
export function holdCountdown(expiresAt: string, nowMs: number): string {
  const expiryMs = new Date(expiresAt).getTime();
  if (!Number.isFinite(expiryMs)) return "Unknown expiry";
  const remaining = expiryMs - nowMs;
  if (remaining <= 0) return "Expired";
  const totalSeconds = Math.floor(remaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

/** Header the bulk CSV parser accepts (aliases covered: code/config/plot/...). */
export const SAMPLE_UNIT_CSV = [
  "code,configuration,facing,carpet_area,floor,tower,position,built_up_area,plot_number,status",
  "A-101,2 BHK,East,1200,1,A,Corner,1350,,AVAILABLE",
  "A-102,3 BHK,West,1450,2,A,,1600,,AVAILABLE",
  "A-103,3 BHK,North East,1500,3,B,,1680,,DRAFT",
  "P-201,Plot,North,2400,,,,2400,P-201,AVAILABLE",
].join("\n");

/** Trigger a browser download of a text file (sample CSV for bulk import). */
export function downloadTextFile(filename: string, text: string): void {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
