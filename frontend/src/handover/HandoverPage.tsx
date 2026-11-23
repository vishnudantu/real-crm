import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, ClipboardCheck, KeyRound, LoaderCircle, Plus, ShieldAlert, Upload } from "lucide-react";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader } from "../customers/CustomerUi";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { formatShortDate, saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { completeHandover, fetchCases, fetchCase, fetchChecklist, fetchKeyRegister, fetchSnags, handoverKeys, transitionSnag, uploadSnagPhoto, collectKeys, openSnagPhoto } from "./api";
import { canManageHandover, handoverStatusLabel, moneyDisplay, nextSnagAction, readinessDisplay, snagStatusLabel } from "./model";
import type { HandoverCase, HandoverStatus, KeyHandover, SnagItem } from "./model";
import { AddSnagDialog, ChecklistFieldsDialog, CreateHandoverDialog, RecordKeysDialog } from "./HandoverDialogs";

export function HandoverPage() {
  const { user } = useAdminUser();
  const canManage = canManageHandover(user.role.name);
  const [selectedId, setSelectedId] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const cases = useQuery({ queryKey: handoverKeys.cases(), queryFn: () => fetchCases(), enabled: canManage });
  const items = cases.data?.items ?? [];
  useEffect(() => { if (!selectedId && items[0]) setSelectedId(items[0].id); }, [items, selectedId]);
  if (!canManage) return <CustomerEmptyState title="Manager access required" description="Handover operations are available to administrators and managers. Your API permissions also enforce this boundary." />;
  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Possession OS" title="Handover & possession" description="Resolve live readiness blockers, independently verify repairs, and record every key issued to the new owner." action={<button type="button" className={salePrimaryButton} onClick={() => setCreateOpen(true)}><Plus className="size-4" />New case</button>} />
    <CustomerErrorBanner error={cases.error} fallback="Handover cases could not be loaded." onRetry={() => void cases.refetch()} />
    <div className="grid items-start gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <CaseList items={items} loading={cases.isLoading} selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId ? <HandoverDetail key={selectedId} caseId={selectedId} actorId={user.id} /> : !cases.isLoading && <CustomerEmptyState title="No handover cases" description="Create a unit-linked case to start the possession checklist." action={<button type="button" className={salePrimaryButton} onClick={() => setCreateOpen(true)}>Start handover</button>} />}
    </div>
    {createOpen && <CreateHandoverDialog onClose={() => setCreateOpen(false)} onCreated={setSelectedId} />}
  </div>;
}

function CaseList({ items, loading, selectedId, onSelect }: { items: HandoverCase[]; loading: boolean; selectedId: string; onSelect: (id: string) => void }) {
  return <section aria-label="Handover cases" className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs"><header className="border-b border-charcoal/10 px-4 py-4"><h2 className="text-sm font-semibold">Cases <span className="ml-1 text-charcoal/45">{items.length}</span></h2></header>{loading ? <div role="status" className="flex justify-center p-8"><LoaderCircle className="size-5 animate-spin" /></div> : <div className="divide-y divide-charcoal/8">{items.map((item) => <button key={item.id} type="button" aria-pressed={selectedId === item.id} onClick={() => onSelect(item.id)} className={`block w-full px-4 py-4 text-left transition ${selectedId === item.id ? "bg-forest/8" : "hover:bg-charcoal/[.025]"}`}><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-semibold">{item.unit_number ?? item.unit_id.slice(0, 8)}</span><StatusBadge status={item.status} /></div><p className="mt-2 text-xs text-charcoal/50">Case {item.id.slice(0, 8)}{item.booking_reference ? ` · ${item.booking_reference}` : ""} · {formatShortDate(item.created_at.slice(0, 10))}</p></button>)}</div>}</section>;
}

function StatusBadge({ status }: { status: HandoverStatus }) {
  return <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${status === "HANDED_OVER" || status === "READY" ? "bg-forest/10 text-forest" : status === "SNAG_OPEN" ? "bg-amber-100 text-amber-800" : "bg-charcoal/8 text-charcoal/60"}`}>{handoverStatusLabel(status)}</span>;
}

function HandoverDetail({ caseId, actorId }: { caseId: string; actorId: string }) {
  const queryClient = useQueryClient();
  const [snagOpen, setSnagOpen] = useState(false);
  const [keysOpen, setKeysOpen] = useState(false);
  const [fieldsOpen, setFieldsOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const detail = useQuery({ queryKey: handoverKeys.detail(caseId), queryFn: async () => { const [handoverCase, checklist, snags, keys] = await Promise.all([fetchCase(caseId), fetchChecklist(caseId), fetchSnags(caseId), fetchKeyRegister(caseId)]); return { handoverCase, checklist, snags, keys }; } });
  const completion = useMutation({ mutationFn: () => completeHandover(caseId, overrideReason), onSuccess: async () => { setOverrideReason(""); setActionError(null); await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); }, onError: (reason: unknown) => setActionError(errorMessage(reason, "Handover could not be completed.")) });
  const checklist = detail.data?.checklist;
  const handedOver = detail.data?.handoverCase.status === "HANDED_OVER";
  const readiness = readinessDisplay(checklist);
  return <div className="space-y-5">
    <CustomerErrorBanner error={detail.error} fallback="Case details could not be loaded." onRetry={() => void detail.refetch()} />
    {detail.isLoading && <div role="status" className="flex justify-center rounded-2xl bg-white p-16"><LoaderCircle className="size-5 animate-spin" /></div>}
    {checklist && <>
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><p className="text-xs font-semibold uppercase tracking-wider text-charcoal/45">Case {caseId.slice(0, 8)}</p><h2 className="mt-2 text-2xl font-semibold">Possession readiness</h2><p className="mt-2 text-sm text-charcoal/55">{readiness.summary}</p></div><div className={`grid size-20 shrink-0 place-items-center rounded-full border-8 ${readiness.tone === "ready" ? "border-forest/15 bg-forest/10 text-forest" : "border-amber-100 bg-amber-50 text-amber-700"}`}><span className="text-xl font-bold">{readiness.score}%</span></div></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><Metric label="Outstanding" value={moneyDisplay(checklist.financials.outstanding_paise)} /><Metric label="Open snags" value={String(checklist.unresolved_snag_count)} /><Metric label="Checked" value={formatShortDate(checklist.checked_at.slice(0, 10))} /></div>{!handedOver && <button type="button" className={`${saleSecondaryButton} mt-4`} onClick={() => setFieldsOpen(true)}>Registration & possession</button>}</section>
      <section aria-label="Possession checklist" className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><h3 className="text-sm font-semibold">Checklist</h3><ul className="mt-4 space-y-3">{checklist.conditions.map((condition) => <li key={condition.code} className="flex gap-3"><span className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${condition.met ? "bg-forest/10 text-forest" : "bg-amber-100 text-amber-700"}`}>{condition.met ? <Check className="size-3" /> : <ShieldAlert className="size-3" />}</span><div><p className="text-sm font-medium">{condition.label}</p><p className="mt-1 text-xs leading-5 text-charcoal/55">{condition.detail}</p></div></li>)}</ul>{!handedOver && checklist.blockers.length > 0 && <div className="mt-5 border-t border-charcoal/10 pt-4"><label className={saleLabelClasses}>Override reason<textarea rows={2} minLength={10} maxLength={5000} className={saleInputClasses} value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} placeholder="Required to complete below 100% readiness (minimum 10 characters)" /></label></div>}{actionError && <p role="alert" className="mt-3 rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{actionError}</p>}{!handedOver && <button type="button" className={`${salePrimaryButton} mt-4`} disabled={completion.isPending || (readiness.score < 100 && overrideReason.trim().length < 10)} onClick={() => completion.mutate()}>{completion.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}{readiness.score === 100 ? "Complete handover" : "Complete with override"}</button>}{handedOver && <p className="mt-5 rounded-xl bg-forest/10 p-3 text-sm text-forest"><CheckCircle2 className="mr-2 inline size-4" />Possession completed. Case fields and snags are locked; the audit trail retains the readiness snapshot and any override.</p>}</section>
      <SnagPanel actorId={actorId} snags={detail.data?.snags ?? []} onAdd={() => setSnagOpen(true)} readOnly={handedOver} />
      <KeyPanel keys={detail.data?.keys ?? []} onAdd={() => setKeysOpen(true)} readOnly={handedOver} />
    </>}
    {snagOpen && <AddSnagDialog caseId={caseId} onClose={() => setSnagOpen(false)} />}
    {keysOpen && <RecordKeysDialog caseId={caseId} onClose={() => setKeysOpen(false)} />}
    {fieldsOpen && detail.data && <ChecklistFieldsDialog handoverCase={detail.data.handoverCase} onClose={() => setFieldsOpen(false)} />}
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-charcoal/[.035] p-3"><p className="text-xs text-charcoal/50">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>; }

function SnagPanel({ actorId, snags, onAdd, readOnly }: { actorId: string; snags: SnagItem[]; onAdd: () => void; readOnly: boolean }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: ({ id, action }: { id: string; action: "fix" | "verify" | "close" }) => transitionSnag(id, action), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); }, onError: (reason: unknown) => setError(errorMessage(reason, "Snag status could not be changed.")) });
  const photo = useMutation({ mutationFn: ({ id, file }: { id: string; file: File }) => uploadSnagPhoto(id, file), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); }, onError: (reason: unknown) => setError(errorMessage(reason, "Photo could not be uploaded.")) });
  return <section aria-label="Snag register" className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Snag register <span className="ml-1 text-charcoal/45">{snags.length}</span></h3>{!readOnly && <button type="button" className={saleSecondaryButton} onClick={onAdd}><Plus className="size-4" />Add snag</button>}</div>{error && <p role="alert" className="mt-3 text-xs text-rose-700">{error}</p>}{snags.length === 0 ? <p className="mt-4 text-sm text-charcoal/55">No snags recorded. A clean snag gate contributes to readiness.</p> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-charcoal/45"><tr><th className="pb-3">Area / issue</th><th className="pb-3">Severity</th><th className="pb-3">Status</th><th className="pb-3">Evidence</th><th className="pb-3 text-right">Next action</th></tr></thead><tbody className="divide-y divide-charcoal/8">{snags.map((snag) => { const next = nextSnagAction(snag.status, actorId, snag.fixed_by_id); return <tr key={snag.id}><td className="py-3 pr-4"><p className="font-semibold">{snag.room}</p><p className="mt-1 max-w-xs text-charcoal/55">{snag.description}</p></td><td className="py-3 pr-4">{snag.severity}</td><td className="py-3 pr-4">{snagStatusLabel(snag.status)}{snag.status === "FIXED" && snag.fixed_by_id === actorId && <p className="mt-1 text-amber-700">Another staff member must verify.</p>}</td><td className="py-3 pr-4">{snag.photo_evidence_path ? <button type="button" className="inline-flex items-center gap-1 text-forest underline" onClick={() => { void openSnagPhoto(snag.id).catch((reason: unknown) => setError(errorMessage(reason, "Photo could not be opened."))); }}>View photo</button> : <label className="inline-flex cursor-pointer items-center gap-1 text-forest"><Upload className="size-3.5" />{photo.isPending ? "Uploading…" : "Upload photo"}<input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" disabled={photo.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) photo.mutate({ id: snag.id, file }); event.target.value = ""; }} /></label>}</td><td className="py-3 text-right">{!readOnly && next && <button type="button" className={saleSecondaryButton} disabled={mutation.isPending} onClick={() => mutation.mutate({ id: snag.id, action: next.action })}>{next.label}</button>}</td></tr>; })}</tbody></table></div>}</section>;
}

function KeyPanel({ keys, onAdd, readOnly }: { keys: KeyHandover[]; onAdd: () => void; readOnly: boolean }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({ mutationFn: (id: string) => collectKeys(id), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: handoverKeys.all }); } });
  return <section aria-label="Key register" className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-sm font-semibold"><KeyRound className="size-4 text-forest" />Key register</h3>{!readOnly && <button type="button" className={saleSecondaryButton} onClick={onAdd}><Plus className="size-4" />Record keys</button>}</div>{keys.length === 0 ? <p className="mt-4 text-sm text-charcoal/55">No keys or access cards recorded for this unit.</p> : <ul className="mt-4 divide-y divide-charcoal/8">{keys.map((key) => <li key={key.id} className="flex flex-col justify-between gap-3 py-3 sm:flex-row sm:items-center"><div><p className="text-sm font-medium">{key.keys_count} keys · {key.cards_count} cards <span className="font-normal text-charcoal/50">to {key.handed_to_name}</span></p><p className="mt-1 text-xs text-charcoal/50">Issued {formatShortDate(key.handed_at.slice(0, 10))}{key.notes ? ` · ${key.notes}` : ""}</p></div>{key.collected_id ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-forest"><ClipboardCheck className="size-4" />Collected {key.collected_at ? formatShortDate(key.collected_at.slice(0, 10)) : ""}</span> : <button type="button" className={saleSecondaryButton} disabled={mutation.isPending} onClick={() => mutation.mutate(key.id)}>Mark collected</button>}</li>)}</ul>}</section>;
}
