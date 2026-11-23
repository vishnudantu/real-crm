import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, AudioLines, LoaderCircle, Mic2 } from "lucide-react";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, shortId } from "../customers/CustomerUi";
import { formatDateTime, saleInputClasses, saleLabelClasses, salePrimaryButton } from "../admin/sales/salesBookingUi";
import { fetchTranscripts, voiceIntelKeys } from "./api";
import { transcriptStatusTone } from "./model";
import type { TranscriptStatus } from "./model";
import { TranscriptDetail } from "./TranscriptDetail";
import { EnqueueTranscriptForm } from "./EnqueueTranscriptForm";

export function VoiceIntelPage() {
  const { user } = useAdminUser();
  const [status, setStatus] = useState<TranscriptStatus | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [enqueueOpen, setEnqueueOpen] = useState(false);
  const query = useQuery({ queryKey: voiceIntelKeys.list(status), queryFn: () => fetchTranscripts(status) });
  const transcripts = query.data?.items ?? [];
  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Insights" title="Call intelligence" description="Review call recordings as searchable transcripts with requirements, objections, commitments, and next actions." action={user.role.name === "ADMIN" && <button type="button" className={salePrimaryButton} onClick={() => setEnqueueOpen(true)}><Mic2 className="size-4" />Transcribe recording</button>} />
    <section className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"><label className={`${saleLabelClasses} max-w-xs`}>Transcript status<select className={saleInputClasses} value={status} onChange={(event) => setStatus(event.target.value as TranscriptStatus | "ALL")}><option value="ALL">All statuses</option><option value="QUEUED">Queued</option><option value="PROCESSING">Processing</option><option value="COMPLETED">Completed</option><option value="FAILED">Failed</option></select></label></section>
    <CustomerErrorBanner error={query.error} fallback="Call transcripts could not be loaded." onRetry={() => void query.refetch()} />
    {query.isLoading && <div role="status" className="flex items-center justify-center gap-2 rounded-2xl bg-white p-12 text-sm text-charcoal/60"><LoaderCircle className="size-5 animate-spin" />Loading call intelligence…</div>}
    {!query.isLoading && !query.isError && !transcripts.length && <CustomerEmptyState title="No call transcripts" description="Queue an existing Omnichannel call recording to generate transcript text and structured call insights." />}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{transcripts.map((transcript) => <button type="button" key={transcript.id} onClick={() => setSelectedId(transcript.id)} className="group rounded-2xl border border-charcoal/10 bg-white p-5 text-left shadow-xs transition-all hover:-translate-y-0.5 hover:border-forest/30 hover:shadow-md"><div className="flex items-start justify-between gap-3"><span className="grid size-10 place-items-center rounded-xl bg-forest/10 text-forest"><AudioLines className="size-5" /></span><span className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${transcriptStatusTone(transcript.status)}`}>{transcript.status}</span></div><h2 className="mt-4 font-mono text-sm font-semibold">Recording {shortId(transcript.call_recording_id)}</h2><p className="mt-1 text-xs text-charcoal/50">{transcript.language} · {transcript.provider}</p><p className="mt-3 line-clamp-3 min-h-10 text-xs leading-5 text-charcoal/60">{transcript.transcript_text ?? transcript.error ?? "Transcription has not completed yet."}</p><footer className="mt-4 flex items-center justify-between border-t border-charcoal/10 pt-3 text-[11px] text-charcoal/50"><span>{formatDateTime(transcript.created_at)}</span><span className="flex items-center gap-1 font-semibold text-forest">View insights<ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" /></span></footer></button>)}</div>
    {query.data && <p className="text-xs text-charcoal/50">{query.data.total} transcript{query.data.total === 1 ? "" : "s"}</p>}
    {selectedId && <TranscriptDetail transcriptId={selectedId} onClose={() => setSelectedId(null)} />}
    {enqueueOpen && <EnqueueTranscriptForm onClose={() => setEnqueueOpen(false)} onComplete={async () => { setEnqueueOpen(false); setStatus("ALL"); }} />}
  </div>;
}
