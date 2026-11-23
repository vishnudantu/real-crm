import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { fetchProjects } from "../admin/api";
import { fetchUnits } from "../inventory/inventoryApi";
import { fetchSaleBookings } from "../admin/sales/salesBookingApi";
import { saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { createHandoverCase, createSnag, handoverKeys, recordKeys, updateHandoverCase } from "./api";
import type { HandoverCase, SnagSeverity } from "./model";

function DialogShell({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useModalFocus<HTMLDivElement>(onClose);
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={onClose}><div ref={ref} role="dialog" aria-modal="true" aria-label={title} className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}><header className="flex items-center justify-between border-b border-charcoal/10 p-5"><h2 className="font-semibold">{title}</h2><button type="button" aria-label="Close" onClick={onClose} className="rounded-lg p-1.5 hover:bg-charcoal/5"><X className="size-4" /></button></header>{children}</div></div>;
}

function DialogFooter({ pending, label }: { pending: boolean; label: string }) {
  return <footer className="flex justify-end pt-3"><button type="submit" className={salePrimaryButton} disabled={pending}>{pending && <LoaderCircle className="size-4 animate-spin" />}{label}</button></footer>;
}

export function CreateHandoverDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [bookingId, setBookingId] = useState("");
  const [registrationDate, setRegistrationDate] = useState("");
  const [registrationReference, setRegistrationReference] = useState("");
  const [possessionDate, setPossessionDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const projects = useQuery({ queryKey: ["admin", "projects", "handover"], queryFn: () => fetchProjects({ page: 1, pageSize: 100 }) });
  const units = useQuery({ queryKey: ["admin", "handover", "units", projectId], queryFn: () => fetchUnits({ projectId, page: 1, pageSize: 100 }), enabled: Boolean(projectId) });
  const bookings = useQuery({ queryKey: ["admin", "handover", "bookings", projectId], queryFn: () => fetchSaleBookings({ projectId, page: 1, pageSize: 100 }), enabled: Boolean(projectId) });
  const mutation = useMutation({
    mutationFn: createHandoverCase,
    onSuccess: async (created) => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); onCreated(created.id); onClose(); },
    onError: (reason: unknown) => setError(errorMessage(reason, "The handover case could not be created.")),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!unitId) { setError("Select a canonical inventory unit."); return; }
    mutation.mutate({ unit_id: unitId, ...(bookingId ? { booking_id: bookingId } : {}), ...(registrationDate ? { registration_date: registrationDate } : {}), ...(registrationReference.trim() ? { registration_reference: registrationReference.trim() } : {}), ...(possessionDate ? { possession_date: possessionDate } : {}) });
  }
  return <DialogShell title="Start handover case" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}>
    <p className="text-sm leading-6 text-charcoal/60">Link the real unit and sale booking. Readiness is recomputed from its ledger, agreement and possession fields.</p>
    {error && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
    <label className={saleLabelClasses}>Project<select required className={saleInputClasses} value={projectId} onChange={(event) => { setProjectId(event.target.value); setUnitId(""); setBookingId(""); }}><option value="">Select project</option>{projects.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label className={saleLabelClasses}>Unit<select required disabled={!projectId || units.isLoading} className={saleInputClasses} value={unitId} onChange={(event) => setUnitId(event.target.value)}><option value="">{units.isLoading ? "Loading units…" : "Select unit"}</option>{units.data?.items.map((item) => <option key={item.id} value={item.id}>{item.internal_code} · {item.configuration ?? "Unit"}</option>)}</select></label>
    <label className={saleLabelClasses}>Sale booking<select disabled={!projectId || bookings.isLoading} className={saleInputClasses} value={bookingId} onChange={(event) => setBookingId(event.target.value)}><option value="">No linked booking</option>{bookings.data?.items.map((item) => <option key={item.id} value={item.id}>{item.unit_number} · {item.status}</option>)}</select></label>
    <div className="grid gap-4 sm:grid-cols-2"><label className={saleLabelClasses}>Registration date<input type="date" className={saleInputClasses} value={registrationDate} onChange={(event) => setRegistrationDate(event.target.value)} /></label><label className={saleLabelClasses}>Possession date<input type="date" className={saleInputClasses} value={possessionDate} onChange={(event) => setPossessionDate(event.target.value)} /></label></div>
    <label className={saleLabelClasses}>Registration reference<input maxLength={128} className={saleInputClasses} value={registrationReference} onChange={(event) => setRegistrationReference(event.target.value)} /></label>
    <DialogFooter pending={mutation.isPending} label="Create case" />
  </form></DialogShell>;
}

export function ChecklistFieldsDialog({ handoverCase, onClose }: { handoverCase: HandoverCase; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [registrationDate, setRegistrationDate] = useState(handoverCase.registration_date ?? "");
  const [registrationReference, setRegistrationReference] = useState(handoverCase.registration_reference ?? "");
  const [possessionDate, setPossessionDate] = useState(handoverCase.possession_date ?? "");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => updateHandoverCase(handoverCase.id, { registration_date: registrationDate || null, registration_reference: registrationReference.trim() || null, possession_date: possessionDate || null }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Checklist fields could not be saved.")) });
  return <DialogShell title="Registration & possession" onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}<label className={saleLabelClasses}>Registration date<input type="date" className={saleInputClasses} value={registrationDate} onChange={(event) => setRegistrationDate(event.target.value)} /></label><label className={saleLabelClasses}>Registration reference<input className={saleInputClasses} maxLength={128} value={registrationReference} onChange={(event) => setRegistrationReference(event.target.value)} /></label><label className={saleLabelClasses}>Actual possession date<input type="date" className={saleInputClasses} value={possessionDate} onChange={(event) => setPossessionDate(event.target.value)} /><span className="text-xs text-charcoal/50">When blank, the booking's expected possession date is used.</span></label><p className="text-xs leading-5 text-charcoal/55">These changes are audit logged. A recorded registration date is required; the reference is optional.</p><DialogFooter pending={mutation.isPending} label="Save checklist fields" /></form></DialogShell>;
}

export function AddSnagDialog({ caseId, onClose }: { caseId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [room, setRoom] = useState(""); const [description, setDescription] = useState(""); const [severity, setSeverity] = useState<SnagSeverity>("MINOR"); const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => createSnag(caseId, { room: room.trim(), description: description.trim(), severity }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Snag could not be recorded.")) });
  return <DialogShell title="Record snag" onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}<label className={saleLabelClasses}>Room / area<input required maxLength={128} className={saleInputClasses} value={room} onChange={(event) => setRoom(event.target.value)} /></label><label className={saleLabelClasses}>Severity<select className={saleInputClasses} value={severity} onChange={(event) => setSeverity(event.target.value as SnagSeverity)}><option value="MINOR">Minor</option><option value="MAJOR">Major</option><option value="CRITICAL">Critical</option></select></label><label className={saleLabelClasses}>Description<textarea required maxLength={5000} rows={4} className={saleInputClasses} value={description} onChange={(event) => setDescription(event.target.value)} /></label><DialogFooter pending={mutation.isPending} label="Record snag" /></form></DialogShell>;
}

export function RecordKeysDialog({ caseId, onClose }: { caseId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [keys, setKeys] = useState("1"); const [cards, setCards] = useState("0"); const [recipient, setRecipient] = useState(""); const [notes, setNotes] = useState(""); const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => recordKeys(caseId, { keys_count: Number(keys), cards_count: Number(cards), handed_to_name: recipient.trim(), ...(notes.trim() ? { notes: notes.trim() } : {}) }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); onClose(); }, onError: (reason: unknown) => setError(errorMessage(reason, "Key handover could not be recorded.")) });
  return <DialogShell title="Record keys & access cards" onClose={onClose}><form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}<div className="grid grid-cols-2 gap-4"><label className={saleLabelClasses}>Keys<input required type="number" min={0} max={1000} className={saleInputClasses} value={keys} onChange={(event) => setKeys(event.target.value)} /></label><label className={saleLabelClasses}>Access cards<input required type="number" min={0} max={1000} className={saleInputClasses} value={cards} onChange={(event) => setCards(event.target.value)} /></label></div><label className={saleLabelClasses}>Handed to<input required maxLength={255} className={saleInputClasses} value={recipient} onChange={(event) => setRecipient(event.target.value)} /></label><label className={saleLabelClasses}>Notes<textarea rows={3} maxLength={5000} className={saleInputClasses} value={notes} onChange={(event) => setNotes(event.target.value)} /></label><DialogFooter pending={mutation.isPending} label="Record key issue" /></form></DialogShell>;
}

export { saleSecondaryButton };
