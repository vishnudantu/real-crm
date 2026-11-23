import { bearerRequest } from "../shared/apiRequest";
import { clearSession, getSession } from "../auth/session";
import type {
  CoordinatesUpdateResponse,
  SunPathResponse,
  TowerOrientationResponse,
  UnitSunScoreResponse,
} from "./solarModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(path, { getToken: getSession, clearToken: clearSession }, init);
}

export function fetchSunPath(projectId: string): Promise<SunPathResponse> {
  return request<SunPathResponse>(`/solar/projects/${projectId}/sun-path`);
}

export function fetchUnitSunScore(unitId: string): Promise<UnitSunScoreResponse> {
  return request<UnitSunScoreResponse>(`/solar/units/${unitId}/sun-score`);
}

export function updateProjectCoordinates(
  projectId: string,
  latitude: number,
  longitude: number,
): Promise<CoordinatesUpdateResponse> {
  return request<CoordinatesUpdateResponse>(`/solar/projects/${projectId}/coordinates`, {
    method: "PATCH",
    body: JSON.stringify({ latitude, longitude }),
  });
}

export function upsertTowerOrientation(
  projectId: string,
  towerLabel: string,
  orientationDeg: number,
): Promise<TowerOrientationResponse> {
  return request<TowerOrientationResponse>("/solar/tower-orientation", {
    method: "PUT",
    body: JSON.stringify({
      project_id: projectId,
      tower_label: towerLabel,
      orientation_deg: orientationDeg,
    }),
  });
}
