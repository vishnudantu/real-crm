export type TranscriptStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface CallTranscript {
  id: string;
  call_recording_id: string;
  call_id: string | null;
  language: string;
  status: TranscriptStatus;
  transcript_text: string | null;
  segments: unknown[];
  provider: string;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface TranscriptListResponse {
  items: CallTranscript[];
  total: number;
}

export interface CallSummary {
  id: string;
  transcript_id: string;
  summary: string;
  requirements: Record<string, unknown>;
  objections: unknown[];
  commitments: Record<string, unknown>[];
  next_actions: unknown[];
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  startMs: number;
  endMs: number;
  speaker: string;
  text: string;
}

export function transcriptStatusTone(status: string): string {
  if (status === "COMPLETED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "FAILED") return "border-rose-200 bg-rose-50 text-rose-700";
  if (status === "PROCESSING") return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export function transcriptSegments(value: unknown): TranscriptSegment[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): TranscriptSegment[] => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) return [];
    const record = item as Record<string, unknown>;
    return [{
      startMs: finiteNumber(record.start_ms),
      endMs: finiteNumber(record.end_ms),
      speaker: typeof record.speaker === "string" ? record.speaker : "",
      text: typeof record.text === "string" ? record.text : "",
    }];
  });
}

function finiteNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function formatMilliseconds(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function structuredText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "Unavailable";
  }
}
