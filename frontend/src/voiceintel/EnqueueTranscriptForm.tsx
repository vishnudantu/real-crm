import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Mic2, X } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { enqueueTranscription, voiceIntelKeys } from "./api";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function EnqueueTranscriptForm({ onClose, onComplete }: { onClose: () => void; onComplete: () => Promise<void> }) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [recordingId, setRecordingId] = useState("");
  const [language, setLanguage] = useState("en");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => enqueueTranscription(recordingId.trim(), language.trim()),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: voiceIntelKeys.all }); await onComplete(); },
    onError: (reason: unknown) => setError(errorMessage(reason, "The transcription could not be queued.")),
  });
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={onClose}><div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="enqueue-title" className="w-full max-w-lg rounded-2xl bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}><header className="flex items-center justify-between border-b border-charcoal/10 p-5"><h2 id="enqueue-title" className="font-semibold">Transcribe a call recording</h2><button type="button" aria-label="Close" onClick={onClose} className="rounded-lg p-1.5 hover:bg-charcoal/5"><X className="size-4" /></button></header><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); if (!recordingId.trim() || !language.trim()) { setError("Recording ID and language are required."); return; } if (!UUID_PATTERN.test(recordingId.trim())) { setError("Enter the call recording's UUID."); return; } setError(null); mutation.mutate(); }}>{error && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}<label className={saleLabelClasses}>Call recording ID<input required className={`${saleInputClasses} font-mono`} value={recordingId} onChange={(event) => setRecordingId(event.target.value)} placeholder="UUID from the call recording" /></label><label className={saleLabelClasses}>Language code<input required maxLength={8} className={saleInputClasses} value={language} onChange={(event) => setLanguage(event.target.value)} /></label><p className="text-xs leading-5 text-charcoal/55">The recording must already exist in Omnichannel. Processing runs synchronously when you choose Process now.</p><footer className="flex justify-end gap-2 border-t border-charcoal/10 pt-4"><button type="button" className={saleSecondaryButton} onClick={onClose}>Cancel</button><button type="submit" className={salePrimaryButton} disabled={mutation.isPending}>{mutation.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Mic2 className="size-4" />}Queue transcription</button></footer></form></div></div>;
}
