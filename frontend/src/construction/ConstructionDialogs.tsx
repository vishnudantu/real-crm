import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";
import { errorMessage } from "../shared/apiRequest";
import { saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { addMilestoneProgress, certifyMilestone, constructionKeys, createMilestone } from "./api";
import type { ConstructionMilestone } from "./model";

function DialogShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useModalFocus<HTMLDivElement>(onClose);
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={onClose}><div ref={ref} role="dialog" aria-modal="true" aria-label={title} className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}><header className="flex items-center justify-between border-b border-charcoal/10 p-5"><h2 className="font-semibold">{title}</h2><button type="button" aria-label="Close" onClick={onClose} className="rounded-lg p-1.5 hover:bg-charcoal/5"><X className="size-4" /></button></header>{children}</div></div>;
}

export function CreateMilestoneDialog({ projectId, sequence, onClose }: { projectId: string; sequence: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [sequenceNo, setSequenceNo] = useState(String(sequence));
  const [date, setDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: createMilestone, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: constructionKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Milestone could not be created.")) });
  return <DialogShell title="Add construction milestone" onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); const sequenceNumber = Number(sequenceNo); if (!name.trim() || !Number.isInteger(sequenceNumber) || sequenceNumber < 1 || !date) { setError("Enter a name, a positive sequence, and a planned date."); return; } setError(null); mutation.mutate({ project_id: projectId, name: name.trim(), sequence_no: sequenceNumber, planned_date: date }); }}>{error && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}<label className={saleLabelClasses}>Milestone name<input required maxLength={255} className={saleInputClasses} value={name} onChange={(event) => setName(event.target.value)} /></label><div className="grid grid-cols-2 gap-4"><label className={saleLabelClasses}>Sequence<input required type="number" min={1} step={1} className={saleInputClasses} value={sequenceNo} onChange={(event) => setSequenceNo(event.target.value)} /></label><label className={saleLabelClasses}>Planned date<input required type="date" className={saleInputClasses} value={date} onChange={(event) => setDate(event.target.value)} /></label></div><footer className="flex justify-end gap-2 pt-3"><button type="button" className={saleSecondaryButton} onClick={onClose}>Cancel</button><button type="submit" className={salePrimaryButton} disabled={mutation.isPending}>{mutation.isPending && <LoaderCircle className="size-4 animate-spin" />}Create milestone</button></footer></form></DialogShell>;
}

export function ProgressDialog({ milestone, onClose }: { milestone: ConstructionMilestone; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [percent, setPercent] = useState(String(milestone.percent_complete));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => addMilestoneProgress(milestone.id, Number(percent), note.trim()), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: constructionKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Progress could not be saved.")) });
  return <DialogShell title={`Update ${milestone.name}`} onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); const value = Number(percent); if (!Number.isInteger(value) || value < 0 || value > 100 || !note.trim()) { setError("Enter a whole percentage from 0 to 100 and a progress note."); return; } setError(null); mutation.mutate(); }}>{error && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}<label className={saleLabelClasses}>Percent complete<input required type="number" min={0} max={100} step={1} className={saleInputClasses} value={percent} onChange={(event) => setPercent(event.target.value)} /></label><label className={saleLabelClasses}>Site progress note<textarea required maxLength={5000} rows={5} className={saleInputClasses} value={note} onChange={(event) => setNote(event.target.value)} /></label><p className="text-xs text-charcoal/50">Progress observations are append-only in the construction record.</p><footer className="flex justify-end gap-2"><button type="button" className={saleSecondaryButton} onClick={onClose}>Cancel</button><button type="submit" className={salePrimaryButton} disabled={mutation.isPending}>{mutation.isPending && <LoaderCircle className="size-4 animate-spin" />}Save progress</button></footer></form></DialogShell>;
}

export function CertifyDialog({ milestone, onClose }: { milestone: ConstructionMilestone; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [evidence, setEvidence] = useState(milestone.evidence_notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => certifyMilestone(milestone.id, evidence.trim()), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: constructionKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Milestone could not be certified.")) });
  return <DialogShell title={`Certify ${milestone.name}`} onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>{error && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}<p className="text-sm leading-6 text-charcoal/65">Certify this completed milestone and retain its evidence notes. Certification is restricted to completed milestones by the API.</p><label className={saleLabelClasses}>Evidence notes<textarea rows={6} maxLength={10000} className={saleInputClasses} value={evidence} onChange={(event) => setEvidence(event.target.value)} placeholder="Inspection reference, engineer verification, or supporting evidence…" /></label><footer className="flex justify-end gap-2"><button type="button" className={saleSecondaryButton} onClick={onClose}>Cancel</button><button type="submit" className={salePrimaryButton} disabled={mutation.isPending}>{mutation.isPending && <LoaderCircle className="size-4 animate-spin" />}Certify milestone</button></footer></form></DialogShell>;
}
