import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileAudio, LoaderCircle, Play, Sparkles, X } from "lucide-react";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { useModalFocus } from "../shared/useModalFocus";
import { ApiError } from "../auth/api";
import { CustomerErrorBanner } from "../customers/CustomerUi";
import { formatDateTime, salePrimaryButton } from "../admin/sales/salesBookingUi";
import { fetchSummary, fetchTranscript, processTranscription, voiceIntelKeys } from "./api";
import { formatMilliseconds, structuredText, transcriptSegments, transcriptStatusTone } from "./model";
import type { CallSummary } from "./model";

export function TranscriptDetail({ transcriptId, onClose }: { transcriptId: string; onClose: () => void }) {
  const { user } = useAdminUser();
  const isAdmin = user.role.name === "ADMIN";
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<unknown>(null);
  const transcript = useQuery({ queryKey: voiceIntelKeys.detail(transcriptId), queryFn: () => fetchTranscript(transcriptId) });
  const summary = useQuery({
    queryKey: voiceIntelKeys.summary(transcriptId),
    queryFn: () => fetchSummary(transcriptId),
    enabled: transcript.data?.status === "COMPLETED",
    retry: (count, error: unknown) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
  const process = useMutation({
    mutationFn: processTranscription,
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: voiceIntelKeys.all });
    },
    onError: setActionError,
  });
  const data = transcript.data;
  const segments = transcriptSegments(data?.segments);

  return <div className="fixed inset-0 z-[70] flex justify-end bg-charcoal/45 backdrop-blur-xs" onClick={onClose}>
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="transcript-title" className="h-full w-full max-w-3xl overflow-y-auto bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-charcoal/10 bg-[#FAFAF7]/95 px-5 py-4 backdrop-blur-md"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-charcoal/50">Call intelligence</p><h2 id="transcript-title" className="mt-1 text-lg font-semibold">Transcript & insights</h2></div><button type="button" aria-label="Close transcript" onClick={onClose} className="rounded-lg p-2 hover:bg-charcoal/5"><X className="size-5" /></button></header>
      <div className="space-y-6 p-5 sm:p-6">
        {transcript.isLoading && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle className="size-4 animate-spin" />Loading transcript…</p>}
        <CustomerErrorBanner error={transcript.error} fallback="The transcript could not be loaded." onRetry={() => void transcript.refetch()} />
        {data && <>
          <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${transcriptStatusTone(data.status)}`}>{data.status}</span><span className="text-xs text-charcoal/55">{data.language} · {data.provider}</span></div><p className="mt-3 font-mono text-xs text-charcoal/60">Recording {data.call_recording_id}</p>{data.call_id && <p className="mt-1 font-mono text-xs text-charcoal/60">Call {data.call_id}</p>}<p className="mt-2 text-xs text-charcoal/50">Created {formatDateTime(data.created_at)}</p></div>{isAdmin && data.status !== "COMPLETED" && data.status !== "PROCESSING" && <button type="button" className={salePrimaryButton} disabled={process.isPending} onClick={() => process.mutate(data.id)}>{process.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4" />}Process now</button>}</div>{data.error && <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{data.error}</p>}</section>
          <CustomerErrorBanner error={actionError} fallback="Processing could not be started." />
          <section><h3 className="flex items-center gap-2 text-sm font-semibold"><FileAudio className="size-4 text-forest" />Transcript</h3>{data.transcript_text ? <div className="mt-3 rounded-2xl border border-charcoal/10 bg-white p-5 text-sm leading-7 whitespace-pre-wrap text-charcoal/80 shadow-xs">{data.transcript_text}</div> : <p className="mt-3 rounded-xl border border-dashed border-charcoal/20 p-5 text-sm text-charcoal/55">No transcript text is available yet.</p>}{segments.length > 0 && <div className="mt-3 space-y-2">{segments.map((segment, index) => <div key={index} className="rounded-xl bg-white px-4 py-3 text-xs shadow-xs"><div className="flex justify-between gap-2 font-semibold text-forest"><span>{segment.speaker || "Speaker"}</span><span className="font-mono text-[10px] text-charcoal/45">{formatMilliseconds(segment.startMs)}–{formatMilliseconds(segment.endMs)}</span></div><p className="mt-1.5 leading-5 text-charcoal/70">{segment.text}</p></div>)}</div>}</section>
          <section><h3 className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="size-4 text-forest" />Summary & follow-up</h3>{summary.isLoading && <p className="mt-3 flex items-center gap-2 text-xs"><LoaderCircle className="size-4 animate-spin" />Loading insights…</p>}{summary.error instanceof ApiError && summary.error.status === 404 && <p className="mt-3 text-xs text-charcoal/55">No summary has been generated.</p>}{summary.isError && !(summary.error instanceof ApiError && summary.error.status === 404) && <div className="mt-3"><CustomerErrorBanner error={summary.error} fallback="Summary unavailable." onRetry={() => void summary.refetch()} /></div>}{summary.data && <SummaryContent summary={summary.data} />}</section>
        </>}
      </div>
    </div>
  </div>;
}

function SummaryContent({ summary }: { summary: CallSummary }) {
  return <div className="mt-3 space-y-4"><p className="rounded-2xl bg-forest/5 p-5 text-sm leading-7 text-charcoal/80">{summary.summary}</p><InsightList title="Objections" items={summary.objections} /><InsightList title="Next actions" items={summary.next_actions} /><div className="rounded-xl border border-charcoal/10 bg-white p-4"><h4 className="text-xs font-semibold">Requirements</h4><pre className="mt-2 overflow-x-auto text-xs whitespace-pre-wrap text-charcoal/65">{structuredText(summary.requirements)}</pre></div>{summary.commitments.length > 0 && <div className="rounded-xl border border-charcoal/10 bg-white p-4"><h4 className="text-xs font-semibold">Commitments</h4><ul className="mt-2 space-y-2">{summary.commitments.map((commitment, index) => <li key={index} className="text-xs leading-5 text-charcoal/70">{structuredText(commitment.text ?? commitment)}{commitment.needs_review ? " · Needs review" : ""}</li>)}</ul></div>}</div>;
}

function InsightList({ title, items }: { title: string; items: unknown[] }) {
  if (!items.length) return null;
  return <div className="rounded-xl border border-charcoal/10 bg-white p-4"><h4 className="text-xs font-semibold">{title}</h4><ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-5 text-charcoal/70">{items.map((item, index) => <li key={index}>{structuredText(item)}</li>)}</ul></div>;
}
