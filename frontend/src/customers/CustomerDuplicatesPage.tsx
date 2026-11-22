import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, GitMerge, LoaderCircle, RotateCcw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { customerKeys, fetchCustomer, fetchDuplicates, mergeCustomer, revertCustomerMerge } from "./customersApi";
import { mergeSummaryCounts } from "./customersModel";
import type { MergeResponse } from "./customersModel";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, CustomerSkeleton, customerInputClass, formatCustomerDate } from "./CustomerUi";

function MergeEvidence({ merge, onRevert, isReverting }: {
  merge: MergeResponse;
  onRevert: () => void;
  isReverting: boolean;
}) {
  const counts = mergeSummaryCounts(merge.evidence);
  return (
    <section aria-live="polite" className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5 sm:p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div><h2 className="flex items-center gap-2 text-sm font-semibold text-emerald-950"><CheckCircle2 aria-hidden="true" className="size-4" />{merge.reverted_at ? "Merge reverted" : "Merge completed"}</h2><p className="mt-1 text-xs text-charcoal/60">{formatCustomerDate(merge.created_at, true)}{merge.reason && <> · {merge.reason}</>}</p></div>
        {merge.reverted_at === null && <button type="button" onClick={onRevert} disabled={isReverting} className="inline-flex items-center gap-2 self-start rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-xs font-semibold text-charcoal hover:bg-charcoal/5 disabled:opacity-50">{isReverting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <RotateCcw aria-hidden="true" className="size-4" />}Revert merge</button>}
      </div>
      <dl className="mt-5 grid grid-cols-3 gap-3">
        <div className="rounded-xl bg-white p-3"><dt className="text-[0.65rem] leading-4 text-charcoal/50">Methods moved</dt><dd className="mt-1 text-xl font-semibold">{counts.methodsMoved}</dd></div>
        <div className="rounded-xl bg-white p-3"><dt className="text-[0.65rem] leading-4 text-charcoal/50">Opportunities repointed</dt><dd className="mt-1 text-xl font-semibold">{counts.opportunitiesRepointed}</dd></div>
        <div className="rounded-xl bg-white p-3"><dt className="text-[0.65rem] leading-4 text-charcoal/50">Conflicting methods retained</dt><dd className="mt-1 text-xl font-semibold">{counts.methodsSkipped}</dd></div>
      </dl>
      {merge.reverted_at && <p className="mt-4 text-xs text-charcoal/60">Reverted {formatCustomerDate(merge.reverted_at, true)}. Methods, opportunities and contact status were restored from the saved evidence.</p>}
    </section>
  );
}

export function CustomerDuplicatesPage() {
  const { id = "" } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [latestMerge, setLatestMerge] = useState<MergeResponse | null>(null);
  const contactQuery = useQuery({ queryKey: customerKeys.detail(id), queryFn: () => fetchCustomer(id), enabled: Boolean(id) });
  const duplicatesQuery = useQuery({ queryKey: customerKeys.duplicates(id), queryFn: () => fetchDuplicates(id), enabled: Boolean(id) });
  const mergeMutation = useMutation({
    mutationFn: ({ candidateId, mergeReason }: { candidateId: string; mergeReason: string }) => mergeCustomer(id, candidateId, mergeReason),
    onSuccess: (merge) => {
      setLatestMerge(merge);
      setSelectedCandidate(null);
      setReason("");
      setReasonError(null);
      void queryClient.invalidateQueries({ queryKey: customerKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: customerKeys.duplicates(id) });
      void queryClient.invalidateQueries({ queryKey: ["admin", "customers", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "opportunities"] });
    },
  });
  const revertMutation = useMutation({
    mutationFn: (mergeId: string) => revertCustomerMerge(mergeId),
    onSuccess: (merge) => {
      setLatestMerge(merge);
      void queryClient.invalidateQueries({ queryKey: customerKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: customerKeys.duplicates(id) });
      void queryClient.invalidateQueries({ queryKey: ["admin", "customers", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "opportunities"] });
    },
  });

  const submitMerge = (event: FormEvent<HTMLFormElement>, candidateId: string) => {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (!normalizedReason) {
      setReasonError("A reason is required to merge duplicate contacts.");
      return;
    }
    setReasonError(null);
    mergeMutation.mutate({ candidateId, mergeReason: normalizedReason });
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <Link to={`/admin/customers/${id}`} className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal/65 hover:text-charcoal"><ArrowLeft aria-hidden="true" className="size-4" />Back to customer 360</Link>
      <CustomerPageHeader eyebrow="Identity resolution" title="Duplicate review" description={`Compare deterministic evidence before merging another identity into ${contactQuery.data?.contact.display_name ?? "this contact"}.`} />
      <CustomerErrorBanner error={contactQuery.error} fallback="The current customer could not be loaded." onRetry={() => void contactQuery.refetch()} />
      {contactQuery.isLoading && <CustomerSkeleton rows={1} />}
      {latestMerge && <MergeEvidence merge={latestMerge} onRevert={() => revertMutation.mutate(latestMerge.id)} isReverting={revertMutation.isPending} />}
      <CustomerErrorBanner error={mergeMutation.error} fallback="The contacts could not be merged. Refresh the candidates and try again." />
      <CustomerErrorBanner error={revertMutation.error} fallback="The merge could not be reverted." />
      {duplicatesQuery.isLoading ? <CustomerSkeleton rows={3} /> : duplicatesQuery.isError ? <CustomerErrorBanner error={duplicatesQuery.error} fallback="Duplicate suggestions could not be loaded." onRetry={() => void duplicatesQuery.refetch()} /> : duplicatesQuery.data?.candidates.length === 0 ? <CustomerEmptyState title="No duplicate candidates" description="No other active contact shares an exact normalized email or a high-confidence phone match." action={<Link to={`/admin/customers/${id}`} className="text-xs font-semibold underline">Return to customer 360</Link>} /> : duplicatesQuery.data ? (
        <div className="space-y-4">
          <p className="text-xs text-charcoal/55">{duplicatesQuery.data.candidates.length} {duplicatesQuery.data.candidates.length === 1 ? "candidate" : "candidates"} · exact email matches appear first.</p>
          {duplicatesQuery.data.candidates.map((candidate) => (
            <article key={candidate.contact_id} className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">{candidate.display_name}</h2><span className={`rounded-full px-2.5 py-1 text-[0.65rem] font-bold ${candidate.confidence === "EXACT" ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"}`}>{candidate.confidence}</span></div><p className="mt-1 font-mono text-[0.68rem] text-charcoal/45">{candidate.contact_id}</p></div>
                <button type="button" disabled={mergeMutation.isPending} onClick={() => { setSelectedCandidate(selectedCandidate === candidate.contact_id ? null : candidate.contact_id); setReason(""); setReasonError(null); }} aria-expanded={selectedCandidate === candidate.contact_id} className="inline-flex items-center justify-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory disabled:opacity-50"><GitMerge aria-hidden="true" className="size-4" />Merge into current contact</button>
              </div>
              <p className="mt-4 text-xs leading-5 text-charcoal/65">{candidate.evidence}</p>
              <div className="mt-4 overflow-x-auto rounded-xl border border-charcoal/10"><table className="w-full min-w-[500px] text-left text-xs"><caption className="px-4 py-3 text-left font-semibold">Matched field evidence</caption><thead className="bg-charcoal/5 text-charcoal/50"><tr><th className="px-4 py-2 font-medium">Kind</th><th className="px-4 py-2 font-medium">Stored value</th><th className="px-4 py-2 font-medium">Normalized value</th></tr></thead><tbody className="divide-y divide-charcoal/10">{candidate.matched_fields.map((field, index) => <tr key={`${field.kind}-${field.normalized_value}-${index}`}><td className="px-4 py-3">{field.kind}</td><td className="px-4 py-3 break-all">{field.value}</td><td className="px-4 py-3 break-all">{field.normalized_value}</td></tr>)}</tbody></table></div>
              {selectedCandidate === candidate.contact_id && (
                <form onSubmit={(event) => submitMerge(event, candidate.contact_id)} className="mt-5 rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <p className="text-xs leading-5 text-charcoal/65"><strong>{candidate.display_name}</strong> will become MERGED. Its methods move here where possible and its opportunities are repointed. Conflicting methods remain on the merged record for an exact revert.</p>
                  <label className="mt-4 block text-xs font-semibold text-charcoal/70">Merge reason <span className="text-rose-700">(required)</span><textarea required maxLength={500} rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why are these records the same customer?" className={`${customerInputClass} mt-1.5 resize-none bg-white`} /></label>
                  {reasonError && <p role="alert" className="mt-2 text-xs text-rose-700">{reasonError}</p>}
                  <button type="submit" disabled={mergeMutation.isPending} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory disabled:opacity-50">{mergeMutation.isPending ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <GitMerge aria-hidden="true" className="size-4" />}Confirm merge</button>
                </form>
              )}
            </article>
          ))}
        </div>
      ) : null}
      <p className="text-xs leading-5 text-charcoal/45">Merge evidence is shown for the latest merge performed in this view. A backend merge-history endpoint is needed to recover earlier merge receipts after leaving the page.</p>
    </div>
  );
}
