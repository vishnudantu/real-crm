import { useEffect, useRef, useState } from "react";
import {
  Disc,
  LoaderCircle,
  Mic,
  MicOff,
  PhoneOff,
  Radio,
  Square,
} from "lucide-react";
import { endCall, listRecordings, startRecording } from "./api";
import { errorMessage } from "../shared/apiRequest";
import type { CallRecord, CallRecording } from "./omnichannelModel";

interface CallingPanelProps {
  call: CallRecord;
  onEnded: (call: CallRecord) => void;
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export function CallingPanel({ call, onEnded }: CallingPanelProps) {
  const [elapsed, setElapsed] = useState(0);
  const [muted, setMuted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordings, setRecordings] = useState<CallRecording[]>([]);
  const [recordingActive, setRecordingActive] = useState(false);
  const timerRef = useRef<number | null>(null);
  const endedRef = useRef(false);

  const isSimulated = call.provider === "simulated";
  const isFinished = call.status === "COMPLETED" || call.status === "FAILED";

  useEffect(() => {
    if (isFinished) return;
    const startedAt = call.started_at ? new Date(call.started_at).getTime() : Date.now();
    timerRef.current = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [call.started_at, isFinished]);

  useEffect(() => {
    void listRecordings(call.id)
      .then(setRecordings)
      .catch(() => undefined);
  }, [call.id, recordingActive]);

  const hangUp = async () => {
    if (endedRef.current) return;
    endedRef.current = true;
    setBusy(true);
    try {
      const ended = await endCall(call.id);
      onEnded(ended);
    } catch (err) {
      setError(errorMessage(err, "The call could not be ended cleanly."));
      endedRef.current = false;
    } finally {
      setBusy(false);
    }
  };

  const toggleRecording = async () => {
    setBusy(true);
    setError(null);
    try {
      if (!recordingActive) {
        // Consent is confirmed by the agent in the UI before this call.
        await startRecording(call.id);
        setRecordingActive(true);
      }
    } catch (err) {
      setError(errorMessage(err, "Recording could not be started."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-b border-charcoal/10 bg-charcoal px-4 py-3 text-ivory">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="relative flex size-10 items-center justify-center rounded-full bg-white/10">
            <Radio aria-hidden="true" className={`size-5 ${isFinished ? "" : "animate-pulse"}`} />
          </span>
          <div>
            <p className="text-sm font-semibold">
              {isFinished ? "Call ended" : "Call in progress"}
              {isSimulated && (
                <span className="ml-2 rounded bg-amber-400/20 px-1.5 py-0.5 text-[0.66rem] font-bold text-amber-200 uppercase">
                  Simulated
                </span>
              )}
            </p>
            <p className="font-mono text-xs text-ivory/60">
              {isFinished ? formatDuration(call.duration_seconds) : formatDuration(elapsed)}
              {call.destination ? ` · ${call.destination}` : ""}
            </p>
          </div>
        </div>

        {!isFinished && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMuted((value) => !value)}
              aria-pressed={muted}
              title={muted ? "Unmute microphone" : "Mute microphone"}
              className={`grid size-9 place-items-center rounded-full transition-colors ${
                muted ? "bg-rose-500/80 text-white" : "bg-white/10 text-ivory hover:bg-white/20"
              }`}
            >
              {muted ? <MicOff className="size-4" /> : <Mic className="size-4" />}
            </button>

            <button
              type="button"
              onClick={() => void toggleRecording()}
              disabled={busy}
              title={
                recordingActive
                  ? "Recording in progress"
                  : "Start recording (confirm the contact has been informed)"
              }
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-semibold transition-colors ${
                recordingActive
                  ? "bg-rose-500/20 text-rose-200"
                  : "bg-white/10 text-ivory hover:bg-white/20"
              }`}
            >
              {recordingActive ? (
                <>
                  <Disc aria-hidden="true" className="size-4 animate-pulse text-rose-400" />
                  REC
                </>
              ) : (
                <>
                  <Square aria-hidden="true" className="size-3" />
                  Record
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => void hangUp()}
              disabled={busy}
              className="grid size-9 place-items-center rounded-full bg-rose-600 text-white transition-colors hover:bg-rose-500 disabled:opacity-50"
              aria-label="End call"
            >
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : <PhoneOff className="size-4" />}
            </button>
          </div>
        )}
      </div>

      {isSimulated && !isFinished && (
        <p className="mt-2 rounded-lg bg-white/5 px-3 py-1.5 text-[0.7rem] text-ivory/60">
          No media server is connected. State transitions and recordings are real API calls;
          configure a LiveKit server in channel settings for live audio.
        </p>
      )}

      {recordingActive && (
        <p className="mt-2 text-[0.7rem] text-rose-200/80">
          Recording active — the contact must be informed the call is being recorded.
        </p>
      )}

      {recordings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {recordings.map((recording) => (
            <li key={recording.id} className="flex items-center gap-2 text-[0.7rem] text-ivory/70">
              <Disc aria-hidden="true" className="size-3" />
              {recording.status.toLowerCase()} · {formatDuration(recording.duration_seconds)}
              {recording.storage_url && (
                <a href={recording.storage_url} className="underline" target="_blank" rel="noreferrer">
                  Download
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && <p className="mt-2 text-xs text-rose-300">{error}</p>}
    </div>
  );
}
