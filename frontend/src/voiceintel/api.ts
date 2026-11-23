import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  CallSummary,
  CallTranscript,
  TranscriptListResponse,
  TranscriptStatus,
} from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const voiceIntelKeys = {
  all: ["admin", "voice-intel"] as const,
  list: (status: TranscriptStatus | "ALL") => ["admin", "voice-intel", { status }] as const,
  detail: (id: string) => ["admin", "voice-intel", id] as const,
  summary: (id: string) => ["admin", "voice-intel", id, "summary"] as const,
};

export function fetchTranscripts(status: TranscriptStatus | "ALL"): Promise<TranscriptListResponse> {
  const suffix = status === "ALL" ? "" : `?status=${encodeURIComponent(status)}`;
  return bearerRequest<TranscriptListResponse>(`/voice-intel/transcriptions${suffix}`, SESSION);
}

export function fetchTranscript(id: string): Promise<CallTranscript> {
  return bearerRequest<CallTranscript>(`/voice-intel/transcriptions/${id}`, SESSION);
}

export function fetchSummary(id: string): Promise<CallSummary> {
  return bearerRequest<CallSummary>(`/voice-intel/transcriptions/${id}/summary`, SESSION);
}

export function enqueueTranscription(callRecordingId: string, language: string): Promise<CallTranscript> {
  return bearerRequest<CallTranscript>("/voice-intel/transcriptions", SESSION, {
    method: "POST",
    body: JSON.stringify({ call_recording_id: callRecordingId, language }),
  });
}

export function processTranscription(id: string): Promise<CallTranscript> {
  return bearerRequest<CallTranscript>(`/voice-intel/transcriptions/${id}/process`, SESSION, {
    method: "POST",
  });
}
