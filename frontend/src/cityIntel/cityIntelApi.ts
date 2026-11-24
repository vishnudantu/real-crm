import { bearerRequest } from "../shared/apiRequest";
import { clearSession, getSession } from "../auth/session";
import type {
  Amenity,
  AmenityListResponse,
  ConnectivityResponse,
  DemandResponse,
  LocalityReport,
  LocalityReportListResponse,
} from "./cityIntelModel";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return bearerRequest<T>(path, { getToken: getSession, clearToken: clearSession }, init);
}

export function fetchDemand(): Promise<DemandResponse> {
  return request<DemandResponse>("/city-intel/demand");
}

export function fetchAmenities(projectId: string): Promise<AmenityListResponse> {
  return request<AmenityListResponse>(`/city-intel/projects/${projectId}/amenities`);
}

export function fetchConnectivity(projectId: string): Promise<ConnectivityResponse> {
  return request<ConnectivityResponse>(`/city-intel/projects/${projectId}/connectivity`);
}

export function fetchReports(projectId: string): Promise<LocalityReportListResponse> {
  return request<LocalityReportListResponse>(`/city-intel/projects/${projectId}/reports`);
}

export interface AmenityInput {
  project_id: string;
  category: string;
  name: string;
  distance_km: number;
  travel_minutes: number;
  source_ref?: string | null;
  confidence: string;
  as_of?: string | null;
}

export function addAmenity(payload: AmenityInput): Promise<Amenity> {
  return request<Amenity>("/city-intel/amenities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface ReportInput {
  project_id: string;
  title: string;
  body: string;
  sources: { label: string; ref?: string | null; observed_on?: string | null; confidence: string }[];
  as_of?: string | null;
}

export function createReport(payload: ReportInput): Promise<LocalityReport> {
  return request<LocalityReport>("/city-intel/reports", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateFacts(projectId: string): Promise<{ generated: number; status: string }> {
  return request<{ generated: number; status: string }>(
    `/city-intel/projects/${projectId}/generate-facts`,
    { method: "POST" },
  );
}
