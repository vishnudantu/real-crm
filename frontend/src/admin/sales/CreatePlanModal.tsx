import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, Plus, Trash2, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { errorMessage } from "../../shared/apiRequest";
import { createPaymentPlan } from "./salesBookingApi";
import type { PaymentPlanItem } from "./salesBookingModel";
import { PLAN_TYPES } from "./salesBookingModel";
import {
  formatInr,
  rupeesInputToPaise,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "./salesBookingUi";

const installmentSchema = z.object({
  milestone: z.string().trim().min(1, "Milestone is required.").max(160),
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
  dueOn: z.string().trim().min(1, "Due date is required."),
});

const createPlanSchema = z.object({
  name: z.string().trim().min(1, "Plan name is required.").max(128),
  planType: z.enum(["CONSTRUCTION_LINKED", "TIME_LINKED", "HYBRID"]),
  installments: z.array(installmentSchema).min(1, "Add at least one installment."),
});

type CreatePlanFormValues = z.infer<typeof createPlanSchema>;

interface CreatePlanModalProps {
  bookingId: string;
  considerationPaise: number;
  onClose: () => void;
  onCreated: (plan: PaymentPlanItem) => Promise<void> | void;
}

export function CreatePlanModal({
  bookingId,
  considerationPaise,
  onClose,
  onCreated,
}: CreatePlanModalProps) {
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreatePlanFormValues>({
    resolver: zodResolver(createPlanSchema),
    defaultValues: {
      name: "",
      planType: "CONSTRUCTION_LINKED",
      installments: [
        { milestone: "", amountRupees: "", dueOn: "" },
        { milestone: "", amountRupees: "", dueOn: "" },
      ],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "installments",
  });

  useEffect(() => {
    reset({
      name: "",
      planType: "CONSTRUCTION_LINKED",
      installments: [
        { milestone: "", amountRupees: "", dueOn: "" },
        { milestone: "", amountRupees: "", dueOn: "" },
      ],
    });
  }, [bookingId, reset]);

  const watchedInstallments = watch("installments");
  const totalPaise = useMemo(
    () =>
      watchedInstallments.reduce((sum, row) => {
        const paise = rupeesInputToPaise(row.amountRupees ?? "");
        return Number.isFinite(paise) ? sum + paise : sum;
      }, 0),
    [watchedInstallments],
  );
  const deltaPaise = considerationPaise - totalPaise;
  const sumMatches = deltaPaise === 0;

  const mutation = useMutation({
    mutationFn: async (values: CreatePlanFormValues) => {
      if (!sumMatches) {
        throw new Error(
          "Installment amounts must sum exactly to the booking consideration.",
        );
      }
      return createPaymentPlan(bookingId, {
        name: values.name.trim(),
        plan_type: values.planType,
        installments: values.installments.map((row) => ({
          milestone: row.milestone.trim(),
          amount_paise: rupeesInputToPaise(row.amountRupees),
          due_on: row.dueOn,
        })),
      });
    },
    onSuccess: async (created) => {
      await onCreated(created);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to create payment plan."));
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
        aria-label="Create payment plan"
        className="max-h-[92svh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Create payment plan
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Installments must total {formatInr(considerationPaise)}.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close plan form"
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
              <label htmlFor="create-plan-name" className={saleLabelClasses}>
                Plan name <span className="text-rose-500">*</span>
              </label>
              <input
                id="create-plan-name"
                placeholder="Standard construction-linked plan"
                maxLength={128}
                className={saleInputClasses}
                {...register("name")}
              />
              {errors.name && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.name.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="create-plan-type" className={saleLabelClasses}>
                Plan type <span className="text-rose-500">*</span>
              </label>
              <select
                id="create-plan-type"
                className={saleInputClasses}
                {...register("planType")}
              >
                {PLAN_TYPES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
              {errors.planType && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.planType.message}
                </p>
              )}
            </div>
          </div>

          <fieldset className="mt-5">
            <legend className="text-[11px] font-semibold text-charcoal/75">
              Installments <span className="text-rose-500">*</span>
            </legend>
            <p className="mt-0.5 text-[11px] text-charcoal/55">
              Add one row per milestone. All amounts are in Indian rupees.
            </p>

            <div className="mt-3 space-y-3">
              {fields.map((field, index) => (
                <div
                  key={field.id}
                  className="grid gap-3 rounded-xl border border-charcoal/10 bg-white p-3 sm:grid-cols-12"
                >
                  <div className="sm:col-span-5">
                    <label
                      htmlFor={`installment-milestone-${index}`}
                      className={saleLabelClasses}
                    >
                      Milestone
                    </label>
                    <input
                      id={`installment-milestone-${index}`}
                      placeholder="Booking amount"
                      maxLength={160}
                      className={saleInputClasses}
                      {...register(`installments.${index}.milestone`)}
                    />
                    {errors.installments?.[index]?.milestone && (
                      <p className="mt-1 text-[11px] text-rose-600">
                        {errors.installments[index]?.milestone?.message}
                      </p>
                    )}
                  </div>
                  <div className="sm:col-span-3">
                    <label
                      htmlFor={`installment-amount-${index}`}
                      className={saleLabelClasses}
                    >
                      Amount (₹)
                    </label>
                    <input
                      id={`installment-amount-${index}`}
                      inputMode="decimal"
                      placeholder="750000"
                      className={saleInputClasses}
                      {...register(`installments.${index}.amountRupees`)}
                    />
                    {errors.installments?.[index]?.amountRupees && (
                      <p className="mt-1 text-[11px] text-rose-600">
                        {errors.installments[index]?.amountRupees?.message}
                      </p>
                    )}
                  </div>
                  <div className="sm:col-span-3">
                    <label
                      htmlFor={`installment-due-${index}`}
                      className={saleLabelClasses}
                    >
                      Due on
                    </label>
                    <input
                      id={`installment-due-${index}`}
                      type="date"
                      className={saleInputClasses}
                      {...register(`installments.${index}.dueOn`)}
                    />
                    {errors.installments?.[index]?.dueOn && (
                      <p className="mt-1 text-[11px] text-rose-600">
                        {errors.installments[index]?.dueOn?.message}
                      </p>
                    )}
                  </div>
                  <div className="flex items-end sm:col-span-1">
                    <button
                      type="button"
                      onClick={() => remove(index)}
                      disabled={fields.length <= 1}
                      aria-label={`Remove installment ${index + 1}`}
                      className="inline-flex size-9 items-center justify-center rounded-lg border border-charcoal/15 text-charcoal/60 transition-colors hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <Trash2 aria-hidden="true" className="size-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {errors.installments?.root && (
              <p className="mt-2 text-[11px] text-rose-600">
                {errors.installments.root.message}
              </p>
            )}
            {typeof errors.installments?.message === "string" && (
              <p className="mt-2 text-[11px] text-rose-600">
                {errors.installments.message}
              </p>
            )}

            <button
              type="button"
              onClick={() =>
                append({ milestone: "", amountRupees: "", dueOn: "" })
              }
              className={`${saleSecondaryButton} mt-3`}
            >
              <Plus aria-hidden="true" className="size-3.5" />
              <span>Add installment</span>
            </button>
          </fieldset>

          <div
            className={`mt-4 rounded-xl border px-4 py-3 text-xs ${
              sumMatches
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold">Total installments</span>
              <span className="font-semibold">{formatInr(totalPaise)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px]">
              <span>Booking consideration</span>
              <span>{formatInr(considerationPaise)}</span>
            </div>
            {!sumMatches && (
              <p className="mt-2 text-[11px]">
                {deltaPaise > 0
                  ? `Add ${formatInr(deltaPaise)} more across installments.`
                  : `Reduce installments by ${formatInr(Math.abs(deltaPaise))}.`}
              </p>
            )}
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
              disabled={isSubmitting || mutation.isPending || !sumMatches}
              className={salePrimaryButton}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <Plus aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Creating…" : "Create plan"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
