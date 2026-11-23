import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, FileUp, Landmark, LoaderCircle, SearchCheck } from "lucide-react";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader } from "../customers/CustomerUi";
import {
  formatInr,
  formatShortDate,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
  shortReference,
} from "./reconciliationUi";
import { fetchTransactions, ignoreTransaction, reconciliationKeys, suggestMatches } from "./api";
import { transactionStatusTone } from "./model";
import type { TransactionStatus } from "./model";
import { ReconciliationIngestForm } from "./ReconciliationIngestForm";

export function ReconciliationPage() {
  const { user } = useAdminUser();
  const isAdmin = user.role.name === "ADMIN";
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<TransactionStatus | "ALL">("UNMATCHED");
  const [account, setAccount] = useState("");
  const [appliedAccount, setAppliedAccount] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const query = useQuery({
    queryKey: reconciliationKeys.list(status, appliedAccount),
    queryFn: () => fetchTransactions(status, appliedAccount),
  });
  const refresh = async () => { await queryClient.invalidateQueries({ queryKey: reconciliationKeys.all }); };
  const ignore = useMutation({
    mutationFn: ignoreTransaction,
    onSuccess: async () => { setActionError(null); setNotice("Transaction ignored."); await refresh(); },
    onError: setActionError,
  });
  const suggest = useMutation({
    mutationFn: suggestMatches,
    onSuccess: async (result) => {
      setActionError(null);
      setNotice(`${result.matched} matched, ${result.suggested} suggestions, ${result.still_unmatched} still unmatched.`);
      await refresh();
    },
    onError: setActionError,
  });
  const transactions = query.data?.items ?? [];

  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Operations" title="Bank reconciliation" description="Review statement rows, run payment matching, and resolve exceptions before receipts are posted." action={isAdmin && <div className="flex flex-wrap gap-2"><button type="button" className={saleSecondaryButton} onClick={() => setImportOpen(true)}><FileUp className="size-4" />Import rows</button><button type="button" className={salePrimaryButton} disabled={suggest.isPending} onClick={() => { setNotice(null); suggest.mutate(); }}>{suggest.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <SearchCheck className="size-4" />}Suggest matches</button></div>} />
    {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    <CustomerErrorBanner error={actionError} fallback="The reconciliation action could not be completed." />
    <section className="flex flex-col gap-3 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs sm:flex-row sm:items-end">
      <label className={saleLabelClasses}>Status<select className={`${saleInputClasses} sm:w-48`} value={status} onChange={(event) => setStatus(event.target.value as TransactionStatus | "ALL")}><option value="UNMATCHED">Unmatched</option><option value="MATCHED">Matched</option><option value="IGNORED">Ignored</option><option value="ALL">All transactions</option></select></label>
      <form className="flex flex-1 items-end gap-2" onSubmit={(event) => { event.preventDefault(); setAppliedAccount(account); }}><label className={`${saleLabelClasses} flex-1`}>Account label<input className={saleInputClasses} value={account} onChange={(event) => setAccount(event.target.value)} placeholder="All accounts" /></label><button type="submit" className={saleSecondaryButton}>Apply</button></form>
    </section>
    <CustomerErrorBanner error={query.error} fallback="Bank transactions could not be loaded." onRetry={() => void query.refetch()} />
    {query.isLoading && <div role="status" className="flex items-center justify-center gap-2 rounded-2xl bg-white p-12 text-sm text-charcoal/60"><LoaderCircle className="size-5 animate-spin" />Loading transactions…</div>}
    {!query.isLoading && !query.isError && transactions.length === 0 && <CustomerEmptyState title="No transactions in this view" description={isAdmin ? "Import statement rows or change the filters to review bank transactions." : "Change the filters to review bank transactions."} />}
    {transactions.length > 0 && <section className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs"><div className="overflow-x-auto"><table className="w-full min-w-[950px] text-left text-xs"><thead className="bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/50"><tr><th className="px-4 py-3">Date / UTR</th><th className="px-4 py-3">Payer</th><th className="px-4 py-3">Account</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Match</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-charcoal/5">{transactions.map((transaction) => <tr key={transaction.id}><td className="px-4 py-4"><p>{formatShortDate(transaction.txn_date)}</p><p className="mt-1 font-mono text-[11px] text-charcoal/60">{transaction.utr}</p></td><td className="px-4 py-4"><p className="font-medium">{transaction.payer_name ?? "Not supplied"}</p><p className="mt-1 max-w-48 truncate text-charcoal/50" title={transaction.payer_detail ?? undefined}>{transaction.payer_detail ?? "—"}</p></td><td className="px-4 py-4">{transaction.account_label}</td><td className="px-4 py-4 text-right font-semibold whitespace-nowrap">{formatInr(transaction.amount_paise)}</td><td className="px-4 py-4">{transaction.matched_installment_id ? <span title={transaction.matched_installment_id}>{transaction.matched_by ?? "Suggested"} · {shortReference(transaction.matched_installment_id)}</span> : "—"}</td><td className="px-4 py-4"><span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold ${transactionStatusTone(transaction.status)}`}>{transaction.status}</span></td><td className="px-4 py-4 text-right">{isAdmin && transaction.status === "UNMATCHED" && <button type="button" disabled={ignore.isPending} onClick={() => { setNotice(null); ignore.mutate(transaction.id); }} className={saleSecondaryButton}><CircleCheck className="size-3.5" />Ignore</button>}</td></tr>)}</tbody></table></div><p className="flex items-center gap-2 border-t border-charcoal/10 px-4 py-3 text-xs text-charcoal/55"><Landmark className="size-3.5" />{query.data?.total ?? 0} transaction{query.data?.total === 1 ? "" : "s"} · suggestions require human confirmation and do not post ledger entries.</p></section>}
    {importOpen && <ReconciliationIngestForm onClose={() => setImportOpen(false)} onComplete={async (result) => { setImportOpen(false); setNotice(`${result.created} rows imported, ${result.duplicates} duplicates, ${result.errors.length} errors.${result.errors.length ? ` ${result.errors.join(" ")}` : ""}`); await refresh(); }} />}
  </div>;
}
