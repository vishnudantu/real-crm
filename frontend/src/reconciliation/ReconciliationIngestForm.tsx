import { useState } from "react";
import { FileUp, LoaderCircle, X } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { ingestTransactions } from "./api";
import { parseBankRows } from "./model";
import type { IngestResponse } from "./model";

export function ReconciliationIngestForm({ onClose, onComplete }: {
  onClose: () => void;
  onComplete: (result: IngestResponse) => Promise<void>;
}) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [account, setAccount] = useState("");
  const [rows, setRows] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ingestTransactions,
    onSuccess: onComplete,
    onError: (reason: unknown) => setError(errorMessage(reason, "Statement rows could not be imported.")),
  });

  const submit = () => {
    try {
      setError(null);
      if (!account.trim()) throw new Error("Account label is required.");
      mutation.mutate({ account_label: account.trim(), rows: parseBankRows(rows) });
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Check the statement rows and try again."));
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={onClose}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="ingest-title" className="max-h-[90svh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between border-b border-charcoal/10 p-5">
          <div><h2 id="ingest-title" className="text-lg font-semibold">Import statement rows</h2><p className="mt-1 text-xs text-charcoal/55">Add up to 2,000 bank transactions without posting to the ledger.</p></div>
          <button type="button" onClick={onClose} aria-label="Close import" className="rounded-lg p-1.5 hover:bg-charcoal/5"><X className="size-4" /></button>
        </header>
        <form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); submit(); }}>
          {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
          <label className={saleLabelClasses}>Account label<input required maxLength={64} value={account} onChange={(event) => setAccount(event.target.value)} className={saleInputClasses} placeholder="HDFC Escrow" /></label>
          <label className={saleLabelClasses}>Statement rows<textarea required rows={9} value={rows} onChange={(event) => setRows(event.target.value)} className={`${saleInputClasses} font-mono text-[11px]`} placeholder="UTR12345, 125000.00, 2026-11-22, Asha Rao, Booking A-1204" /></label>
          <p className="text-xs leading-5 text-charcoal/55">One CSV row per line: <strong>UTR, amount in rupees, YYYY-MM-DD, payer name (optional), payer detail (optional)</strong>. Do not include a header row.</p>
          <footer className="flex justify-end gap-2 border-t border-charcoal/10 pt-4"><button type="button" onClick={onClose} className={saleSecondaryButton}>Cancel</button><button type="submit" disabled={mutation.isPending} className={salePrimaryButton}>{mutation.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <FileUp className="size-4" />}Import rows</button></footer>
        </form>
      </div>
    </div>
  );
}
