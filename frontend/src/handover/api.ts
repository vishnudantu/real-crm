import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type { HandoverCase, HandoverChecklist, HandoverStatus, KeyHandover, SnagItem, SnagSeverity } from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };
function request<T>(path: string, init: RequestInit = {}): Promise<T> { return bearerRequest<T>(path, SESSION, init); }

export const handoverKeys = {
  all: ["admin", "handover"] as const,
  cases: () => [...handoverKeys.all, "cases"] as const,
  detail: (id: string) => [...handoverKeys.all, id] as const,
};

export function fetchCases(status?: HandoverStatus): Promise<{ items: HandoverCase[]; total: number }> {
  return request(`/handover/cases${status ? `?status=${status}` : ""}`);
}
export function fetchChecklist(caseId: string): Promise<HandoverChecklist> { return request(`/handover/cases/${caseId}/checklist`); }
export function fetchCase(caseId: string): Promise<HandoverCase> { return request(`/handover/cases/${caseId}`); }
export function fetchSnags(caseId: string): Promise<SnagItem[]> { return request(`/handover/cases/${caseId}/snags`); }
export function fetchKeyRegister(caseId: string): Promise<KeyHandover[]> { return request(`/handover/cases/${caseId}/keys`); }
export function createHandoverCase(payload: { unit_id: string; booking_id?: string; registration_date?: string; registration_reference?: string; possession_date?: string }): Promise<HandoverCase> {
  return request("/handover/cases", { method: "POST", body: JSON.stringify(payload) });
}
export function updateHandoverCase(caseId: string, payload: { registration_date?: string | null; registration_reference?: string | null; possession_date?: string | null }): Promise<HandoverCase> {
  return request(`/handover/cases/${caseId}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function completeHandover(caseId: string, overrideReason?: string): Promise<HandoverCase> {
  return request(`/handover/cases/${caseId}/complete`, { method: "POST", body: JSON.stringify({ override_reason: overrideReason?.trim() || null }) });
}
export function createSnag(caseId: string, payload: { room: string; description: string; severity: SnagSeverity }): Promise<SnagItem> {
  return request(`/handover/cases/${caseId}/snags`, { method: "POST", body: JSON.stringify(payload) });
}
export function transitionSnag(snagId: string, action: "fix" | "verify" | "close"): Promise<SnagItem> {
  return request(`/handover/snags/${snagId}/${action}`, { method: "POST", body: "{}" });
}
export function uploadSnagPhoto(snagId: string, file: File): Promise<SnagItem> {
  return request(`/handover/snags/${snagId}/photo`, { method: "POST", headers: { "Content-Type": file.type }, body: file });
}
export function recordKeys(caseId: string, payload: { keys_count: number; cards_count: number; handed_to_name: string; notes?: string }): Promise<KeyHandover> {
  return request(`/handover/cases/${caseId}/keys`, { method: "POST", body: JSON.stringify(payload) });
}
export function collectKeys(keyId: string, notes?: string): Promise<KeyHandover> {
  return request(`/handover/keys/${keyId}/collect`, { method: "POST", body: JSON.stringify({ notes: notes || null }) });
}
export async function openSnagPhoto(snagId: string): Promise<void> {
  const token = getSession()?.accessToken;
  if (!token) throw new Error("Sign in again to view snag evidence.");
  const response = await fetch(`${(import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000/api/v1").replace(/\/+$/, "")}/handover/snags/${snagId}/photo`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("The snag photo could not be opened.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.click();
  globalThis.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
