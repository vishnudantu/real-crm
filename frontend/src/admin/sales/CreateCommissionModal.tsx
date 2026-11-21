import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, Plus, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { errorMessage } from "../../shared/apiRequest";
import { createCommission } from "./salesBookingApi";
import type { CommissionItem } from "./salesBookingModel";
import {
  formatInr,
  rupeesInputToPaise,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "./salesBookingUi";

const commissionSchema = z.object({
  brokerName: z.string().trim().min(1, "Broker name is required.").max(255),
  brokerPhone: z.string().trim().max(32),
  amountRupees: z
    .string()
    .trim()
    .min(1, "Commission amount is required.")
    .refine(
      (value) => {
        const paise = rupeesInputToPaise(value);
        return Number.isFinite(paise) && paise >= 0;
      },
      { message: "Enter a non-negative rupee amount." },
    ),
  basisPercent: z.string().trim(),
});

type CommissionFormValues = z.infer<typeof commissionSchema>;

interface CreateCommissionModalProps {
  bookingId: string;
  considerationPaise: number;
  onClose: () => void;
  onCreated: (commission: CommissionItem) => Promise<void> | void;
}

export function CreateCommissionModal({
  bookingId,
  considerationPaise,
  onClose,
  onCreated,
}: CreateCommissionModalProps) {
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CommissionFormValues>({
    resolver: zodResolver(commissionSchema),
    defaultValues: {
      brokerName: "",
      brokerPhone: "",
      amountRupees: "",
      basisPercent: "",
    },
  });

  const amountRupees = watch("amountRupees");
  const basisPercent = watch("basisPercent");

  const computedPaiseFromPercent = (() => {
    const trimmed = basisPercent.trim();
    if (!trimmed) return null;
    const percent = Number(trimmed);
    if (!Number.isFinite(percent) || percent < 0) return null;
    return Math.round((considerationPaise * percent) / 100);
  })();

  const mutation = useMutation({
    mutationFn: async (values: CommissionFormValues) => {
      const basis: Record<string, unknown> = {};
      const trimmedPercent = values.basisPercent.trim();
      if (trimmedPercent) {
        const percent = Number(trimmedPercent);
        if (Number.isFinite(percent)) {
          basis.percent = percent;
        }
      }
      return createCommission(bookingId, {
        broker_name: values.brokerName.trim(),
        broker_phone: values.brokerPhone.trim() || null,
        amount_paise: rupeesInputToPaise(values.amountRupees),
        basis,
      });
    },
    onSuccess: async (created) => {
      await onCreated(created);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to create commission."));
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
        aria-label="Add broker commission"
        className="max-h-[90svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Add broker commission
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Record a referral payout against this sale booking.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close commission form"
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
            <div className="sm:col-span-2">
              <label htmlFor="commission-name" className={saleLabelClasses}>
                Broker name <span className="text-rose-500">*</span>
              </label>
              <input
                id="commission-name"
                maxLength={255}
                placeholder="Suresh Realty Advisors"
                className={saleInputClasses}
                {...register("brokerName")}
              />
              {errors.brokerName && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.brokerName.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="commission-phone" className={saleLabelClasses}>
                Broker phone
              </label>
              <input
                id="commission-phone"
                maxLength={32}
                placeholder="+91 98765 43210"
                className={saleInputClasses}
                {...register("brokerPhone")}
              />
              {errors.brokerPhone && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.brokerPhone.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="commission-amount" className={saleLabelClasses}>
                Commission amount (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                id="commission-amount"
                inputMode="decimal"
                placeholder="150000"
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
              <label htmlFor="commission-percent" className={saleLabelClasses}>
                Basis (% of consideration)
              </label>
              <input
                id="commission-percent"
                inputMode="decimal"
                placeholder="2"
                className={saleInputClasses}
                {...register("basisPercent")}
              />
              {errors.basisPercent && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.basisPercent.message}
                </p>
              )}
              {computedPaiseFromPercent !== null && (
                <p className="mt-1 text-[11px] text-charcoal/55">
                  ≈ {formatInr(computedPaiseFromPercent)} of consideration
                </p>
              )}
            </div>
          </div>

          {amountRupees.trim() && (
            <p className="mt-4 rounded-xl border border-charcoal/10 bg-white px-4 py-3 text-xs text-charcoal/75">
              Recording commission of{" "}
              <span className="font-semibold text-charcoal">
                ₹{amountRupees.trim()}
              </span>{" "}
              against this booking.
            </p>
          )}

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
              <span>{mutation.isPending ? "Saving…" : "Add commission"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
