import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, Plus, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { errorMessage } from "../../shared/apiRequest";
import { recordReceipt } from "./salesBookingApi";
import type { InstallmentItem, ReceiptItem } from "./salesBookingModel";
import { RECEIPT_CHANNELS } from "./salesBookingModel";
import {
  formatInr,
  paiseToRupeesInput,
  rupeesInputToPaise,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "./salesBookingUi";

const receiptSchema = z.object({
  amountRupees: z
    .string()
    .trim()
    .min(1, "Amount is required.")
    .refine(
      (value) => {
        const paise = rupeesInputToPaise(value);
        return Number.isFinite(paise) && paise > 0;
      },
      { message: "Enter a positive rupee amount." },
    ),
  channel: z.enum(["UPI", "CHEQUE", "NEFT", "CASH", "CARD", "LOAN_DISBURSAL"]),
  reference: z.string().trim().max(160),
  notes: z.string().trim().max(2000),
  paidAt: z.string().trim(),
});

type ReceiptFormValues = z.infer<typeof receiptSchema>;

interface RecordReceiptModalProps {
  installment: InstallmentItem;
  onClose: () => void;
  onRecorded: (receipt: ReceiptItem) => Promise<void> | void;
}

export function RecordReceiptModal({
  installment,
  onClose,
  onRecorded,
}: RecordReceiptModalProps) {
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ReceiptFormValues>({
    resolver: zodResolver(receiptSchema),
    defaultValues: {
      amountRupees: paiseToRupeesInput(installment.outstanding_paise),
      channel: "UPI",
      reference: "",
      notes: "",
      paidAt: "",
    },
  });

  useEffect(() => {
    reset({
      amountRupees: paiseToRupeesInput(installment.outstanding_paise),
      channel: "UPI",
      reference: "",
      notes: "",
      paidAt: "",
    });
  }, [installment, reset]);

  const mutation = useMutation({
    mutationFn: async (values: ReceiptFormValues) => {
      const payload = {
        installment_id: installment.id,
        amount_paise: rupeesInputToPaise(values.amountRupees),
        channel: values.channel,
        reference: values.reference.trim() || null,
        notes: values.notes.trim() || null,
        paid_at: values.paidAt.trim()
          ? new Date(values.paidAt).toISOString()
          : null,
      };
      return recordReceipt(payload);
    },
    onSuccess: async (created) => {
      await onRecorded(created);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to record receipt."));
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Record receipt"
        className="max-h-[90svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Record receipt
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              {installment.milestone} · Outstanding{" "}
              {formatInr(installment.outstanding_paise)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close receipt form"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form
          noValidate
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="p-5"
        >
          {error && (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {error}
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="receipt-amount" className={saleLabelClasses}>
                Amount (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                id="receipt-amount"
                inputMode="decimal"
                className={saleInputClasses}
                {...register("amountRupees")}
              />
              {errors.amountRupees && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.amountRupees.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="receipt-channel" className={saleLabelClasses}>
                Channel <span className="text-rose-500">*</span>
              </label>
              <select
                id="receipt-channel"
                className={saleInputClasses}
                {...register("channel")}
              >
                {RECEIPT_CHANNELS.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
              {errors.channel && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.channel.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="receipt-reference" className={saleLabelClasses}>
                Reference
              </label>
              <input
                id="receipt-reference"
                maxLength={160}
                placeholder="UPI/Cheque transaction id"
                className={saleInputClasses}
                {...register("reference")}
              />
              {errors.reference && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.reference.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="receipt-paid-at" className={saleLabelClasses}>
                Paid at (optional)
              </label>
              <input
                id="receipt-paid-at"
                type="datetime-local"
                className={saleInputClasses}
                {...register("paidAt")}
              />
              {errors.paidAt && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.paidAt.message}
                </p>
              )}
            </div>

            <div className="sm:col-span-2">
              <label htmlFor="receipt-notes" className={saleLabelClasses}>
                Notes
              </label>
              <textarea
                id="receipt-notes"
                rows={3}
                maxLength={2000}
                className={`${saleInputClasses} resize-y`}
                {...register("notes")}
              />
              {errors.notes && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.notes.message}
                </p>
              )}
            </div>
          </div>

          <div className="mt-5 flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting || mutation.isPending}
              className={saleSecondaryButton}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className={salePrimaryButton}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <Plus aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Saving…" : "Record receipt"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
