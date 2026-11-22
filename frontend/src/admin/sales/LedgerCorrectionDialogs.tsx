import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { errorMessage } from "../../shared/apiRequest";
import { updateInstallment, voidReceipt } from "./salesBookingApi";
import type { InstallmentItem, ReceiptItem } from "./salesBookingModel";
import {
  formatInr,
  formatShortDate,
  paiseToRupeesInput,
  rupeesInputToPaise,
  saleDangerButton,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "./salesBookingUi";

interface DialogShellProps {
  title: string;
  description: string;
  onClose: () => void;
  children: React.ReactNode;
}

function DialogShell({ title, description, onClose, children }: DialogShellProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90svh] w-full max-w-md overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold tracking-tight text-charcoal">{title}</h3>
            <p className="mt-1 text-[11px] leading-relaxed text-charcoal/55">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={`Close ${title}`}
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

interface EditInstallmentDialogProps {
  installment: InstallmentItem;
  onClose: () => void;
  onSaved: (message: string) => void | Promise<void>;
}

/**
 * Correct an open installment's due date, amount, or open-state status.
 * Amount cannot drop below the live paid total, and status never offers
 * PAID (requires a receipt) or WAIVED (reserved for a waiver workflow).
 * Any financial edit lets the backend recompute status from the balance.
 */
export function EditInstallmentDialog({
  installment,
  onClose,
  onSaved,
}: EditInstallmentDialogProps) {
  const [dueOn, setDueOn] = useState(installment.due_on);
  const [amountRupees, setAmountRupees] = useState(paiseToRupeesInput(installment.amount_paise));
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: { due_on: string; amount_paise: number }) =>
      updateInstallment(installment.id, payload),
    onSuccess: () => onSaved(`Installment ${installment.milestone} updated.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to update installment.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!dueOn) {
      setFormError("A due date is required.");
      return;
    }
    const amountPaise = rupeesInputToPaise(amountRupees);
    if (!Number.isFinite(amountPaise) || amountPaise < 0) {
      setFormError("Enter a valid non-negative amount (up to 2 decimal places).");
      return;
    }
    if (amountPaise < installment.paid_paise) {
      setFormError(
        `Amount cannot be below the live paid total of ${formatInr(installment.paid_paise)}.`,
      );
      return;
    }
    setFormError(null);
    mutation.mutate({ due_on: dueOn, amount_paise: amountPaise });
  };

  const isPaid = installment.status === "PAID";

  return (
    <DialogShell
      title={`Edit ${installment.milestone}`}
      description={
        isPaid
          ? "This installment is fully paid. Reduce the amount only after voiding the relevant receipt; the backend enforces the live paid total."
          : "Adjust the due date or amount. Status is recomputed from the balance; marking an installment paid requires posting a receipt."
      }
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <dl className="grid grid-cols-3 gap-2 rounded-xl bg-charcoal/[0.03] p-3 text-[11px]">
          <div>
            <dt className="text-charcoal/55">Current due</dt>
            <dd className="mt-0.5 font-medium text-charcoal">{formatShortDate(installment.due_on)}</dd>
          </div>
          <div>
            <dt className="text-charcoal/55">Paid</dt>
            <dd className="mt-0.5 font-medium text-emerald-700">{formatInr(installment.paid_paise)}</dd>
          </div>
          <div>
            <dt className="text-charcoal/55">Status</dt>
            <dd className="mt-0.5 font-medium text-charcoal">{installment.status}</dd>
          </div>
        </dl>
        <div>
          <label htmlFor="edit-installment-due" className={saleLabelClasses}>
            Due date <span className="text-rose-500">*</span>
          </label>
          <input
            id="edit-installment-due"
            type="date"
            value={dueOn}
            onChange={(e) => setDueOn(e.target.value)}
            className={saleInputClasses}
          />
        </div>
        <div>
          <label htmlFor="edit-installment-amount" className={saleLabelClasses}>
            Amount (INR) <span className="text-rose-500">*</span>
          </label>
          <input
            id="edit-installment-amount"
            inputMode="decimal"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
            className={saleInputClasses}
          />
          <p className="mt-1 text-[11px] text-charcoal/50">
            Minimum {formatInr(installment.paid_paise)} (live paid total).
          </p>
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={saleSecondaryButton}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={salePrimaryButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}

interface VoidReceiptDialogProps {
  receipt: ReceiptItem;
  onClose: () => void;
  onVoided: (message: string) => void | Promise<void>;
}

/**
 * Reverse a receipt's financial effect. The original row is preserved with
 * void metadata and excluded from live totals; linked documents are voided
 * server-side and the booking re-opens if an installment is still outstanding.
 * A replacement posting needs a new idempotency key.
 */
export function VoidReceiptDialog({ receipt, onClose, onVoided }: VoidReceiptDialogProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (value: string) => voidReceipt(receipt.id, value),
    onSuccess: () => onVoided(`Receipt ${receipt.receipt_number} voided; balances recalculated.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to void receipt.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = reason.trim();
    if (trimmed.length < 3) {
      setFormError("A reason of at least 3 characters is required for the audit trail.");
      return;
    }
    setFormError(null);
    mutation.mutate(trimmed);
  };

  return (
    <DialogShell
      title={`Void receipt ${receipt.receipt_number}`}
      description="Reverses this receipt's financial effect without deleting it. The amount, installment balance, and any linked documents are updated; the original entry stays in the audit trail. This is not a cash refund."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <dl className="grid grid-cols-2 gap-2 rounded-xl bg-charcoal/[0.03] p-3 text-[11px]">
          <div>
            <dt className="text-charcoal/55">Amount</dt>
            <dd className="mt-0.5 font-medium text-charcoal">{formatInr(receipt.amount_paise)}</dd>
          </div>
          <div>
            <dt className="text-charcoal/55">Channel</dt>
            <dd className="mt-0.5 font-medium text-charcoal">
              {receipt.channel}
              {receipt.reference ? ` · ${receipt.reference}` : ""}
            </dd>
          </div>
        </dl>
        <div>
          <label htmlFor="void-receipt-reason" className={saleLabelClasses}>
            Reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            id="void-receipt-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder="e.g. Duplicate posting — bank reference recorded twice"
            className={saleInputClasses}
          />
          <p className="mt-1 text-[11px] text-charcoal/50">{reason.trim().length}/500 characters.</p>
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={saleSecondaryButton}>
            Keep receipt
          </button>
          <button type="submit" disabled={mutation.isPending} className={saleDangerButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Voiding…" : "Void receipt"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
