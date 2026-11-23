import { bearerRequest } from "../shared/apiRequest";
import { clearSession, getSession } from "../auth/session";
import type {
  AvailabilityResponse,
  BulkUnitCreateResponse,
  FetchUnitsParams,
  HoldConvertResponse,
  HoldResponse,
  Unit,
  UnitCreateRequest,
  UnitDetail,
  UnitEventSource,
  UnitListResponse,
  UnitStatus,
  UnitUpdateRequest,
} from "./inventoryModel";
import { buildUnitsQuery } from "./inventoryModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(path, { getToken: getSession, clearToken: clearSession }, init);
}

export function fetchUnits(params: FetchUnitsParams): Promise<UnitListResponse> {
  return request<UnitListResponse>(`/inventory/units?${buildUnitsQuery(params)}`);
}

export function fetchUnit(unitId: string): Promise<UnitDetail> {
  return request<UnitDetail>(`/inventory/units/${unitId}`);
}

export function fetchAvailability(projectId: string): Promise<AvailabilityResponse> {
  const id = projectId.trim();
  if (!id) {
    // The map page renders before a project is selected; an empty id would hit
    // /availability/ (404). Resolve to empty counts instead of a failed call.
    return Promise.resolve({ project_id: "", counts: {}, total: 0 });
  }
  return request<AvailabilityResponse>(`/inventory/availability/${id}`);
}

export function bulkCreateUnits(
  rows: UnitCreateRequest[],
  dryRun: boolean,
): Promise<BulkUnitCreateResponse> {
  return request<BulkUnitCreateResponse>(
    `/inventory/units/bulk?dry_run=${dryRun ? "true" : "false"}`,
    { method: "POST", body: JSON.stringify({ rows }) },
  );
}

export function updateUnit(
  unitId: string,
  payload: UnitUpdateRequest,
): Promise<Unit> {
  return request<Unit>(`/inventory/units/${unitId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/** Only the backend's guarded DRAFT-only delete; progressed units must use the
 * state machine, and the server enforces that regardless of what is sent. */
export function deleteUnit(unitId: string): Promise<void> {
  return request<void>(`/inventory/units/${unitId}`, { method: "DELETE" });
}

export interface TransitionUnitPayload {
  to_status: UnitStatus;
  reason: string | null;
  source: UnitEventSource;
  approved: boolean;
}

export function transitionUnit(
  unitId: string,
  payload: TransitionUnitPayload,
): Promise<Unit> {
  return request<Unit>(`/inventory/units/${unitId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export interface CreateHoldPayload {
  unit_id: string;
  lead_id: string | null;
  opportunity_ref: string | null;
  hours: number;
  reason: string | null;
}

export function createHold(payload: CreateHoldPayload): Promise<HoldResponse> {
  return request<HoldResponse>("/inventory/holds", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function extendHold(
  holdId: string,
  payload: { hours: number; reason: string | null },
): Promise<HoldResponse> {
  return request<HoldResponse>(`/inventory/holds/${holdId}/extend`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function releaseHold(holdId: string, reason: string): Promise<HoldResponse> {
  return request<HoldResponse>(`/inventory/holds/${holdId}/release`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function reserveHold(holdId: string): Promise<Unit> {
  return request<Unit>(`/inventory/holds/${holdId}/reserve`, { method: "POST" });
}

export function convertHold(
  holdId: string,
  payload: { consideration_paise: number; booked_on: string | null },
): Promise<HoldConvertResponse> {
  return request<HoldConvertResponse>(`/inventory/holds/${holdId}/convert`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
